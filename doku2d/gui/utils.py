from math import hypot
from sfml.system import Vector2
from ..core import Signal
from .base import Control
from .buttons import TextureButton
from .theme import disk


class TouchScreenButton(TextureButton):
    released = Signal()
    action_changed = Signal()

    def __init__(self,name=None):
        super().__init__(name)
        self._bitmask = None
        self._shape = None
        self._shape_centered = True
        self._shape_visible = True
        self._passby_press = False
        self._action = None
        self._visibility_mode = "always"
        self._pointers = set()
        self.focusable = False

    def contains(self, pixel):
        if not super().contains(pixel):
            return False
        point = self.local_point(pixel)
        if self.bitmask is not None:
            width, height = self.bitmask.size
            x = min(width-1, int(point.x/max(1,self.size.x)*width))
            y = min(height-1, int(point.y/max(1,self.size.y)*height))
            if width == 0 or height == 0 or self.bitmask[x,y].a == 0:
                return False
        if callable(self.shape):
            return bool(self.shape(point))
        if self.shape is not None and hasattr(self.shape, "radius"):
            center = self.size/2 if self.shape_centered else Vector2(self.shape.radius,self.shape.radius)
            return hypot(point.x-center.x,point.y-center.y) <= self.shape.radius
        return True

    def render(self, target, states):
        if self.visibility_mode == "when_touched" and not self._pressed:
            return
        if self.shape_visible:
            super().render(target, states)

    def _pointer_down(self,point,button=0,pointer=0):
        if button != 0: return False
        first = not self._pointers
        self._pointers.add(pointer)
        self._pressed = True
        if first:
            self.pressed.emit()
            self.action_changed.emit(self.action,True)
            if self.game: self.game._ui.set_action(self.action,self,True)
        return True

    def _pointer_up(self,point,button=0,pointer=0):
        self._pointers.discard(pointer)
        if not self._pointers and self._pressed:
            self._pressed = False
            self.released.emit()
            self.action_changed.emit(self.action,False)
            if self.game: self.game._ui.set_action(self.action,self,False)

    def _cancel_pointer(self):
        self._pointers.clear()
        self._pointer_up(Vector2(0,0))


    @property
    def bitmask(self):
        return self._bitmask

    @bitmask.setter
    def bitmask(self, value):
        self._bitmask = value

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, value):
        self._shape = value

    @property
    def shape_centered(self):
        return self._shape_centered

    @shape_centered.setter
    def shape_centered(self, value):
        self._shape_centered = value

    @property
    def shape_visible(self):
        return self._shape_visible

    @shape_visible.setter
    def shape_visible(self, value):
        self._shape_visible = value

    @property
    def passby_press(self):
        return self._passby_press

    @passby_press.setter
    def passby_press(self, value):
        self._passby_press = value

    @property
    def action(self):
        return self._action

    @action.setter
    def action(self, value):
        if self.game and self._pressed:
            self.game.ui.set_action(self._action,self,False)
        self._action = value
        if self.game and self._pressed:
            self.game.ui.set_action(self._action,self,True)

    @property
    def visibility_mode(self):
        return self._visibility_mode

    @visibility_mode.setter
    def visibility_mode(self, value):
        self._visibility_mode = value


