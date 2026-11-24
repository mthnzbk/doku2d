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
    deadzone: float | None = None
    device: int | None = None

    def __post_init__(self):
        if self.direction not in (-1,1) or self.deadzone is not None and not 0 <= self.deadzone < 1:
            raise ValueError("Axis direction must be -1/1 and deadzone in [0,1)")
        if isinstance(self.axis,str):
            object.__setattr__(self,"axis",getattr(Axis,self.axis.upper()))


@dataclass(frozen=True)
class MouseButton:
    button: int = 0


@dataclass(frozen=True)
class _BindingCapture:
    action: str
    callback: object
    append: bool
    axis_threshold: float
    cancel_key: int | None


class Input:
    def __init__(self):
        self._bindings = {}
        self._overrides = {}
        self._joy_deadzone = 0.2
        self._save_preferences = None
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
        self._contexts = []
        self._context_blocked = set()
        self._last_device = 'keyboard'
        self._binding_capture = None
        self._capture_keys = set()
        self._capture_buttons = set()
        self._capture_axes = {}
        self._capture_text = False
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
        self._check_bindings(bindings)
        self._bindings[action] = self._overrides.get(action, bindings)
        if global_action:
            self._global.add(action)
        else:
            self._global.discard(action)
        self._refresh()
        return self

    @staticmethod
    def _check_bindings(bindings):
        if not all(isinstance(item, (int, JoyAxis, JoyButton, MouseButton)) for item in bindings):
            raise TypeError('Bindings must be Key constants, JoyAxis, JoyButton or MouseButton')

    def get_bindings(self, action):
        return self._bindings[action]

    @property
    def last_device(self):
        return self._last_device

    def binding_hint(self, action, *, device=None):
        """Caption for the first binding on the selected or last-used device."""
        bindings = self.get_bindings(action)
        device = self.last_device if device is None else device
        gamepad = device == 'gamepad'
        binding = next((item for item in bindings if isinstance(item, (JoyButton, JoyAxis)) == gamepad),
                       bindings[0] if bindings else None)
        if isinstance(binding, JoyButton):
            return f'Gamepad {binding.button+1}'
        if isinstance(binding, JoyAxis):
            return f'Gamepad {binding.axis} {"+" if binding.direction > 0 else "−"}'
        if isinstance(binding, MouseButton):
            return f'Mouse {binding.button+1}'
        if binding is None:
            return '—'
        name = next((name for name in dir(Key) if name.isupper() and getattr(Key, name) == binding), None)
        return name.replace('_', ' ').title() if name else str(binding)

    def push_context(self, *actions, allow_gui=False):
        """Enable only these actions and global actions until this token is popped."""
        unknown = set(actions) - self._bindings.keys()
        if unknown:
            raise KeyError(sorted(unknown)[0])
        token = object()
        self._change_context([*self._contexts, (token, frozenset(actions), bool(allow_gui))])
        return token

    def pop_context(self, token=None):
        """Remove the specified context, or remove the current one."""
        if self._contexts:
            token = self._contexts[-1][0] if token is None else token
            self._change_context([context for context in self._contexts if context[0] is not token])

    def _enabled_actions(self):
        return self._contexts[-1][1] | self._global if self._contexts else set(self._bindings)

    def _change_context(self, contexts):
        before = self._enabled_actions()
        self._contexts = contexts
        after = self._enabled_actions()
        changed = before ^ after
        self._context_blocked.update(action for action in changed if self._raw_strength(action))
        for edges in (self._pressed, self._pending_pressed, self._physics_pressed):
            edges.difference_update(changed)
        self._refresh()

    def set_bindings(self, action, *bindings):
        """Set the player's bindings for a registered action, keeping its global flag."""
        if action not in self._bindings:
            raise KeyError(action)
        self._check_bindings(bindings)
        self._overrides[action] = self._bindings[action] = bindings
        self._refresh()
        self._remember()

    @property
    def binding_capture_action(self):
        """Action currently waiting for an input, or None."""
        return self._binding_capture.action if self._binding_capture is not None else None

    def capture_binding(self, action, callback=None, *, append=False, axis_threshold=.65,
                        cancel_key=Key.ESCAPE):
        """Assign the next keyboard key, gamepad button or strong axis movement."""
        if action not in self._bindings:
            raise KeyError(action)
        if callback is not None and not callable(callback):
            raise TypeError('Binding capture callback must be callable')
        if not isfinite(axis_threshold) or not 0 < axis_threshold <= 1:
            raise ValueError('Axis capture threshold must be in (0, 1]')
        if cancel_key is not None and not isinstance(cancel_key, int):
            raise TypeError('Cancel key must be a Key constant or None')
        if self._binding_capture is not None:
            raise RuntimeError('Cancel the active binding capture before starting another')
        self._binding_capture = _BindingCapture(action, callback, bool(append), axis_threshold, cancel_key)

    def cancel_binding_capture(self):
        """Cancel the active capture without changing the action's bindings."""
        if self._binding_capture is None:
            return False
        self._finish_capture(None)
        return True

    def _finish_capture(self, binding):
        capture, self._binding_capture = self._binding_capture, None
        if binding is not None:
            old = self.get_bindings(capture.action)
            if not capture.append:
                self.set_bindings(capture.action, binding)
            elif binding not in old:
                self.set_bindings(capture.action, *old, binding)
        if capture.callback is not None:
            capture.callback(binding)

    def _consume_capture_event(self, event):
        kind = getattr(event, 'type', None)
        capture = self._binding_capture
        if kind == Event.TEXT_ENTERED and (capture is not None or self._capture_text):
            self._capture_text = False
            return True
        if kind == Event.KEY_PRESSED:
            self._capture_text = False
            if capture is None and event.code not in self._capture_keys:
                return False
            repeated = event.code in self._keys or event.code in self._capture_keys
            self._keys.discard(event.code)
            self._blocked_keys.discard(event.code)
            self._capture_keys.add(event.code)
            self._capture_text = True
            self._refresh()
            if capture is not None and not repeated and 0 <= event.code < Key.KEY_COUNT:
                self._finish_capture(None if event.code == capture.cancel_key else event.code)
            return True
        if kind == Event.KEY_RELEASED and event.code in self._capture_keys:
            self._capture_keys.remove(event.code)
            return True
        if kind in (Event.JOYSTICK_BUTTON_PRESSED, Event.JOYSTICK_BUTTON_RELEASED):
            item = (event.joystick_id, event.button)
            if kind == Event.JOYSTICK_BUTTON_RELEASED and item in self._capture_buttons:
                self._capture_buttons.remove(item)
                return True
            if kind == Event.JOYSTICK_BUTTON_PRESSED and (capture is not None or item in self._capture_buttons):
                repeated = item in self._buttons or item in self._capture_buttons
                self._buttons.discard(item)
                self._capture_buttons.add(item)
                self._refresh()
                if capture is not None and not repeated:
                    self._finish_capture(JoyButton(event.button))
                return True
        if kind == Event.JOYSTICK_MOVED:
            item = (event.joystick_id, event.axis)
            if capture is None and item not in self._capture_axes:
                return False
            value = self._axis_value(event)
            previous = self._capture_axes.get(item, self._axes.get(item, 0))
            self._axes.pop(item, None)
            if abs(value) <= min(self.joy_deadzone, .25) or (capture is None and previous * value < 0):
                self._capture_axes.pop(item, None)
            else:
                self._capture_axes[item] = value
            self._refresh()
            direction = 1 if value >= 0 else -1
            if capture is not None and previous * direction < capture.axis_threshold <= abs(value):
                self._finish_capture(JoyAxis(event.axis, direction))
            return True
        return False

    @property
    def joy_deadzone(self):
        return self._joy_deadzone

    @joy_deadzone.setter
    def joy_deadzone(self, value):
        if not 0 <= value < 1:
            raise ValueError('Joystick deadzone must be in [0, 1)')
        if value != self._joy_deadzone:
            self._joy_deadzone = float(value)
            self._refresh()
            self._remember()

    def _restore_preferences(self, data, save):
        if isinstance(data, dict):
            overrides = data.get('bindings', {})
            if isinstance(overrides, dict):
                for name, bindings in overrides.items():
                    try:
                        if not isinstance(bindings, list):
                            continue
                        self._overrides[name] = tuple(_decode_binding(binding) for binding in bindings)
                    except (TypeError, ValueError, KeyError):
                        continue
                    if name in self._bindings:
                        self._bindings[name] = self._overrides[name]
            deadzone = data.get('joy_deadzone', 0.2)
            if type(deadzone) in (int, float) and 0 <= deadzone < 1:
                self._joy_deadzone = float(deadzone)
        self._refresh()
        self._save_preferences = save

    def _remember(self):
        if self._save_preferences is not None:
            self._save_preferences({
                'joy_deadzone': self.joy_deadzone,
                'bindings': {name: [_encode_binding(binding) for binding in bindings]
                             for name, bindings in self._overrides.items()},
            })

    def _binding_strength(self, binding):
        if isinstance(binding,JoyButton):
            return float(any(button == binding.button and (binding.device is None or device == binding.device)
                             for device,button in self._buttons))
        if isinstance(binding,JoyAxis):
            values = [max(0,value*binding.direction) for (device,axis),value in self._axes.items()
                      if axis == binding.axis and (binding.device is None or device == binding.device)]
            value = max(values,default=0)
            deadzone = self.joy_deadzone if binding.deadzone is None else binding.deadzone
            return max(0, (value - deadzone) / (1 - deadzone))
        if isinstance(binding,MouseButton):
            return float(binding.button in self._mouse)
        return float(binding in self._keys and binding not in self._blocked_keys)

    def _raw_strength(self, action):
        return max([self._binding_strength(binding) for binding in self._bindings[action]]
                   + list(self._virtual.get(action, {}).values()) + [0])

    def _refresh(self):
        enabled = self._enabled_actions()
        allow_gui = self._contexts and self._contexts[-1][2]
        for action in self._bindings:
            previous = self._strengths.get(action,0)
            value = self._raw_strength(action)
            if not value:
                self._context_blocked.discard(action)
            if (action not in enabled or action in self._context_blocked
                    or (self._gui_captured and not allow_gui and action not in self._global)):
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
        self._note_device(event)
        if not self._consume_capture_event(event):
            self._handle_event(event, consumed=consumed)

    def _note_device(self, event):
        kind = getattr(event, 'type', None)
        if kind in (Event.KEY_PRESSED, Event.MOUSE_BUTTON_PRESSED):
            self._last_device = 'keyboard'
        elif kind == Event.JOYSTICK_BUTTON_PRESSED or (kind == Event.JOYSTICK_MOVED
                                                       and abs(self._axis_value(event)) > self.joy_deadzone):
            self._last_device = 'gamepad'

    @staticmethod
    def _axis_value(event):
        return max(-1, min(1, event.position / 100))

    def _handle_event(self, event, *, consumed=False):
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
            self._axes[event.joystick_id,event.axis] = self._axis_value(event)
        elif kind == Event.JOYSTICK_DISCONNECTED:
            self._buttons = {item for item in self._buttons if item[0] != event.joystick_id}
            self._axes = {key:value for key,value in self._axes.items() if key[0] != event.joystick_id}
            self._capture_buttons = {item for item in self._capture_buttons if item[0] != event.joystick_id}
            self._capture_axes = {key:value for key,value in self._capture_axes.items() if key[0] != event.joystick_id}
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
        changed = False
        for values in self._virtual.values():
            if source in values:
                del values[source]
                changed = True
        if changed:
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
        self._context_blocked.clear()
        self._capture_keys.clear()
        self._capture_buttons.clear()
        self._capture_axes.clear()
        self._capture_text = False
        self._refresh()
        self.cancel_binding_capture()

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


def _encode_binding(binding):
    if isinstance(binding, JoyAxis):
        return {'type': 'axis', 'axis': int(binding.axis), 'direction': binding.direction,
                'deadzone': binding.deadzone, 'device': binding.device}
    if isinstance(binding, JoyButton):
        return {'type': 'joy_button', 'button': binding.button, 'device': binding.device}
    if isinstance(binding, MouseButton):
        return {'type': 'mouse_button', 'button': binding.button}
    return {'type': 'key', 'key': int(binding)}


def _decode_binding(data):
    def integer(name):
        value = data[name]
        if type(value) is not int:
            raise ValueError('Expected an integer binding value')
        return value

    def device():
        return None if data.get('device') is None else integer('device')

    kind = data['type']
    if kind == 'key':
        return integer('key')
    if kind == 'axis':
        return JoyAxis(integer('axis'), integer('direction'), data.get('deadzone'), device())
    if kind == 'joy_button':
        return JoyButton(integer('button'), device())
    if kind == 'mouse_button':
        return MouseButton(integer('button'))
    raise ValueError('Unknown input binding type')


__all__ = ["Input","Key","JoyAxis","JoyButton","MouseButton"]
