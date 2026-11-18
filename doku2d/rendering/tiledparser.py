"""CPU-only Tiled reader. Parsing never opens a window or loads a GPU texture."""
from dataclasses import dataclass, field
from pathlib import Path
import base64
import gzip
import json
import struct
import zlib
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class TileCell:
    tile_id: int = 0
    tileset: int = 0
    flip_h: bool = False
    flip_v: bool = False
    transpose: bool = False


@dataclass
class MapObject:
    id: int = 0
    name: str = ''
    type: str = ''
    position: tuple = (0,0)
    size: tuple = (0,0)
    rotation: float = 0
    visible: bool = True
    shape: str = 'rectangle'
    points: tuple = ()
    tile: TileCell | None = None
    properties: dict = field(default_factory=dict)
    layer: str = ''
    text: dict | None = None


@dataclass
class TileSetData:
    name: str = ''
    firstgid: int = 1
    tile_size: tuple = (16,16)
    image: Path | None = None
    image_size: tuple = (0,0)
    columns: int = 0
    tile_count: int = 0
    spacing: int = 0
    margin: int = 0
    offset: tuple = (0,0)
    properties: dict = field(default_factory=dict)
    tiles: dict = field(default_factory=dict)
    transparent_color: tuple | None = None
    wangsets: tuple = ()


@dataclass
class LayerData:
    name: str = ''
    kind: str = 'tilelayer'
    cells: dict = field(default_factory=dict)
    objects: tuple = ()
    image: Path | None = None
    offset: tuple = (0,0)
    parallax: tuple = (1,1)
    opacity: float = 1
    tint: tuple = (255,255,255,255)
    visible: bool = True
    properties: dict = field(default_factory=dict)
    repeat_x: bool = False
    repeat_y: bool = False
    draw_order: str = 'topdown'


@dataclass
class MapData:
    name: str = ''
    size: tuple = (0,0)
    tile_size: tuple = (16,16)
    layers: tuple = ()
    tilesets: tuple = ()
    properties: dict = field(default_factory=dict)
    infinite: bool = False
    render_order: str = 'right-down'
    parallax_origin: tuple = (0,0)
    background_color: tuple | None = None


def tiled_color(value):
    if value is None: return None
    value = value.lstrip('#')
    if len(value) == 6: return tuple(bytes.fromhex(value))+(255,)
    if len(value) == 8:
        a,r,g,b = bytes.fromhex(value)
        return r,g,b,a
    raise ValueError('Tiled colors must use #RRGGBB or #AARRGGBB')


