"""Editable, chunk-cached orthogonal tile maps with independent drawing layers."""
from contextlib import nullcontext
from math import floor, ceil, isfinite
from pathlib import Path
from types import MappingProxyType
from sfml.graphics import Texture, Image, Rect, Color, Transform, RenderStates, Vertex, VertexArray, PrimitiveType
from sfml.system import Vector2
from ..core import Entity, Signal, Object
from .tiledparser import TiledParser, MapData, MapObject, TileCell
from .autotile import AutoTile


def dimensions(value):
    x,y = value
    if not all(isfinite(v) and int(v) == v and v > 0 for v in (x,y)):
        raise ValueError('Dimensions must be positive integers')
    return int(x),int(y)


def coordinates(value):
    x,y = value
    if not all(isfinite(v) and int(v) == v for v in (x,y)):
        raise ValueError('Cell coordinates must be integers')
    return int(x),int(y)


class TileSet(Object):
    def __init__(self,texture=None,*,tile_size=(16,16),margin=0,spacing=0,name=None,resources=None):
        super().__init__(name)
        self.name = name or 'Tiles'
        self._texture = None
        self._texture_path=None;self._resources=resources;self._transparent_color=None;self._image_paths={}
        self._tile_size = dimensions(tile_size)
        self._revision = 0
        self._margin = 0
        self._spacing = 0
        self._columns = 0
        self._tile_count = 0
        self._offset = Vector2(0,0)
        self._images = {}
        self._tiles = {}
        self._autotiles = {}
        self.properties = {}
        self.margin,self.spacing = margin,spacing
        self.texture = texture

    @property
    def texture(self):
        if self._texture is None and self._texture_path is not None:self._load_texture()
        return self._texture
    @texture.setter
    def texture(self,value):
        if isinstance(value,(str,Path)):
            self._texture_path=value
            value=self._resources.get_texture(value,color_key=self._transparent_color) if self._resources else None
        else:self._texture_path=None
        if value is not None and not isinstance(value,Texture): raise TypeError('Tileset texture must be a Texture, path or None')
        self._texture = value
        self._revision += 1
    @property
    def tile_size(self): return Vector2(*self._tile_size)
    @tile_size.setter
    def tile_size(self,value):
        self._tile_size = dimensions(value)
        self._revision += 1
    @property
    def margin(self): return self._margin
    @margin.setter
    def margin(self,value):
        if not isinstance(value,int) or value < 0: raise ValueError('Margin must be a nonnegative integer')
        self._margin = value
        self._revision += 1
    @property
    def spacing(self): return self._spacing
    @spacing.setter
    def spacing(self,value):
        if not isinstance(value,int) or value < 0: raise ValueError('Spacing must be a nonnegative integer')
        self._spacing = value
        self._revision += 1
    @property
    def columns(self):
        return self._columns or (max(0,(int(self.texture.size.x)-2*self.margin+self.spacing)//(self._tile_size[0]+self.spacing)) if self.texture else 0)
    @property
    def tile_count(self):
        if self._tile_count: return self._tile_count
        if not self.texture: return len(self._images)
        return self.columns*max(0,(int(self.texture.size.y)-2*self.margin+self.spacing)//(self._tile_size[1]+self.spacing))
    @property
    def offset(self): return Vector2(*self._offset)
    @offset.setter
    def offset(self,value):
        self._offset = Entity._vector(value)
        self._revision += 1
    @property
    def tiles(self): return MappingProxyType(self._tiles)

    @property
    def autotiles(self):return MappingProxyType(self._autotiles)

    def add_autotile(self,name,tiles,*,mode='sides',fallback=None):
        rule=AutoTile(name,tiles,mode=mode,fallback=fallback)
        for index in rule.tile_ids:self.validate(index)
        self._autotiles[name]=rule
        self._revision+=1
        return rule

    def set_solid(self,tile_ids,enabled=True):
        tile_ids=(tile_ids,) if isinstance(tile_ids,int) else tuple(tile_ids)
        for index in tile_ids:self.validate(index)
        for index in tile_ids:
            item=dict(self._tiles.get(index,{}))
            item['properties']=dict(item.get('properties',{}),solid=bool(enabled))
            self._tiles[index]=item
        self._revision+=1
        return self

    def add_animation(self,tile_id,frames,*,fps=8,durations=None):
        self.validate(tile_id)
        frames=tuple(frames)
        if not frames:raise ValueError('Tile animation needs frames')
        for index in frames:self.validate(index)
        if not isfinite(fps) or fps<=0:raise ValueError('Animation fps must be positive')
        durations=tuple(durations) if durations is not None else (1/fps,)*len(frames)
        if len(durations)!=len(frames) or any(not isfinite(value) or value<=0 for value in durations):
            raise ValueError('Each frame needs a positive duration in seconds')
        item=dict(self._tiles.get(tile_id,{}))
        item['animation']=tuple(zip(frames,durations))
        self._tiles[tile_id]=item
        self._revision+=1
        return self

    def _load_texture(self):
        if self._texture_path is not None:
            if self._resources:self._texture=self._resources.get_texture(self._texture_path,color_key=self._transparent_color)
            else:
                from ..core.resource import Resources
                self._texture=Resources().get_texture(self._texture_path,color_key=self._transparent_color)

    def _bind_resources(self,resources):
        self._resources=resources
        if self._texture_path is not None:self._texture=None;self._load_texture()
        for index,path in self._image_paths.items():self._images[index]=resources.get_texture(path)
        for index,tile in self._tiles.items():
            self.validate(index)
            for frame,seconds in tile.get('animation',()):self.validate(frame)

    @classmethod
    def from_data(cls,data,resources=None):
        result=cls(tile_size=data.tile_size,margin=data.margin,spacing=data.spacing,name=data.name,resources=resources)
        result._columns,result._tile_count=data.columns,data.tile_count
        result._transparent_color=data.transparent_color
        if data.image:result.texture=data.image
        result.offset=data.offset;result.properties=dict(data.properties);result._tiles=dict(data.tiles)
        for index,tile in data.tiles.items():
            if tile.get('image'):
                result._image_paths[index]=tile['image']
                if resources:result._images[index]=resources.get_texture(tile['image'])
        for tile in result._tiles.values():
            for frame,seconds in tile.get('animation',()):result.validate(frame)
        for wang in data.wangsets:
            entries=wang.get('wangtiles',[])
            edge=wang.get('type')=='edge' or (entries and all(not any(tile['wangid'][i] for i in (1,3,5,7)) for tile in entries))
            if not edge:continue
            colors=wang.get('colors',wang.get('wangcolors',[]))
            for number,color in enumerate(colors,1):
                masks={}
                for tile in entries:
                    ids=tile['wangid']
                    if len(ids)!=8:raise ValueError('Wang IDs must contain eight entries')
                    mask=sum(1<<i for i,slot in enumerate((0,2,4,6)) if ids[slot]==number)
                    if mask or not any(ids):masks.setdefault(mask,int(tile['tileid']))
                if masks:
                    name=wang.get('name','Terrain')+'/'+color.get('name',str(number))
                    rule=result.add_autotile(name,masks)
                    if len(colors)==1:result._autotiles[wang.get('name','Terrain')]=rule
        return result

    def validate(self,index):
        if not isinstance(index,int) or index<0:raise ValueError('Tile id must be a nonnegative integer')
        atlas=self._texture is not None or self._texture_path is not None
        if atlas:
            # Relative paths can be resolved when the map is attached to a Game.
            known=self._tile_count or self._texture is not None or self._resources is not None
            if known and index>=self.tile_count:raise ValueError(f'Tile id outside tileset {self.name!r}: {index}')
        elif index not in self._images and index not in self._image_paths and not self._tiles.get(index,{}).get('animation'):
            raise ValueError(f'Tile id outside tileset {self.name!r}: {index}')

    def animation_frame(self,index,time):
        frames = self._tiles.get(index,{}).get('animation',())
        if not frames: return index
        remaining = time%sum(duration for frame,duration in frames)
        for frame,duration in frames:
            if remaining < duration: return frame
            remaining -= duration
        return frames[-1][0]

    def region(self,index,time=0):
        index = self.animation_frame(index,time)
        self.validate(index)
        if index in self._image_paths and index not in self._images:
            self._images[index]=self._resources.get_texture(self._image_paths[index]) if self._resources else Texture.from_file(str(self._image_paths[index]))
        if index in self._images:
            texture = self._images[index]
            return texture,(0,0,int(texture.size.x),int(texture.size.y))
        width,height = self._tile_size
        x = self.margin+(index%self.columns)*(width+self.spacing)
        y = self.margin+(index//self.columns)*(height+self.spacing)
        if x+width > self.texture.size.x or y+height > self.texture.size.y: raise ValueError('Tileset atlas is smaller than its declared grid')
        return self.texture,(x,y,width,height)


def quad(texture,region,rect,cell,tint):
    """Invert Tiled's diagonal-then-horizontal/vertical transformation for UVs."""
    rx,ry,rw,rh = region
    x,y,w,h = rect
    if cell.transpose:
        y,w,h = y+h-w,h,w  # Preserve Tiled's bottom-left anchor for rectangular tiles.
    vertices = []
    for u,v in ((0,0),(1,0),(1,1),(0,0),(1,1),(0,1)):
        px,py = x+u*w,y+v*h
        if cell.flip_h: u = 1-u
        if cell.flip_v: v = 1-v
        if cell.transpose: u,v = v,u
        vertices.append(Vertex((px,py),tint,(rx+u*rw,ry+v*rh)))
    return vertices


class TileLayer(Entity):
    changed = Signal()
    def __init__(self,name=None):
        super().__init__(name)
        self._tile_map = None
        self._cells = {}
        self._terrains = {}
        self._collision_enabled = False
        self._chunks = {}
        self._meshes = {}
        self._mesh_revision = None
        self._mesh_padding = 0
        self._opacity = 1.0
        self._tint = (255,255,255,255)
        self._parallax = Vector2(1,1)
        self.kind = 'tilelayer'
        self.properties = {}
        self.objects = ()
        self._image = None
        self._image_texture = None
        self.repeat_x = self.repeat_y = False
        self.draw_order = 'topdown'

    @property
    def tile_map(self): return self._tile_map

    @property
    def material(self):
        return self._material if self._material is not None else (self.tile_map.material if self.tile_map else None)

    @material.setter
    def material(self, value):
        Entity.material.fset(self, value)
    @property
    def cells(self): return MappingProxyType(self._cells)
    @property
    def opacity(self): return self._opacity
    @opacity.setter
    def opacity(self,value):
        if not isfinite(value) or not 0 <= value <= 1: raise ValueError('Opacity must be in [0,1]')
        self._opacity = float(value)
        self._meshes.clear()
    @property
    def tint(self): return self._tint
    @tint.setter
    def tint(self,value):
        if isinstance(value,Color): value = (value.r,value.g,value.b,value.a)
        value = tuple(value)
        if len(value) == 3: value += (255,)
        if len(value) != 4 or any(not isinstance(v,int) or not 0 <= v <= 255 for v in value): raise ValueError('Tint needs RGB/RGBA byte values')
        self._tint = value
        self._meshes.clear()
    @property
    def parallax(self): return Vector2(*self._parallax)
    @parallax.setter
    def parallax(self,value): self._parallax = self._vector(value)
    @property
    def visible(self): return self._visible and (self.tile_map is None or self.tile_map.visible)
    @visible.setter
    def visible(self,value): self._visible = bool(value)
    @property
    def z_index(self): return self._z_index+(self.tile_map.z_index if self.tile_map else 0)
    @z_index.setter
    def z_index(self,value): self._z_index = int(value)
    @property
    def canvas(self): return self._canvas or (self.tile_map.canvas if self.tile_map else None)
    @canvas.setter
    def canvas(self,value): Entity.canvas.fset(self,value)
    @property
    def transform(self):
        result = Transform()
        if self.tile_map: result.combine(self.tile_map.transform)
        result.combine(Entity.transform.fget(self))
        return result

    def _chunk_key(self,point):
        w,h = self.tile_map._chunk if self.tile_map else (16,16)
        return point[0]//w,point[1]//h

    def _reindex(self):
        self._chunks.clear()
        self._meshes.clear()
        for point,cell in self._cells.items(): self._chunks.setdefault(self._chunk_key(point),{})[point] = cell

    def set_cell(self,point,tile_id,*,tileset=0,flip_h=False,flip_v=False,transpose=False):
        if self.kind != 'tilelayer': raise TypeError('Cells belong to tile layers')
        point = coordinates(point)
        if tile_id is None or isinstance(tile_id,int) and tile_id < 0:
            self.erase_cell(point)
            return
        if self.tile_map:
            tileset = self.tile_map._tileset_index(tileset)
            self.tile_map.tilesets[tileset].validate(tile_id)
        elif not isinstance(tile_id,int) or tile_id < 0: raise ValueError('Tile id must be a nonnegative integer')
        cell = TileCell(tile_id,tileset,bool(flip_h),bool(flip_v),bool(transpose))
        self._terrains.pop(point,None)
        self._store_cell(point,cell)
        self._refresh_terrains({point})

    def _store_cell(self,point,cell):
        if self._cells.get(point)==cell:return
        key=self._chunk_key(point)
        if cell is None:
            self._cells.pop(point,None)
            self._chunks.get(key,{}).pop(point,None)
            if not self._chunks.get(key):self._chunks.pop(key,None)
        else:
            self._cells[point]=cell
            self._chunks.setdefault(key,{})[point]=cell
        self._meshes.pop(key,None)
        self.changed.emit()
        if self.tile_map:
            self.tile_map._collision_dirty.add(self.name)
            self.tile_map.changed.emit()

    def erase_cell(self,point):
        point=coordinates(point)
        self._terrains.pop(point,None)
        self._store_cell(point,None)
        self._refresh_terrains({point})

    @property
    def terrains(self):return MappingProxyType(self._terrains)

    def set_terrain(self,point,terrain,*,tileset=0):
        if terrain is None:self.erase_cell(point)
        else:self.paint_terrain([point],terrain,tileset=tileset)

    def paint_terrain(self,points,terrain,*,tileset=0):
        if self.kind!='tilelayer' or self.tile_map is None:raise ValueError('Autotiles need a tile layer owned by a TileMap')
        tileset=self.tile_map._tileset_index(tileset)
        rule=self.tile_map.tilesets[tileset].autotiles[terrain]
        points={coordinates(point) for point in points}
        for point in points:self._terrains[point]=(tileset,rule.name)
        self._refresh_terrains(points,infer=(tileset,rule.name))

    def update_terrain(self,terrain=None,*,tileset=0):
        if terrain is None:self._refresh_terrains(set(self._terrains))
        else:
            if self.tile_map is None:raise ValueError('Terrain needs a TileMap')
            index=self.tile_map._tileset_index(tileset)
            rule=self.tile_map.tilesets[index].autotiles[terrain]
            points={point for point,cell in self.cells.items() if cell.tileset==index and cell.tile_id in rule.tile_ids}
            self.paint_terrain(points,terrain,tileset=index)

    def _refresh_terrains(self,points,infer=None):
        if self.tile_map is None:return
        affected={(x+dx,y+dy) for x,y in points for dx in (-1,0,1) for dy in (-1,0,1)}
        if infer is not None:
            index,name=infer;rule=self.tile_map.tilesets[index].autotiles[name]
            for point in affected:
                cell=self._cells.get(point)
                if point not in self._terrains and cell is not None and cell.tileset==index and cell.tile_id in rule.tile_ids:
                    self._terrains[point]=infer
        for point in affected:
            label=self._terrains.get(point)
            if label is None:continue
            index,name=label;rule=self.tile_map.tilesets[index].autotiles[name]
            x,y=point
            def connected(dx,dy):
                other=(x+dx,y+dy)
                if other in self._terrains:return self._terrains[other]==label
                cell=self._cells.get(other)
                return cell is not None and cell.tileset==index and cell.tile_id in rule.tile_ids
            self._store_cell(point,TileCell(rule.choose(rule.mask(connected)),index))

    @property
    def collision_enabled(self):return self._collision_enabled
    @collision_enabled.setter
    def collision_enabled(self,value):
        self._collision_enabled=bool(value)
        if self.tile_map:self.tile_map._collision_dirty.add(self.name)

    def get_cell(self,point): return self._cells.get(coordinates(point))
    def fill(self,rect,tile_id,**options):
        x,y,w,h = rect
        x,y = coordinates((x,y))
        w,h = coordinates((w,h))
        if w < 0 or h < 0: raise ValueError('Fill dimensions cannot be negative')
        for row in range(y,y+h):
            for column in range(x,x+w): self.set_cell((column,row),tile_id,**options)
    def clear(self):
        self._terrains.clear()
        if self.tile_map:self.tile_map._collision_dirty.add(self.name)
        self._cells.clear()
        self._chunks.clear()
        self._meshes.clear()
        self.changed.emit()
        if self.tile_map: self.tile_map.changed.emit()
    @property
    def used_rect(self):
        if not self._cells: return (0,0,0,0)
        xs,ys = zip(*self._cells)
        return min(xs),min(ys),max(xs)-min(xs)+1,max(ys)-min(ys)+1

    def _build_chunk(self,key):
        owner = self.tile_map
        tw,th = owner._tile_size
        reverse_x = owner.render_order.startswith('left')
        rows = {}
        color = Color(*self.tint[:3],round(self.tint[3]*self.opacity))
        points = self._chunks.get(key,{})
        frames = {}
        for (x,y),cell in sorted(points.items(),key=lambda item:(item[0][1],-item[0][0] if reverse_x else item[0][0])):
            tileset = owner.tilesets[cell.tileset]
            texture,region = tileset.region(cell.tile_id,owner._time)
            if tileset.tiles.get(cell.tile_id, {}).get('animation'):
                frames[cell.tileset, cell.tile_id] = tileset.animation_frame(cell.tile_id, owner._time)
            offset = tileset.offset
            rect = (x*tw+offset.x,y*th+th-region[3]+offset.y,region[2],region[3])
            runs = rows.setdefault(y,[])
            if not runs or runs[-1][0] is not texture: runs.append((texture,VertexArray(PrimitiveType.TRIANGLES)))
            for vertex in quad(texture,region,rect,cell,color): runs[-1][1].append(vertex)
        self._meshes[key] = (rows, frames)
        return rows

    def _view_bounds(self,target,transform):
        inverse = transform.inverse
        w,h = target.size
        corners = [inverse.transform_point(target.map_pixel_to_coords(point)) for point in ((0,0),(w,0),(0,h),(w,h))]
        return min(p.x for p in corners),min(p.y for p in corners),max(p.x for p in corners),max(p.y for p in corners)

    def render(self,target,states):
        owner = self.tile_map
        if owner is None or not self.visible or self.opacity <= 0: return
        transform = Transform()
        shift = target.view.center-Vector2(*owner.parallax_origin)
        transform.translate((shift.x*(1-self.parallax.x),shift.y*(1-self.parallax.y)))
        transform.combine(states.transform)
        if self.kind == 'imagelayer':
            self._render_image(target,transform,states.shader)
            return
        if self.kind == 'objectgroup':
            self._render_objects(target,transform,states.shader)
            return
        revision = (owner.render_order, tuple(owner._tile_size),
                    tuple((ts, ts._revision) for ts in owner.tilesets))
        if revision != self._mesh_revision:
            self._meshes.clear()
            self._mesh_revision = revision
            self._mesh_padding = max([max(owner._tile_size)] + [
                max(*ts._tile_size, *(max(texture.size) for texture in ts._images.values()))
                + max(abs(ts.offset.x), abs(ts.offset.y)) for ts in owner.tilesets])
        left,top,right,bottom = self._view_bounds(target,transform)
        tw,th = owner._tile_size
        cw,ch = owner._chunk
        pad = self._mesh_padding
        x0, x1 = floor((left-pad)/tw), floor((right+pad)/tw)
        y0, y1 = floor((top-pad)/th), floor((bottom+pad)/th)
        reverse_x = owner.render_order.startswith('left')
        reverse_y = owner.render_order.endswith('up')
        rows_in_view = {}
        # For a sparse map or an extremely wide view, visit occupied chunks only.
        columns, rows = range(x0//cw, x1//cw+1), range(y0//ch, y1//ch+1)
        if len(columns)*len(rows) > len(self._chunks):
            keys = (key for key in self._chunks if key[0] in columns and key[1] in rows)
        else:
            keys = ((cx,cy) for cy in rows for cx in columns if (cx,cy) in self._chunks)
        tilesets = owner.tilesets
        frame_cache = {}
        debug = self.game.debug if self.game and self.game.debug.visible else None
        for key in sorted(keys, key=lambda key: -key[0] if reverse_x else key[0]):
            mesh = self._meshes.get(key)
            if mesh is not None:
                for tile, previous in mesh[1].items():
                    if tile not in frame_cache:
                        index, tile_id = tile
                        frame_cache[tile] = tilesets[index].animation_frame(tile_id, owner._time)
                    if previous != frame_cache[tile]:
                        mesh = None
                        break
            mesh_rows = self._build_chunk(key) if mesh is None else mesh[0]
            if debug is not None and any(y0 <= y <= y1 for y in mesh_rows):
                debug._tile_chunk(self.canvas or self.game.world, transform,
                                  (key[0]*cw*tw, key[1]*ch*th, cw*tw, ch*th))
            for y, runs in mesh_rows.items():
                if y0 <= y <= y1:
                    rows_in_view.setdefault(y, []).extend(runs)
        for y in sorted(rows_in_view, reverse=reverse_y):
            for texture, mesh in rows_in_view[y]:
                target.draw(mesh, RenderStates(transform=transform, texture=texture, shader=states.shader))

    def _render_image(self,target,transform,shader):
        if self._image is None: return
        if self._image_texture is None: self._image_texture = self.tile_map._resources.get_texture(self._image) if self.tile_map._resources else Texture.from_file(str(self._image))
        texture = self._image_texture
        w,h = texture.size
        left,top,right,bottom = self._view_bounds(target,transform)
        xs = range(floor(left/w),ceil(right/w)) if self.repeat_x else (0,)
        ys = range(floor(top/h),ceil(bottom/h)) if self.repeat_y else (0,)
        tint = Color(*self.tint[:3],round(self.tint[3]*self.opacity))
        mesh = VertexArray(PrimitiveType.TRIANGLES)
        for y in ys:
            for x in xs:
                for vertex in quad(texture,(0,0,w,h),(x*w,y*h,w,h),TileCell(),tint): mesh.append(vertex)
        target.draw(mesh,RenderStates(transform=transform,texture=texture,shader=shader))

    def _render_objects(self,target,transform,shader):
        objects = sorted(self.objects,key=lambda obj:obj.position[1]) if self.draw_order == 'topdown' else self.objects
        tint = Color(*self.tint[:3],round(self.tint[3]*self.opacity))
        for obj in objects:
            if obj.tile is None or not obj.visible: continue
            tileset = self.tile_map.tilesets[obj.tile.tileset]
            texture,region = tileset.region(obj.tile.tile_id,self.tile_map._time)
            w,h = obj.size
            w,h = w or region[2],h or region[3]
            local = Transform()
            local.combine(transform)
            local.translate((obj.position[0]-self.position.x,obj.position[1]-self.position.y))
            local.rotate(obj.rotation)
            mesh = VertexArray(PrimitiveType.TRIANGLES)
            offset_x,offset_y = tileset.offset.x*w/region[2],tileset.offset.y*h/region[3]
            for vertex in quad(texture,region,(offset_x,-h+offset_y,w,h),obj.tile,tint): mesh.append(vertex)
            target.draw(mesh,RenderStates(transform=local,texture=texture,shader=shader))


class TileMap(Entity):
    changed = Signal()
    def __init__(self,data=None,*,tile_set=None,tile_size=None,name=None,collisions=False,resources=None):
        super().__init__(name)
        self._resources=resources;self._resource_override=resources
        self._chunk = (16,16)
        self._tile_size = dimensions(tile_size or (16,16))
        self._tilesets = []
        self._layers = {}
        self._collision_dirty=set()
        self._collision_manager=None
        self._collisions_default=False
        self._map_size = (0,0)
        self._time = 0.0
        self._overhang = max(self._tile_size)
        self.properties = {}
        self.render_order = 'right-down'
        self.parallax_origin = (0,0)
        self.background_color = None
        self.infinite = False
        if tile_set is not None:
            self.add_tileset(tile_set)
            if tile_size is None: self._tile_size = tile_set._tile_size
        if data is not None and tile_set is not None: raise ValueError('Supply either map data or a manual tileset')
        if isinstance(data,(str,Path)): data = resources.get_map(data) if resources else TiledParser.parse(data)
        if data is not None: self._load(data)
        if collisions:self.enable_collisions()

    @classmethod
    def from_tiled(cls,path,*,collisions=False,resources=None):
        return cls(path,collisions=collisions,resources=resources)
    @property
    def tile_size(self): return Vector2(*self._tile_size)
    @tile_size.setter
    def tile_size(self,value):
        self._tile_size = dimensions(value)
        for layer in self._layers.values(): layer._meshes.clear()
    @property
    def map_size(self): return Vector2(*self._map_size)
    @property
    def pixel_size(self): return Vector2(self._map_size[0]*self._tile_size[0],self._map_size[1]*self._tile_size[1])
    @property
    def chunk(self): return Vector2(*self._chunk)
    @chunk.setter
    def chunk(self,value):
        self._chunk = dimensions(value)
        for layer in self._layers.values(): layer._reindex()
    @property
    def layers(self): return MappingProxyType(self._layers)
    @property
    def tilesets(self): return tuple(self._tilesets)
    @property
    def tile_set(self): return self._tilesets[0] if self._tilesets else None
    @tile_set.setter
    def tile_set(self,value):
        if value is None:
            if any(layer.cells for layer in self.layers.values()): raise ValueError('Clear cells before removing their tilesets')
            self._tilesets.clear()
        else:
            if not isinstance(value,TileSet): raise TypeError('Expected a TileSet')
            for layer in self.layers.values():
                for cell in layer.cells.values():
                    if cell.tileset == 0: value.validate(cell.tile_id)
            if self._tilesets: self._tilesets[0] = value
            else:
                self.add_tileset(value)
                self.tile_size = value.tile_size
        for layer in self.layers.values(): layer._meshes.clear()
        self.changed.emit()
    @property
    def objects(self): return tuple(obj for layer in self._layers.values() for obj in layer.objects)

    @property
    def colliders(self):return self._collision_manager.bodies if self._collision_manager else ()

    def enable_collisions(self,layers=None,*,collision_layer=1,collision_mask=0xffffffff):
        self._collisions_default=layers is None
        if layers is not None:layers={layers} if isinstance(layers,str) else set(layers)
        if layers is not None and layers-set(self.layers):raise ValueError('Unknown collision layer name')
        for name,layer in self.layers.items():
            marked = layer.properties.get('collision_enabled', layer.properties.get('collision', layer.properties.get('one_way', False)))
            selected = (layer.kind == 'tilelayer' or marked) if layers is None else name in layers
            layer.collision_enabled=bool(selected and layer.properties.get('collision_enabled',layer.properties.get('collision',True)))
            layer.properties.setdefault('collision_layer',collision_layer)
            layer.properties.setdefault('collision_mask',collision_mask)
        self._sync_collisions()
        return self

    def disable_collisions(self):
        self._collisions_default=False
        for layer in self.layers.values():layer.collision_enabled=False
        self._sync_collisions()

    def _sync_collisions(self):
        if self._collision_manager is None and any(layer.collision_enabled for layer in self.layers.values()):
            from .tilecollision import TileCollisions
            self._collision_manager=TileCollisions(self)
        if self._collision_manager is not None:self._collision_manager.sync()

    def set_terrain(self,layer,point,terrain,**options):self.layers[layer].set_terrain(point,terrain,**options)
    def paint_terrain(self,layer,points,terrain,**options):self.layers[layer].paint_terrain(points,terrain,**options)

    def _tileset_index(self,value):
        if isinstance(value,str):
            matches = [i for i,ts in enumerate(self.tilesets) if ts.name == value]
            if len(matches) != 1: raise ValueError('Tileset name must identify exactly one tileset')
            return matches[0]
        if not isinstance(value,int) or not 0 <= value < len(self.tilesets): raise ValueError('Unknown tileset index')
        return value

    def add_tileset(self,tileset):
        if not isinstance(tileset,TileSet): raise TypeError('Expected a TileSet')
        self._tilesets.append(tileset)
        if self._resources is not None:tileset._bind_resources(self._resources)
        self._overhang = max(self._overhang,*tileset._tile_size,abs(tileset.offset.x),abs(tileset.offset.y),
                             *(max(texture.size) for texture in tileset._images.values()))
        return len(self._tilesets)-1

    def add_layer(self,name,*,z_index=None):
        if not isinstance(name,str) or not name or name in self._layers: raise ValueError('Layer names must be nonempty and unique')
        layer = TileLayer(name)
        layer._tile_map = self
        layer.z_index = len(self._layers) if z_index is None else z_index
        self._layers[name] = layer
        layer.collision_enabled=self._collisions_default
        if self.game: self._register(layer)
        self.changed.emit()
        return layer

    def remove_layer(self,name):
        layer = self._layers.pop(name)
        if layer.game is not None: layer.game.remove(layer)
        elif layer._pending_game is not None: layer._pending_game.remove(layer)
        layer._tile_map = None
        self.changed.emit()

    def set_cell(self,layer,point,tile_id,**options): self.layers[layer].set_cell(point,tile_id,**options)
    def get_cell(self,layer,point): return self.layers[layer].get_cell(point)
    def erase_cell(self,layer,point): self.layers[layer].erase_cell(point)

    def map_to_local(self,point):
        x,y = coordinates(point)
        return Vector2((x+.5)*self._tile_size[0],(y+.5)*self._tile_size[1])
    def local_to_map(self,point):
        x,y = Entity._vector(point)
        return floor(x/self._tile_size[0]),floor(y/self._tile_size[1])
    def map_to_world(self,point): return self.transform.transform_point(self.map_to_local(point))
    def world_to_map(self,point): return self.local_to_map(self.transform.inverse.transform_point(Entity._vector(point)))

    def find_path(self, start, goal, *, diagonal=False, blocked_layers=None, bounds=None, blocked=(),
                  radius=None, agent=None, avoid_bodies=None, ignore=()):
        """Return a path of cells including both endpoints, or [] if unreachable.

        Authored solid tiles and collision objects are obstacles by default.
        Supply blocked_layers to use only those layers (all occupied cells block).
        bounds is an optional (x, y, width, height) rectangle in cells.
        radius is in world units. An agent supplies its radius and collision filters.
        """
        from .tilenavigation import find_path

        if bounds is not None:
            x, y, width, height = bounds
            bounds = (*coordinates((x, y)), *dimensions((width, height)))
        if agent is not None and not getattr(agent, '_is_physics_body', False):
            raise TypeError('Navigation agent must be a physics body')
        if radius is None:
            radius = agent._navigation_radius() if agent is not None else 0
        if not isfinite(radius) or radius < 0:
            raise ValueError('Navigation radius must be nonnegative and finite')
        check_bodies = agent is not None if avoid_bodies is None else bool(avoid_bodies)
        if check_bodies and agent is not None and agent.game is not self.game:
            raise ValueError('The agent and tile map must belong to the same Game')
        physics = self.game._physics if check_bodies and self.game is not None else None
        profile = self.game.debug._measure('navigation') if self.game is not None else nullcontext()
        with profile:
            return find_path(self, coordinates(start), coordinates(goal), diagonal=diagonal,
                             blocked_layers=blocked_layers, bounds=bounds,
                             blocked=(coordinates(point) for point in blocked), radius=radius,
                             physics=physics, agent=agent, ignored=tuple(ignore))

    def find_world_path(self, start, goal, **options):
        """Return the world-space center of each cell on the path."""
        path = self.find_path(self.world_to_map(start), self.world_to_map(goal), **options)
        return [self.map_to_world(cell) for cell in path]

    @property
    def bounds(self):
        if not self.infinite and self._map_size != (0,0): return (0,0,*self.pixel_size)
        rects = []
        tw,th = self._tile_size
        for layer in self.layers.values():
            if not layer.cells: continue
            x,y,w,h = layer.used_rect
            rects.append((x*tw+layer.position.x,y*th+layer.position.y,w*tw,h*th))
        if not rects: return (0,0,0,0)
        left,top = min(r[0] for r in rects),min(r[1] for r in rects)
        return left,top,max(r[0]+r[2] for r in rects)-left,max(r[1]+r[3] for r in rects)-top
    @property
    def world_bounds(self):
        x,y,w,h = self.bounds
        rect = self.transform.transform_rectangle(Rect((x,y),(w,h)))
        return (*rect.position,*rect.size)

    def _load(self,data):
        if not isinstance(data,MapData): raise TypeError('Expected MapData, a Tiled path or None')
        self.name = data.name or self.name
        self._tile_size = dimensions(data.tile_size)
        self._map_size = data.size
        self.properties = dict(data.properties)
        self.infinite,self.render_order = data.infinite,data.render_order
        self.parallax_origin,self.background_color = data.parallax_origin,data.background_color
        for ts in data.tilesets: self.add_tileset(TileSet.from_data(ts,self._resources))
        for index,item in enumerate(data.layers):
            layer = self.add_layer(item.name,z_index=index)
            layer.kind,layer.position = item.kind,item.offset
            layer.parallax,layer.opacity,layer.visible,layer.tint = item.parallax,item.opacity,item.visible,item.tint
            layer.properties,layer.objects = dict(item.properties),item.objects
            layer.collision_enabled=bool(layer.properties.get('collision_enabled',layer.properties.get('collision',layer.properties.get('one_way',False))))
            layer._image = item.image
            layer.repeat_x,layer.repeat_y,layer.draw_order = item.repeat_x,item.repeat_y,item.draw_order
            layer._cells = dict(item.cells)
            layer._reindex()

    def _bind_resources(self,resources):
        self._resources=self._resource_override or resources
        for tileset in self.tilesets:tileset._bind_resources(self._resources)
        for layer in self.layers.values():
            for cell in layer.cells.values():self.tilesets[cell.tileset].validate(cell.tile_id)

    def _register(self,layer):
        if layer.game is not None or layer._pending_game is not None: raise ValueError('Tile layers cannot belong to two games')
        self.game.add(layer, persistent=self.game._objects[self], scope=self.scope)
    def on_added(self):
        for layer in self.layers.values(): self._register(layer)
        self._sync_collisions()
    def on_removed(self):
        if self._collision_manager is not None:self._collision_manager.clear()
        if self.game.closed: return  # Game.close already removes every registered layer.
        for layer in self.layers.values():
            if layer.game is self.game or layer._pending_game is self.game: self.game.remove(layer)

    def _advance(self,dt):
        self._time += dt


__all__ = ['TiledParser','MapData','MapObject','TileCell','TileLayer','TileSet','TileMap']
