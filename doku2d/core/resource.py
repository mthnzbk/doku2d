"""Per-game resource cache with one path policy and copyable map data."""
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from pathlib import Path
from copy import deepcopy
import json
from sfml.graphics import Texture,Font,Image,Color
from sfml.audio import SoundBuffer
from .entity import Object


_ASSET_TYPES = {
    '.png': 'textures', '.jpg': 'textures', '.jpeg': 'textures', '.bmp': 'textures',
    '.ttf': 'fonts', '.otf': 'fonts',
    '.wav': 'sounds', '.ogg': 'sounds', '.flac': 'sounds',
    '.tmx': 'maps', '.tmj': 'maps', '.json': 'json',
}


class PreloadRequest:
    """Status of a set of assets requested with Resources.preload_async."""

    def __init__(self, assets):
        self._assets = assets

    @property
    def done(self):
        return all(asset.done() for asset in self._assets.values())

    @property
    def progress(self):
        """Fraction of assets finished, including failed or cancelled assets."""
        return (sum(asset.done() for asset in self._assets.values()) / len(self._assets)
                if self._assets else 1.0)

    @property
    def errors(self):
        errors = {}
        for path, asset in self._assets.items():
            if asset.cancelled():
                errors[path] = CancelledError()
            elif asset.done() and (error := asset.exception()) is not None:
                errors[path] = error
        return errors


def _prepare_asset(kind, path, cached_text=None):
    if kind == 'textures':
        return Image.from_file(str(path))
    if kind == 'fonts':
        return Font.from_file(str(path))
    if kind == 'sounds':
        return SoundBuffer.from_file(str(path))
    if kind == 'maps':
        from ..rendering.tiledparser import TiledParser
        return TiledParser.parse(path)
    text = path.read_text(encoding='utf-8-sig') if cached_text is None else cached_text
    return (text, json.loads(text)) if kind == 'json' else text


