"""Named actions shared by keyboard, gamepad and virtual controls."""
from dataclasses import dataclass
from math import hypot, isfinite
from sfml.system import Vector2
from sfml.window import Axis, Event, Keyboard

Key = Keyboard


@dataclass(frozen=True)
class JoyButton:
    button: int
    device: int | None = None


@dataclass(frozen=True)
class JoyAxis:
    axis: object
    direction: int = 1
    deadzone: float = 0.2
    device: int | None = None

    def __post_init__(self):
        if self.direction not in (-1,1) or not 0 <= self.deadzone < 1:
            raise ValueError("Axis direction must be -1/1 and deadzone in [0,1)")
        if isinstance(self.axis,str):
            object.__setattr__(self,"axis",getattr(Axis,self.axis.upper()))


@dataclass(frozen=True)
class MouseButton:
    button: int = 0


class Input:
    def __init__(self):
        self._bindings = {}
        self._global = set()
        self._keys = set()
        self._blocked_keys = set()
        self._mouse = set()
        self._buttons = set()
        self._axes = {}
        self._virtual = {}
        self._strengths = {}
        self._pressed = set()
        self._released = set()
        self._physics_pressed = set()
        self._physics_released = set()
        self._pending_pressed = set()
        self._pending_released = set()
        self._phase = "frame"
        self._gui_captured = False
        self.bind("move_left",Key.A,Key.LEFT,JoyAxis("X",-1),JoyAxis("POV_X",-1))
        self.bind("move_right",Key.D,Key.RIGHT,JoyAxis("X"),JoyAxis("POV_X"))
        self.bind("move_up",Key.W,Key.UP,JoyAxis("Y",-1),JoyAxis("POV_Y",1))
        self.bind("move_down",Key.S,Key.DOWN,JoyAxis("Y"),JoyAxis("POV_Y",-1))
        self.bind("jump",Key.SPACE,JoyButton(0))
        self.bind("interact",Key.E,JoyButton(0))
        self.bind("pause",Key.ESCAPE,Key.P,JoyButton(7),global_action=True)

    @property
    def actions(self):
        return tuple(self._bindings)

    def bind(self, action, *bindings, global_action=False):
        if not isinstance(action,str) or not action:
            raise ValueError("Action names must be nonempty strings")
        if not all(isinstance(item,(int,JoyAxis,JoyButton,MouseButton)) for item in bindings):
            raise TypeError("Bindings must be Key constants, JoyAxis, JoyButton or MouseButton")
        self._bindings[action] = tuple(bindings)
        if global_action:
            self._global.add(action)
        else:
            self._global.discard(action)
        self._refresh()
        return self

    def _binding_strength(self, binding):
        if isinstance(binding,JoyButton):
            return float(any(button == binding.button and (binding.device is None or device == binding.device)
                             for device,button in self._buttons))
        if isinstance(binding,JoyAxis):
            values = [max(0,value*binding.direction) for (device,axis),value in self._axes.items()
                      if axis == binding.axis and (binding.device is None or device == binding.device)]
            value = max(values,default=0)
            return max(0,(value-binding.deadzone)/(1-binding.deadzone))
        if isinstance(binding,MouseButton):
            return float(binding.button in self._mouse)
        return float(binding in self._keys and binding not in self._blocked_keys)

    def _refresh(self):
        for action,bindings in self._bindings.items():
            previous = self._strengths.get(action,0)
            value = max([self._binding_strength(binding) for binding in bindings]
                        + list(self._virtual.get(action,{}).values()) + [0])
            if self._gui_captured and action not in self._global:
                value = 0
            self._strengths[action] = value
            if previous <= 0 < value:
                self._pressed.add(action)
                self._pending_pressed.add(action)
            if value <= 0 < previous:
                self._released.add(action)
                self._pending_released.add(action)

    def set_gui_captured(self, value):
        value = bool(value)
        if value and not self._gui_captured:
            self._blocked_keys.update(self._keys)
            for edges in (self._pressed,self._pending_pressed,self._physics_pressed):
                edges.intersection_update(self._global)
        self._gui_captured = value
        self._refresh()

    def handle_event(self, event, *, consumed=False):
        kind = getattr(event,"type",None)
        if kind == Event.KEY_PRESSED:
            self._keys.add(event.code)
            if consumed:
                self._blocked_keys.add(event.code)
        elif kind == Event.KEY_RELEASED:
            self._keys.discard(event.code)
            self._blocked_keys.discard(event.code)
        elif kind == Event.MOUSE_BUTTON_PRESSED and not consumed:
            self._mouse.add(event.button)
        elif kind == Event.MOUSE_BUTTON_RELEASED:
            self._mouse.discard(event.button)
        elif kind == Event.JOYSTICK_BUTTON_PRESSED and not consumed:
            self._buttons.add((event.joystick_id,event.button))
        elif kind == Event.JOYSTICK_BUTTON_RELEASED:
            self._buttons.discard((event.joystick_id,event.button))
        elif kind == Event.JOYSTICK_MOVED:
            self._axes[event.joystick_id,event.axis] = max(-1,min(1,event.position/100))
        elif kind == Event.JOYSTICK_DISCONNECTED:
            self._buttons = {item for item in self._buttons if item[0] != event.joystick_id}
            self._axes = {key:value for key,value in self._axes.items() if key[0] != event.joystick_id}
        elif kind == Event.LOST_FOCUS:
            self.clear()
        self._refresh()

    def get_action_strength(self, action):
        return self._strengths.get(action,0.0)

    def is_action_pressed(self, action):
        return self.get_action_strength(action) > 0

    def is_action_just_pressed(self, action):
        return action in (self._physics_pressed if self._phase == "physics" else self._pressed)

    def is_action_just_released(self, action):
        return action in (self._physics_released if self._phase == "physics" else self._released)

    def get_axis(self, negative, positive):
        return self.get_action_strength(positive)-self.get_action_strength(negative)

    def get_vector(self, left="move_left", right="move_right", up="move_up", down="move_down", *, deadzone=0):
        if not 0 <= deadzone < 1:
            raise ValueError("deadzone must be in [0,1)")
        x,y = self.get_axis(left,right),self.get_axis(up,down)
        length = hypot(x,y)
        if length <= deadzone:
            return Vector2(0,0)
        magnitude = min(1,(length-deadzone)/(1-deadzone))
        return Vector2(x/length*magnitude,y/length*magnitude)

    def action_press(self, action, strength=1.0, *, source=None):
        if not isfinite(strength) or not 0 <= strength <= 1:
            raise ValueError("Action strength must be finite and in [0,1]")
        if action not in self._bindings:
            self.bind(action)
        self._virtual.setdefault(action,{})[source] = float(strength)
        self._refresh()

    def action_release(self, action, *, source=None):
        self._virtual.get(action,{}).pop(source,None)
        self._refresh()

    def release_source(self, source):
        for values in self._virtual.values():
            values.pop(source,None)
        self._refresh()

    def clear(self):
        self._pressed.clear()
        self._pending_pressed.clear()
        self._physics_pressed.clear()
        self._keys.clear()
        self._blocked_keys.clear()
        self._mouse.clear()
        self._buttons.clear()
        self._axes.clear()
        self._virtual.clear()
        self._refresh()

    def _begin_physics(self):
        self._phase = "physics"
        self._physics_pressed,self._pending_pressed = self._pending_pressed,set()
        self._physics_released,self._pending_released = self._pending_released,set()

    def _end_physics(self):
        self._physics_pressed.clear()
        self._physics_released.clear()
        self._phase = "frame"

    def _end_frame(self):
        self._pressed.clear()
        self._released.clear()


__all__ = ["Input","Key","JoyAxis","JoyButton","MouseButton"]
