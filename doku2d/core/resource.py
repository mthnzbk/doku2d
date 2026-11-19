"""Per-game resource cache with one path policy and copyable map data."""
from pathlib import Path
from copy import deepcopy
import json
from sfml.graphics import Texture,Font,Image,Color
from sfml.audio import SoundBuffer
from .entity import Object


class Resources(Object):
    def __init__(self,root='.'):
        super().__init__()
        self._root=Path(root).resolve()
        self._textures={};self._fonts={};self._sounds={};self._maps={};self._json={};self._text={}
        self._atlases = {}
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
        loaders={'.png':self.get_texture,'.jpg':self.get_texture,'.jpeg':self.get_texture,
                 '.bmp':self.get_texture,'.ttf':self.get_font,'.otf':self.get_font,
                 '.wav':self.get_sound,'.ogg':self.get_sound,'.flac':self.get_sound,
                 '.tmx':self.get_map,'.tmj':self.get_map,'.json':self.get_json}
        for path in paths:loaders.get(Path(str(path)).suffix.lower(),self.get_text)(path)
        return self
    @property
    def cache_info(self):
        return {name:len(getattr(self,'_'+name)) for name in ('textures','fonts','sounds','maps','json','text','atlases')}
    def unload(self,path):
        path=self.resolve(path)
        unloaded_textures = []
        for key in tuple(self._textures):
            if key[0] == path:
                unloaded_textures.append(self._textures.pop(key))
        for cache in (self._fonts,self._sounds,self._maps,self._json,self._text,self._atlases):cache.pop(path,None)
        for key, atlas in tuple(self._atlases.items()):
            if any(atlas.texture is texture for texture in unloaded_textures):
                del self._atlases[key]
    def clear(self):
        for cache in (self._textures,self._fonts,self._sounds,self._maps,self._json,self._text,self._atlases):cache.clear()


Resource=Resources
__all__=['Resources','Resource']