class Resources(Object):
    def __init__(self,root='.'):
        super().__init__()
        self._root=Path(root).resolve()
        self._textures={};self._fonts={};self._sounds={};self._maps={};self._json={};self._text={}
        self._atlases = {}
        self._preloader = None
        self._pending_preloads = {}
        self.preloads_per_frame = 2
    @property
    def root(self):return self._root
    def resolve(self,path):
        text=str(path)
        if text.startswith('res://'):text=text[6:]
        return (self.root/Path(text)).resolve()
    def get_texture(self,path,*,color_key=None):
        path=self.resolve(path);key=(path,tuple(color_key[:3]) if color_key is not None else None)
        if key not in self._textures:
            if color_key is None:texture=Texture.from_file(str(path))
            else:
                image=Image.from_file(str(path))
                for y in range(int(image.size.y)):
                    for x in range(int(image.size.x)):
                        p=image[x,y]
                        if (p.r,p.g,p.b)==tuple(color_key[:3]):image[x,y]=Color.TRANSPARENT
                texture=Texture.from_image(image)
            self._textures[key]=texture
        return self._textures[key]
    def get_font(self,path):
        path=self.resolve(path)
        if path not in self._fonts:self._fonts[path]=Font.from_file(str(path))
        return self._fonts[path]
    def get_sound(self,path):
        path=self.resolve(path)
        if path not in self._sounds:self._sounds[path]=SoundBuffer.from_file(str(path))
        return self._sounds[path]
    def get_map(self,path):
        from ..rendering.tiledparser import TiledParser
        path=self.resolve(path)
        if path not in self._maps:self._maps[path]=TiledParser.parse(path)
        return deepcopy(self._maps[path])
    def load_map(self,path,*,collisions=False):
        from ..rendering.tilemap import TileMap
        return TileMap(self.get_map(path),resources=self,collisions=collisions)
    def get_text(self,path):
        path=self.resolve(path)
        if path not in self._text:self._text[path]=path.read_text(encoding='utf-8-sig')
        return self._text[path]
    def get_json(self,path):
        path=self.resolve(path)
        if path not in self._json:self._json[path]=json.loads(self.get_text(path))
        return deepcopy(self._json[path])
    def load_atlas(self, path):
        from ..rendering.atlas import SpriteAtlas

        path = self.resolve(path)
        if path not in self._atlases:
            self._atlases[path] = SpriteAtlas.from_file(path, resources=self)
        return self._atlases[path]
    def preload(self,*paths):
        loaders = {'textures':self.get_texture, 'fonts':self.get_font, 'sounds':self.get_sound,
                   'maps':self.get_map, 'json':self.get_json, 'text':self.get_text}
        for path in paths:
            loaders[_ASSET_TYPES.get(Path(str(path)).suffix.lower(), 'text')](path)
        return self

    def _submit_preparation(self, prepare, *args):
        if self._preloader is None:
            self._preloader = ThreadPoolExecutor(max_workers=2, thread_name_prefix='doku2d-assets')
        return self._preloader.submit(prepare, *args)

    def _asset_cache(self, kind, path):
        return getattr(self, '_'+kind), (path, None) if kind == 'textures' else path

    @property
    def preloads_per_frame(self):
        """Maximum prepared assets applied by each Game.update call."""
        return self._preloads_per_frame

    @preloads_per_frame.setter
    def preloads_per_frame(self, value):
        if type(value) is not int or value < 1:
            raise ValueError('preloads_per_frame must be a positive integer')
        self._preloads_per_frame = value

    def preload_async(self, *paths):
        """Prepare assets in the background and return a PreloadRequest."""
        assets = {}
        for value in paths:
            path = self.resolve(value)
            if path in assets:
                continue
            kind = _ASSET_TYPES.get(path.suffix.lower(), 'text')
            cache, key = self._asset_cache(kind, path)
            if path in self._pending_preloads:
                assets[path] = self._pending_preloads[path][2]
            else:
                completed = Future()
                if key in cache:
                    completed.set_result(None)
                else:
                    self._pending_preloads[path] = kind, None, completed
                assets[path] = completed
        self._start_preloads()
        return PreloadRequest(assets)

    def _start_preloads(self):
        slots = max(4, self.preloads_per_frame * 2)
        for path, (kind, prepared, completed) in self._pending_preloads.items():
            if not slots:
                break
            if prepared is None:
                prepared = self._submit_preparation(_prepare_asset, kind, path, self._text.get(path))
                self._pending_preloads[path] = kind, prepared, completed
            slots -= 1

    def update_preloads(self):
        """Apply ready assets on the calling thread, up to the frame budget."""
        count = 0
        for path, (kind, prepared, completed) in tuple(self._pending_preloads.items()):
            if prepared is None:
                break
            if not prepared.done():
                continue
            del self._pending_preloads[path]
            cache, key = self._asset_cache(kind, path)
            try:
                if key not in cache:
                    value = prepared.result()
                    if kind == 'textures':
                        value = Texture.from_image(value)
                    elif kind == 'json':
                        text, value = value
                        self._text.setdefault(path, text)
                    cache[key] = value
                completed.set_result(None)
            except Exception as error:
                completed.set_exception(error)
            count += 1
            if count >= self.preloads_per_frame:
                break
        self._start_preloads()
        return count

    def _cancel_preload(self, path):
        pending = self._pending_preloads.pop(path, None)
        if pending is not None:
            _, prepared, completed = pending
            if prepared is not None:
                prepared.cancel()
            completed.cancel()

    @property
    def cache_info(self):
        return {name:len(getattr(self,'_'+name)) for name in ('textures','fonts','sounds','maps','json','text','atlases')}
    def unload(self,path):
        path=self.resolve(path)
        self._cancel_preload(path)
        unloaded_textures = []
        for key in tuple(self._textures):
            if key[0] == path:
                unloaded_textures.append(self._textures.pop(key))
        for cache in (self._fonts,self._sounds,self._maps,self._json,self._text,self._atlases):cache.pop(path,None)
        for key, atlas in tuple(self._atlases.items()):
            if any(atlas.texture is texture for texture in unloaded_textures):
                del self._atlases[key]
    def clear(self):
        for path in tuple(self._pending_preloads):
            self._cancel_preload(path)
        if self._preloader is not None:
            self._preloader.shutdown(wait=False, cancel_futures=True)
            self._preloader = None
        for cache in (self._textures,self._fonts,self._sounds,self._maps,self._json,self._text,self._atlases):cache.clear()


Resource=Resources
__all__=['Resources','Resource','PreloadRequest']
