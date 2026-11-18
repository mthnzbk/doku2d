"""Build static physics from authored tile/object geometry; never from animation frames."""
from math import cos,sin,pi,radians
from sfml.system import Vector2
from ..physics import StaticBody,Polygon,Segment


def properties(raw):
    value=raw.get('properties',{})
    return value if isinstance(value,dict) else {item['name']:item.get('value') for item in value}


def geometry(raw):
    x,y=float(raw.get('x',0)),float(raw.get('y',0))
    w,h=float(raw.get('width',0)),float(raw.get('height',0))
    if raw.get('point') or 'text' in raw:return []
    kind='polygon'
    if 'polygon' in raw or 'polyline' in raw:
        kind='segment' if 'polyline' in raw else 'polygon'
        points=[(p['x'],p['y']) for p in raw.get('polyline',raw.get('polygon',[]))]
    elif raw.get('ellipse'):
        if w<=0 or h<=0:return []
        points=[(w/2+cos(i*2*pi/24)*w/2,h/2+sin(i*2*pi/24)*h/2) for i in range(24)]
    else:
        if w<=0 or h<=0:return []
        points=[(0,0),(w,0),(w,h),(0,h)]
    angle=radians(float(raw.get('rotation',0)));c,s=cos(angle),sin(angle)
    points=[(x+px*c-py*s,y+px*s+py*c) for px,py in points]
    if kind=='segment':return [('segment',(a,b)) for a,b in zip(points,points[1:]) if a!=b]
    return [('polygon',points)]


def convex_parts(points):
    points=[tuple(p) for p in points]
    if len(points)>1 and points[0]==points[-1]:points.pop()
    try:Polygon(points);return [points]
    except ValueError:pass
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
    if abs(area)<1e-8:raise ValueError('Collision polygon has zero area')
    sign=1 if area>0 else -1
    remaining=list(points);parts=[]
    while len(remaining)>3:
        for index,b in enumerate(remaining):
            a,c=remaining[index-1],remaining[(index+1)%len(remaining)]
            if cross(a,b,c)*sign<=1e-8:continue
            def inside(p):return all(cross(v1,v2,p)*sign>=-1e-8 for v1,v2 in ((a,b),(b,c),(c,a)))
            if any(inside(p) for p in remaining if p not in (a,b,c)):continue
            parts.append([a,b,c]);remaining.pop(index);break
        else:raise ValueError('Collision polygon must be simple (no crossing edges)')
    parts.append(remaining)
    return parts


