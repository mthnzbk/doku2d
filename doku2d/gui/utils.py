from typing import Any
from sfml.system import Vector2
from ..core import Signal
from .control import Control


class TouchScreenButton(Control):
    pressed = Signal()
    released = Signal()

    _texture_normal:Any
    _texture_pressed:Any
    _bitmask:Any
    _shape:Any
    _shape_centered:bool = True
    _shape_visible:bool = True
    _passby_press:bool = False
    _action:Any # inputmap
    _visibility_mode:Any #Always, touchscreen only

class VirtualJoystick(Control):
    flick_canceled = Signal()
    flicked = Signal()
    pressed = Signal()
    released = Signal()
    tapped = Signal()

    _joystick_mode:Any #fixed Dynamic, following
    _joystick_size:int = 100
    _tip_size:int = 50
    _deadzone_ratio:float = 0.0
    _clampzone_ratio:float = 1.0
    _initial_offset_ratio:Vector2


    _visibility_mode:Any # always, when touched