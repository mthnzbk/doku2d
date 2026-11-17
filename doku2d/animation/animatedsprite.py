from typing import List

from sfml.system import Vector2

from ..core import Signal, Node

class AnimatedSprite(Node):
    animation_changed = Signal()
    animation_finished = Signal()
    animation_looped = Signal()
    frame_changed = Signal()
    sprite_frames_changed = Signal()

    _sprite_frames:int#List[Node] SpriteFrames dict olabilir :S Resource nesnesi
    _animation:str = "default"
    _frame:int = 0
    _speed_scale:float = 1.0

    #offset
    _centered:bool = True
    _offset:Vector2
    _flip_h:bool = False
    _flip_v:bool = False