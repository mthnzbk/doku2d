from typing import Any
from sfml.system import Vector2


class Object: pass


class Node(Object):

    _position:Vector2
    _global_position:Vector2
    _rotation:float = 0.0 #derece
    _scale:Vector2 = Vector2(1.0, 1.0)
    _visible:bool = True
    _material:Any #??

    @property
    def position(self): return self._position

    @position.setter
    def position(self, value:Vector2): self._position = value

    @property
    def global_position(self): return self._global_position

    @property
    def rotation(self): return self._rotation

    @rotation.setter
    def rotation(self, value:float): self._rotation = value

    @property
    def scale(self): return self._scale

    @property
    def visible(self): return self._visible

    @visible.setter
    def visible(self, value:bool): self._visible = value

    @scale.setter
    def scale(self, value:Vector2): self._scale = value

    @global_position.setter
    def global_position(self, value:Vector2): self._global_position = value

    def update(self, dt): pass

    def add_child(self, child): pass
    def remove_child(self, child): pass
    def children(self): pass

    def parent(self): pass

