from typing import Any, List
from sfml.graphics import Sprite as _Sprite
from sfml.system import Vector2
from ..core import Signal, Node


class Sprite(Node, _Sprite):
    frame_changed = Signal()
    texture_changed = Signal()


    _texture:Any
    _offset:Vector2
    _centered:bool = True
    flip_h:bool = False
    flip_v:bool = False

    #animation
    _hframes:int = 1
    _vframes:int = 1
    _frame:int = 0
    _frame_coords:Vector2

    _region:bool = False
    _region_rect:List[float] = [0.0, 0.0, 0.0, 0.0]
