"""4-side and 47-pattern blob autotiling. Bits: N E S W NE SE SW NW."""
from types import MappingProxyType

NEIGHBORS=((0,-1,1),(1,0,2),(0,1,4),(-1,0,8),
           (1,-1,16),(1,1,32),(-1,1,64),(-1,-1,128))


class AutoTile:
    def __init__(self,name,tiles,*,mode='sides',fallback=None):
        if not isinstance(name,str) or not name:raise ValueError('Autotile name must be nonempty')
        if mode not in ('sides','blob'):raise ValueError('Autotile mode must be sides or blob')
        values=dict(tiles) if hasattr(tiles,'items') else dict(enumerate(tiles))
        if not values:raise ValueError('Autotile needs at least one mask/tile pair')
        maximum=15 if mode=='sides' else 255
        if any(not isinstance(mask,int) or not 0<=mask<=maximum or not isinstance(tile,int) or tile<0 for mask,tile in values.items()):
            raise ValueError('Autotile masks and tile IDs must be valid nonnegative integers')
        self.name,self.mode=name,mode
        self._tiles=MappingProxyType(values)
        self.fallback=values.get(0,next(iter(values.values()))) if fallback is None else fallback
    @property
    def tiles(self):return self._tiles
    @property
    def tile_ids(self):return frozenset(self.tiles.values())|{self.fallback}
    def mask(self,connected):
        value=sum(bit for dx,dy,bit in NEIGHBORS if connected(dx,dy))
        if self.mode=='sides':return value&15
        for diagonal,adjacent in ((16,3),(32,6),(64,12),(128,9)):
            if value&adjacent!=adjacent:value&=~diagonal
        return value
    def choose(self,mask):return self.tiles.get(mask,self.fallback)
