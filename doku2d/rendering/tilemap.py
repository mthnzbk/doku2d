from sfml.system import Vector2

from ..core import Node, Signal

class TiledParser(Node): pass


class TileLayer(Node): pass


class TileMap(Node):
    changed = Signal()

    _chunk:Vector2 = Vector2(16, 16)

    #bağzı şeyler...

    @property
    def chunk(self) -> Vector2: return self._chunk

    @chunk.setter
    def chunk(self, value: Vector2): self._chunk = value




class TileSet(Node): #resource
    _tile_shape:str = 'square' #isometric, hexagon
    _tile_size:Vector2 = Vector2(16, 16)
    #square hariç
    _tile_layout:str #stacked, stacked offset, stairs right, stairs down, diamond right-down
    _tile_offset_axis:str #horizontal-vertical offset

    #physics layer
    #terrain sets
    ##
    #navigation layers
    #custom data layers