class TileCollisions:
    def __init__(self,tilemap):
        self.tilemap=tilemap
        self._generated={}
        self._keys={}
    @property
    def bodies(self):return tuple(body for bodies in self._generated.values() for body in bodies)

    def _remove(self,name):
        for body in self._generated.pop(name,()):
            game=body.game or body._pending_game
            if game is not None and not game.closed:game.remove(body)
        self._keys.pop(name,None)

    def clear(self):
        for name in tuple(self._generated):self._remove(name)

    def _settings(self,layer,*sources):
        result={'collision_layer':1,'collision_mask':0xffffffff,'friction':.7,'elasticity':0}
        for source in (layer.properties,*sources):
            for key in result:
                if key in source:result[key]=source[key]
        return result

    def _body(self,layer,kind,points,settings,cell=None):
        world=[tuple(layer.transform.transform_point(point)) for point in points]
        groups=convex_parts(world) if kind=='polygon' else [world]
        result=[]
        for vertices in groups:
            center=Vector2(sum(p[0] for p in vertices)/len(vertices),sum(p[1] for p in vertices)/len(vertices))
            local=[(x-center.x,y-center.y) for x,y in vertices]
            shape=Polygon(local) if kind=='polygon' else Segment(local[0],local[1],.25)
            body=StaticBody(name=f'{layer.name} collision',position=center,shape=shape)
            for key,value in settings.items():setattr(body,key,value)
            body.visible=False
            body.tile_layer=layer.name
            body.tile_cell=cell
            result.append(body)
        return result

    def _tile_object(self,layer,obj):
        cell=obj.tile;ts=self.tilemap.tilesets[cell.tileset]
        tile=ts.tiles.get(cell.tile_id,{})
        prop=properties(tile)
        if prop.get('collision_enabled',True) is False:return []
        _,region=ts.region(cell.tile_id,0)
        gw,gh=region[2:];w,h=obj.size
        w,h=w or gw,h or gh
        sx,sy=w/gw,h/gh
        outw,outh=(h,w) if cell.transpose else (w,h)
        angle=radians(obj.rotation);c,s=cos(angle),sin(angle)
        def transform(point):
            x,y=point[0]*sx,point[1]*sy
            if cell.transpose:x,y=y,x
            if cell.flip_h:x=outw-x
            if cell.flip_v:y=outh-y
            x+=ts.offset.x*sx;y+=ts.offset.y*sy-outh
            return (obj.position[0]-layer.position.x+x*c-y*s,
                    obj.position[1]-layer.position.y+x*s+y*c)
        objects=tile.get('objectgroup',{}).get('objects',[])
        if not objects:objects=[{'x':0,'y':0,'width':gw,'height':gh}]
        result=[]
        for child in objects:
            childprop=properties(child)
            if childprop.get('collision_enabled',True) is False:continue
            for kind,points in geometry(child):
                result+=self._body(layer,kind,[transform(p) for p in points],self._settings(layer,prop,obj.properties,childprop))
        return result

    def _build(self,layer):
        if tuple(layer.parallax)!=(1,1):raise ValueError('Physics tile layers must have parallax=(1,1)')
        owner=self.tilemap;result=[]
        tw,th=owner._tile_size
        solid_rows={}
        for (x,y),cell in layer.cells.items():
            ts=owner.tilesets[cell.tileset]
            tile=ts.tiles.get(cell.tile_id,{})
            prop=properties(tile)
            if prop.get('collision_enabled',True) is False:continue
            objects=tile.get('objectgroup',{}).get('objects',[])
            solid=layer.properties.get('collision_mode')=='solid' or prop.get('solid',False)
            settings=self._settings(layer,prop)
            if solid and not objects:
                solid_rows.setdefault((y,tuple(settings.items())),[]).append(x)
                continue
            _,region=ts.region(cell.tile_id,0)
            gw,gh=region[2:]
            outw,outh=(gh,gw) if cell.transpose else (gw,gh)
            def transform(point):
                px,py=point
                if cell.transpose:px,py=py,px
                if cell.flip_h:px=outw-px
                if cell.flip_v:py=outh-py
                return x*tw+ts.offset.x+px,y*th+th-outh+ts.offset.y+py
            for obj in objects:
                objprop=properties(obj)
                if objprop.get('collision_enabled',True) is False:continue
                for kind,points in geometry(obj):
                    result+=self._body(layer,kind,[transform(p) for p in points],self._settings(layer,prop,objprop),(x,y))
        # Adjacent full cells share one floor surface, avoiding tile-edge seams.
        for (y,settings),xs in solid_rows.items():
            xs=sorted(set(xs));start=last=xs[0]
            for x in xs[1:]+[None]:
                if x is not None and x==last+1:last=x;continue
                left,right=start*tw,(last+1)*tw
                result+=self._body(layer,'polygon',[(left,y*th),(right,y*th),(right,(y+1)*th),(left,(y+1)*th)],dict(settings),(start,y))
                start=last=x
        for obj in layer.objects:
            if obj.properties.get('collision_enabled',True) is False:continue
            if obj.tile is not None:
                result+=self._tile_object(layer,obj)
                continue
            raw={'x':obj.position[0]-layer.position.x,'y':obj.position[1]-layer.position.y,
                 'width':obj.size[0],'height':obj.size[1],'rotation':obj.rotation}
            if obj.shape in ('polygon','polyline'):raw[obj.shape]=[{'x':x,'y':y} for x,y in obj.points]
            elif obj.shape in ('point','ellipse','text'):raw[obj.shape]=True
            for kind,points in geometry(raw):result+=self._body(layer,kind,points,self._settings(layer,obj.properties))
        return result

    def sync(self):
        owner=self.tilemap
        if owner.game is None or owner.game.closed:return
        for name in set(self._generated)-set(owner.layers):self._remove(name)
        for name,layer in owner.layers.items():
            transform=layer.transform
            affine=tuple(tuple(transform.transform_point(point)) for point in ((0,0),(1,0),(0,1)))
            key=(affine,layer.collision_enabled,tuple(layer.parallax),repr(layer.properties),
                 tuple(ts._revision for ts in owner.tilesets),tuple(owner.tile_size))
            if key==self._keys.get(name) and name not in owner._collision_dirty:continue
            bodies=self._build(layer) if layer.collision_enabled else []
            self._remove(name)
            self._generated[name]=bodies
            self._keys[name]=key
            for body in bodies:owner.game.add(body, persistent=owner.game._objects[owner], scope=owner.scope)
        owner._collision_dirty.clear()
