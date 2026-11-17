from typing import List
from sfml.system import Vector2
from ..core import Node

class Camera(Node):
    _offset:Vector2
    _anchor_mode:str #drag center, fixed top left
    _enabled:bool =True
    _zoom:Vector2 = Vector2(1.0, 1.0)
    _limit_enable:bool = True
    _limit:List[int] = [
        -10000000,
        -10000000,
        10000000,
        10000000,
    ]
    _smoothed:bool = False
    _position_smoothing:bool = False
    _rotation_smoothing:bool = False