class VirtualJoystick(Control):
    flick_canceled = Signal()
    flicked = Signal()
    pressed = Signal()
    released = Signal()
    tapped = Signal()
    moved = Signal()

    def __init__(self,name=None):
        super().__init__(name)
        self._joystick_mode = "fixed"
        self._joystick_size = 100
        self._tip_size = 40
        self._deadzone_ratio = 0.1
        self._clampzone_ratio = 1.0
        self._initial_offset_ratio = Vector2(0,0)
        self._visibility_mode = "always"
        self._value = Vector2(0,0)
        self._origin = Vector2(50,50)
        self._pointer = None
        self._touch_time = 0
        self._actions = ("move_left", "move_right", "move_up", "move_down")
        self.size = (100,100)

    def bind_actions(self, left="move_left", right="move_right", up="move_up", down="move_down"):
        """Map this joystick to four named actions; pass four None values to disable."""
        actions = (left, right, up, down)
        if not all(value is None or isinstance(value, str) and value for value in actions):
            raise ValueError("Action names must be nonempty strings or None")
        if self.input is not None:
            self.input.release_source(self)
        self._actions = actions
        self._publish_actions()
        return self

    def _publish_actions(self):
        if self.input is None:
            return
        x, y = self.value
        for action, strength in zip(self._actions, (max(0,-x), max(0,x), max(0,-y), max(0,y))):
            if action is not None:
                self.input.action_press(action, strength, source=self)

    @property
    def value(self):
        return Vector2(*self._value)

    def _pointer_down(self,point,button=0,pointer=0):
        if button != 0 or self._pointer is not None: return False
        self._pointer = pointer
        self._touch_time = 0
        self._origin = Vector2(*point) if self.joystick_mode in ("dynamic","following") else self.size/2
        self._origin += self.initial_offset_ratio*(self.joystick_size/2)
        self.pressed.emit()
        self._pointer_move(point,pointer)
        return True

    def _pointer_move(self,point,pointer=0):
        if pointer != self._pointer: return
        delta = point-self._origin
        distance = hypot(delta.x,delta.y)
        radius = max(1,self.joystick_size/2*max(0.01,self.clampzone_ratio))
        if self.joystick_mode == "following" and distance > radius:
            self._origin += delta*(1-radius/distance)
        magnitude = min(1,distance/radius)
        deadzone = max(0,min(0.99,self.deadzone_ratio))
        strength = max(0,(magnitude-deadzone)/(1-deadzone))
        self._value = delta*(strength/distance) if distance else Vector2(0,0)
        self._publish_actions()
        self.moved.emit(self.value)

    def _pointer_up(self,point,button=0,pointer=0):
        if pointer != self._pointer: return
        if self._touch_time < 0.25:
            if hypot(self.value.x,self.value.y) > 0.5: self.flicked.emit(self.value)
            else: self.tapped.emit()
        else: self.flick_canceled.emit()
        self._pointer = None
        self._value = Vector2(0,0)
        self._publish_actions()
        self.moved.emit(self.value)
        self.released.emit()

    def _cancel_pointer(self):
        if self._pointer is not None:
            self._pointer_up(self._origin,pointer=self._pointer)

    def update(self,dt):
        self._touch_time += dt

    def render(self,target,states):
        if self.visibility_mode == "when_touched" and self._pointer is None: return
        center = self._origin if self._pointer is not None else self.size/2
        disk(target,states,center,self.joystick_size/2,self.theme.background)
        tip = center+self.value*(self.joystick_size/2-self.tip_size/2)
        disk(target,states,tip,self.tip_size/2,self.theme.accent)


    @property
    def joystick_mode(self):
        return self._joystick_mode

    @joystick_mode.setter
    def joystick_mode(self, value):
        self._joystick_mode = value

    @property
    def joystick_size(self):
        return self._joystick_size

    @joystick_size.setter
    def joystick_size(self, value):
        self._joystick_size = value

    @property
    def tip_size(self):
        return self._tip_size

    @tip_size.setter
    def tip_size(self, value):
        self._tip_size = value

    @property
    def deadzone_ratio(self):
        return self._deadzone_ratio

    @deadzone_ratio.setter
    def deadzone_ratio(self, value):
        self._deadzone_ratio = value

    @property
    def clampzone_ratio(self):
        return self._clampzone_ratio

    @clampzone_ratio.setter
    def clampzone_ratio(self, value):
        self._clampzone_ratio = value

    @property
    def initial_offset_ratio(self):
        return self._initial_offset_ratio

    @initial_offset_ratio.setter
    def initial_offset_ratio(self, value):
        self._initial_offset_ratio = value

    @property
    def visibility_mode(self):
        return self._visibility_mode

    @visibility_mode.setter
    def visibility_mode(self, value):
        self._visibility_mode = value


__all__ = ["TouchScreenButton","VirtualJoystick"]
