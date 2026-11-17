from typing import List, Tuple

from sfml.system import Vector2

from ..core import Node

#class NavigationAgent(): pass

class Path2D(Node):
                    # position, out
    _curve:List[Tuple[Vector2, Vector2]] #Curve
    _bake_interval:float = 5.0


class PathFollow(Node):
    _progress:float = 0.0 #px
    _progress_ratio:float = 0.0
    _h_offset:float = 0.0
    _v_offset:float = 0.0
    _rotates:bool = True
    _cubic_interp:bool = True
    _loop:bool = True