class TiledParser:
    """TiledParser.parse('level.tmx') -> MapData suitable for TileMap(data)."""
    @classmethod
    def parse(cls,path):
        path = Path(path).resolve()
        raw = cls._read(path)
        if raw.get('orientation','orthogonal') != 'orthogonal':
            raise NotImplementedError('TileMap currently renders orthogonal Tiled maps only')
        if raw.get('renderorder','right-down') not in ('right-down','right-up','left-down','left-up'):
            raise ValueError('Invalid Tiled render order')
        tile_size = (int(raw['tilewidth']),int(raw['tileheight']))
        if min(tile_size) <= 0: raise ValueError('Map tile size must be positive')
        tilesets = tuple(cls._tileset(ts,path.parent) for ts in raw.get('tilesets',[]))
        gids = [ts.firstgid for ts in tilesets]
        if gids != sorted(set(gids)) or any(gid < 1 for gid in gids):
            raise ValueError('Tileset firstgid values must be positive, unique and increasing')
        layers = tuple(cls._layers(raw.get('layers',[]),path.parent,tile_size,tilesets))
        names = [layer.name for layer in layers]
        if len(names) != len(set(names)): raise ValueError('Layer paths must be unique')
        return MapData(path.stem,(int(raw.get('width',0)),int(raw.get('height',0))),tile_size,
                       layers,tilesets,cls._properties(raw,path.parent),bool(raw.get('infinite',False)),
                       raw.get('renderorder','right-down'),
                       (float(raw.get('parallaxoriginx',0)),float(raw.get('parallaxoriginy',0))),
                       tiled_color(raw.get('backgroundcolor')))

    @staticmethod
    def _properties(raw,base):
        result = {}
        for prop in raw.get('properties',[]):
            value,kind = prop.get('value'),prop.get('type','string')
            if kind == 'file' and value: value = (base/value).resolve()
            elif kind == 'color' and value: value = tiled_color(value)
            elif kind == 'class' and isinstance(value,dict): value = dict(value)
            result[prop['name']] = value
        return result

    @classmethod
    def _tileset(cls,raw,base):
        firstgid = int(raw['firstgid'])
        if 'source' in raw:
            source = (base/raw['source']).resolve()
            raw,base = cls._read(source),source.parent
        if raw.get('objectalignment','unspecified') not in ('unspecified','bottomleft'):
            raise NotImplementedError('Tile objects currently require bottom-left alignment')
        image = (base/raw['image']).resolve() if raw.get('image') else None
        tw,th = int(raw['tilewidth']),int(raw['tileheight'])
        if min(tw,th) <= 0: raise ValueError('Tileset tile size must be positive')
        spacing,margin = int(raw.get('spacing',0)),int(raw.get('margin',0))
        if min(spacing,margin) < 0: raise ValueError('Tileset margin/spacing cannot be negative')
        width,height = int(raw.get('imagewidth',0)),int(raw.get('imageheight',0))
        columns = int(raw.get('columns',0)) or (max(0,(width-2*margin+spacing)//(tw+spacing)) if image else 0)
        rows = max(0,(height-2*margin+spacing)//(th+spacing))
        tiles = {}
        for tile in raw.get('tiles',[]):
            item = dict(tile)
            item['properties'] = cls._properties(tile,base)
            if tile.get('image'): item['image'] = (base/tile['image']).resolve()
            animation = tuple((int(frame['tileid']),int(frame['duration'])/1000) for frame in tile.get('animation',[]))
            if any(duration <= 0 or index < 0 for index,duration in animation):
                raise ValueError('Tile animations need valid frame ids and positive durations')
            item['animation'] = animation
            tiles[int(tile['id'])] = item
        count = int(raw.get('tilecount',columns*rows if image else len(tiles)))
        offset = raw.get('tileoffset',{})
        return TileSetData(raw.get('name','Tiles'),firstgid,(tw,th),image,(width,height),
                           columns,count,spacing,margin,(float(offset.get('x',0)),float(offset.get('y',0))),
                           cls._properties(raw,base),tiles,tiled_color(raw.get('transparentcolor')),tuple(raw.get('wangsets',[])))

    @staticmethod
    def _cell(gid,tilesets):
        gid = int(gid)
        if not 0 <= gid <= 0xffffffff: raise ValueError('Tiled gids must be unsigned 32-bit integers')
        clean = gid & 0x0fffffff
        if not clean: return None
        for index in range(len(tilesets)-1,-1,-1):
            ts = tilesets[index]
            if clean >= ts.firstgid:
                local = clean-ts.firstgid
                if ts.image and ts.tile_count and local >= ts.tile_count or not ts.image and local not in ts.tiles:
                    raise ValueError(f'Unknown tile gid: {clean}')
                return TileCell(local,index,bool(gid&0x80000000),bool(gid&0x40000000),bool(gid&0x20000000))
        raise ValueError(f'No tileset for gid: {clean}')

    @staticmethod
    def _decode(data,encoding,compression,count):
        if isinstance(data,list): values = data
        elif encoding == 'csv': values = [int(v.strip()) for v in data.replace('\n','').split(',') if v.strip()]
        elif encoding == 'base64':
            payload = base64.b64decode(''.join(data.split()),validate=True)
            if compression == 'zlib': payload = zlib.decompress(payload)
            elif compression == 'gzip': payload = gzip.decompress(payload)
            elif compression: raise NotImplementedError('Use uncompressed, zlib or gzip Tiled data')
            if len(payload) != count*4: raise ValueError('Tile data byte count does not match layer dimensions')
            values = struct.unpack('<'+'I'*count,payload)
        else: raise ValueError(f'Unsupported tile encoding: {encoding!r}')
        if len(values) != count: raise ValueError('Tile data count does not match layer dimensions')
        return values

    @classmethod
    def _layers(cls,layers,base,tile_size,tilesets,*,prefix='',offset=(0,0),parallax=(1,1),opacity=1,visible=True,tint=(255,255,255,255)):
        tw,th = tile_size
        for raw in layers:
            name = prefix+raw.get('name','Layer')
            kind = raw['type']
            position = (offset[0]+float(raw.get('offsetx',0))+float(raw.get('x',0))*tw,
                        offset[1]+float(raw.get('offsety',0))+float(raw.get('y',0))*th)
            factor = (parallax[0]*float(raw.get('parallaxx',1)),parallax[1]*float(raw.get('parallaxy',1)))
            alpha = opacity*float(raw.get('opacity',1))
            if not 0 <= alpha <= 1: raise ValueError('Layer opacity must be in [0,1]')
            shown = visible and bool(raw.get('visible',True))
            tint_color = tiled_color(raw.get('tintcolor')) or (255,255,255,255)
            tint_color = tuple(round(a*b/255) for a,b in zip(tint,tint_color))
            if kind == 'group':
                yield from cls._layers(raw.get('layers',[]),base,tile_size,tilesets,prefix=name+'/',
                                       offset=position,parallax=factor,opacity=alpha,visible=shown,tint=tint_color)
                continue
            layer = LayerData(name,kind,offset=position,parallax=factor,opacity=alpha,visible=shown,
                              tint=tint_color,properties=cls._properties(raw,base))
            if kind == 'tilelayer':
                chunks = raw.get('chunks')
                if chunks is None: chunks = [dict(x=0,y=0,width=raw['width'],height=raw['height'],data=raw.get('data',[]))]
                for chunk in chunks:
                    w,h = int(chunk['width']),int(chunk['height'])
                    if w < 0 or h < 0: raise ValueError('Chunk dimensions cannot be negative')
                    values = cls._decode(chunk['data'],raw.get('encoding'),raw.get('compression'),w*h)
                    for i,gid in enumerate(values):
                        cell = cls._cell(gid,tilesets)
                        if cell is not None: layer.cells[int(chunk['x'])+i%w,int(chunk['y'])+i//w] = cell
            elif kind == 'objectgroup':
                layer.objects = tuple(cls._object(obj,base,tilesets,name,position,shown) for obj in raw.get('objects',[]))
                layer.draw_order = raw.get('draworder','topdown')
            elif kind == 'imagelayer':
                if raw.get('image'): layer.image = (base/raw['image']).resolve()
                layer.repeat_x,layer.repeat_y = bool(raw.get('repeatx',False)),bool(raw.get('repeaty',False))
            else: raise NotImplementedError(f'Unsupported Tiled layer: {kind}')
            yield layer

    @classmethod
    def _object(cls,raw,base,tilesets,layer,offset,visible):
        if raw.get('template'): raise NotImplementedError('Resolve Tiled object templates before exporting')
        shape = next((kind for kind in ('polygon','polyline','ellipse','point','text') if kind in raw),'rectangle')
        return MapObject(int(raw.get('id',0)),raw.get('name',''),raw.get('class',raw.get('type','')),
                         (float(raw.get('x',0))+offset[0],float(raw.get('y',0))+offset[1]),
                         (float(raw.get('width',0)),float(raw.get('height',0))),float(raw.get('rotation',0)),
                         bool(raw.get('visible',True)),shape,
                         tuple((p['x'],p['y']) for p in raw.get(shape,[]) if isinstance(p,dict)) if shape in ('polygon','polyline') else (),
                         cls._cell(raw.get('gid',0),tilesets),cls._properties(raw,base),layer,raw.get('text'))

    @classmethod
    def _read(cls,path):
        if path.suffix.lower() in ('.tmx','.tsx'):
            root = ET.parse(path).getroot()
            if root.tag == 'map':
                data = cls._attrs(root)
                data['layers'] = [cls._xml_layer(child) for child in root if child.tag in ('layer','objectgroup','imagelayer','group')]
                data['tilesets'] = [cls._xml_tileset(child) for child in root.findall('tileset')]
                data['properties'] = cls._xml_properties(root)
                return data
            if root.tag == 'tileset': return cls._xml_tileset(root)
            raise ValueError('Expected a Tiled map or tileset')
        with path.open(encoding='utf-8-sig') as stream: return json.load(stream)

    @staticmethod
    def _attrs(element):
        ints = {'firstgid','tilewidth','tileheight','tilecount','columns','spacing','margin','width','height',
                'imagewidth','imageheight','id','gid','duration','tileid','startx','starty'}
        floats = {'x','y','offsetx','offsety','parallaxx','parallaxy','parallaxoriginx','parallaxoriginy','opacity','rotation'}
        bools = {'visible','infinite','repeatx','repeaty'}
        return {k:(float(v) if element.tag == 'object' and k in ('width','height') else int(v) if k in ints else float(v) if k in floats else v not in ('0','false') if k in bools else v)
                for k,v in element.attrib.items()}

    @classmethod
    def _xml_properties(cls,element):
        result = []
        for prop in element.findall('properties/property'):
            raw = dict(prop.attrib)
            value = raw.get('value',prop.text or '')
            kind = raw.get('type')
            if kind in ('int','object'): value = int(value)
            elif kind == 'float': value = float(value)
            elif kind == 'bool': value = value not in ('0','false','')
            elif kind == 'class': value = {p['name']:p['value'] for p in cls._xml_properties(prop)}
            raw['value'] = value
            result.append(raw)
        return result

    @classmethod
    def _xml_tileset(cls,element):
        data = cls._attrs(element)
        data['properties'] = cls._xml_properties(element)
        image = element.find('image')
        if image is not None:
            data.update(image=image.get('source'),imagewidth=int(image.get('width',0)),imageheight=int(image.get('height',0)))
            if image.get('trans'): data['transparentcolor'] = '#'+image.get('trans')
        offset = element.find('tileoffset')
        if offset is not None: data['tileoffset'] = cls._attrs(offset)
        data['wangsets'] = []
        for wang in element.findall('wangsets/wangset'):
            item=cls._attrs(wang)
            item['colors']=[cls._attrs(color) for color in wang if color.tag in ('wangcolor','wangedgecolor','wangcornercolor')]
            item['wangtiles']=[]
            for tile in wang.findall('wangtile'):
                values=cls._attrs(tile)
                values['wangid']=[int(v) for v in tile.get('wangid','').split(',')]
                item['wangtiles'].append(values)
            data['wangsets'].append(item)
        data['tiles'] = []
        for tile in element.findall('tile'):
            item = cls._attrs(tile)
            item['properties'] = cls._xml_properties(tile)
            item['animation'] = [cls._attrs(frame) for frame in tile.findall('animation/frame')]
            image = tile.find('image')
            if image is not None: item.update(image=image.get('source'),imagewidth=int(image.get('width',0)),imageheight=int(image.get('height',0)))
            group = tile.find('objectgroup')
            if group is not None: item['objectgroup'] = cls._xml_layer(group)
            data['tiles'].append(item)
        return data

    @classmethod
    def _xml_layer(cls,element):
        data = cls._attrs(element)
        data['type'] = 'tilelayer' if element.tag == 'layer' else element.tag
        data['properties'] = cls._xml_properties(element)
        if element.tag == 'group': data['layers'] = [cls._xml_layer(child) for child in element if child.tag in ('layer','objectgroup','imagelayer','group')]
        elif element.tag == 'layer':
            content = element.find('data')
            if content is None: raise ValueError('Tiled tile layer is missing data')
            data.update(encoding=content.get('encoding'),compression=content.get('compression'))
            def payload(node):
                return [int(tile.get('gid',0)) for tile in node.findall('tile')] if not content.get('encoding') else node.text or ''
            chunks = content.findall('chunk')
            if chunks: data['chunks'] = [dict(cls._attrs(chunk),data=payload(chunk)) for chunk in chunks]
            else: data['data'] = payload(content)
        elif element.tag == 'imagelayer':
            image = element.find('image')
            if image is not None: data['image'] = image.get('source')
        elif element.tag == 'objectgroup': data['objects'] = [cls._xml_object(obj) for obj in element.findall('object')]
        return data

    @classmethod
    def _xml_object(cls,element):
        data = cls._attrs(element)
        data['properties'] = cls._xml_properties(element)
        for kind in ('ellipse','point','polygon','polyline','text'):
            child = element.find(kind)
            if child is None: continue
            if kind in ('polygon','polyline'):
                data[kind] = [dict(zip(('x','y'),map(float,point.split(',')))) for point in child.get('points','').split()]
            elif kind == 'text': data[kind] = dict(cls._attrs(child),text=child.text or '')
            else: data[kind] = True
        return data


__all__ = ['TiledParser','MapData','MapObject','TileCell']
