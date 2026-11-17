from sfml.system import Vector2
from ..core import Node

class Parallax(Node):
    _scroll_scale:Vector2 = Vector2(1.0,1.0)
    _scroll_offset:Vector2 = Vector2(1.0, 1.0)

    _repeat_size:Vector2 = Vector2(0.0, 0.0)
    _autoscroll: Vector2 = Vector2(0.0, 0.0)#px/sn
    _repeat_times:int = 1

    _limit_begin:Vector2 = Vector2(-10000000.0, -10000000.0)
    _limit_end: Vector2 = Vector2(10000000.0, 10000000.0)

    _follow_viewport:bool = True
    _ignore_camera_scroll:bool = True
    _screen_offset:Vector2 = Vector2(0.0, 0.0) #px