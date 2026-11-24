from dataclasses import replace
from sfml.graphics import Rect
from sfml.window import Event, Keyboard
from ..core import Canvas
from .base import Control
from .dragdrop import _DragDrop
from .theme import Theme


class _LogicalPointerEvent:
    def __init__(self, event, position):
        self._event = event
        self.position = position

    def __getattr__(self, name):
        return getattr(self._event, name)


class UI:
    """Per-game focus, capture, event routing and drawing clips."""
    def __init__(self, game):
        self.game = game
        self.canvas = Canvas("Interface", order=100, screen_space=True)
        self.theme = game._theme_source if game._theme_source is not None else Theme()
        self.focus = None
        self.hover = None
        self.capture = {}
        self.popup = None
        self._actions = {}
        self._down_pointers = set()
        self.drag_drop = _DragDrop(self)

    @property
    def theme(self):
        return self._theme

    @theme.setter
    def theme(self, value):
        if not isinstance(value, Theme):
            value = Theme.load(value, resources=self.game.resources)
        elif value.resources is None:
            value = replace(value, resources=self.game.resources)
        self._theme = value

    def set_action(self, name, source, pressed):
        if not name:
            return
        sources = self._actions.setdefault(name, set())
        if pressed:
            sources.add(source)
            self.game.input.action_press(name,source=source)
        else:
            sources.discard(source)
            self.game.input.action_release(name,source=source)

    def is_action_pressed(self, name):
        return bool(self._actions.get(name))

    @property
    def keyboard_captured(self):
        return self.focus is not None

    def controls(self):
        return [obj for obj in self.game.draw_list()
                if getattr(obj, "_is_control", False) and obj.can_process()]

    def set_focus(self, control):
        if control is not None and (not control.focusable or control.disabled or not control.visible):
            return
        if self.focus is control:
            return
        previous, self.focus = self.focus, control
        if previous:
            previous._cancel_pointer()
            previous.focus_exited.emit()
        if control:
            control.focus_entered.emit()

    def release(self, control):
        self.drag_drop.release(control)
        if self.focus is control:
            self.set_focus(None)
        if self.hover is control:
            self.hover = None
            control.hovered = False
            control.mouse_exited.emit()
        for pointer, owner in tuple(self.capture.items()):
            if owner is control:
                del self.capture[pointer]
                owner._cancel_pointer()
        if self.popup is control:
            self.popup = None

    def arrange(self):
        for obj in self.game.objects:
            if getattr(obj, "_is_control", False):
                obj.arrange()
        for control in (self.focus, self.hover, self.popup, *tuple(self.capture.values())):
            if control and (control.game is not self.game or not control.visible
                            or control.disabled or not control.can_process()):
                self.release(control)
        self.drag_drop.prune()

    def _hit(self, position):
        return next((obj for obj in reversed(self.controls())
                     if obj.mouse_filter != "ignore" and obj.contains(position)), None)

    def handle_event(self, event):
        self.arrange()
        if event.type == Event.LOST_FOCUS:
            self.drag_drop.cancel(lost_focus=True)
            for control in tuple(self.capture.values()):
                self.release(control)
            self.set_focus(None)
            self._down_pointers.clear()
            return False
        if (event.type == Event.KEY_PRESSED and event.code == Keyboard.ESCAPE
                and self.drag_drop.active is not None):
            self.drag_drop.cancel()
            return True
        pointer_types = (Event.MOUSE_MOVED, Event.MOUSE_BUTTON_PRESSED,
                         Event.MOUSE_BUTTON_RELEASED, Event.MOUSE_WHEEL_SCROLLED,
                         Event.TOUCH_BEGAN, Event.TOUCH_MOVED, Event.TOUCH_ENDED)
        if event.type in pointer_types:
            logical = self.game.window_to_screen(event.position, allow_outside=True)
            if logical is None:
                return False
            position = tuple(logical)
            width, height = self.game.size
            inside = 0 <= logical.x < width and 0 <= logical.y < height
            event = _LogicalPointerEvent(event, logical)
            touch = event.type in (Event.TOUCH_BEGAN, Event.TOUCH_MOVED, Event.TOUCH_ENDED)
            pointer = event.finger+1 if touch else 0
            down = event.type in (Event.MOUSE_BUTTON_PRESSED, Event.TOUCH_BEGAN)
            up = event.type in (Event.MOUSE_BUTTON_RELEASED, Event.TOUCH_ENDED)
            if down and inside:
                self._down_pointers.add(pointer)
            elif up:
                self._down_pointers.discard(pointer)
            moved = event.type in (Event.MOUSE_MOVED, Event.TOUCH_MOVED)
            primary_up = up and getattr(event, 'button', 0) == 0
            if self.drag_drop.pointer(pointer, position, inside=inside, moved=moved, released=primary_up):
                return True
            if self.popup is not None and self.popup._popup_event(event):
                return True
            target = self.capture.get(pointer) or (self._hit(position) if inside else None)
            if (target is not None and getattr(target, "passby_press", False)
                    and pointer in self.capture and not target.contains(position)):
                target._pointer_up(target.local_point(position), pointer=pointer)
                del self.capture[pointer]
                target = self._hit(position) if inside else None
            if (target is not None and getattr(target, "passby_press", False)
                    and pointer in self._down_pointers and pointer not in self.capture and not down):
                if target._pointer_down(target.local_point(position), pointer=pointer):
                    self.capture[pointer] = target
            if not touch:
                hover = self._hit(position) if inside else None
                if hover is not self.hover:
                    if self.hover:
                        self.hover.hovered = False
                        self.hover.mouse_exited.emit()
                    self.hover = hover
                    if hover:
                        hover.hovered = True
                        hover.mouse_entered.emit()
            if down:
                self.set_focus(target if target and target.focusable else None)
            if target is None:
                return False
            target.gui_input.emit(event)
            if target.disabled:
                return target.mouse_filter == "stop"
            point = target.local_point(position)
            if down:
                button = getattr(event, "button", 0)
                if target._pointer_down(point, button, pointer):
                    self.capture[pointer] = target
                if button == 0 and (target.drag_source is not None
                                    or type(target).get_drag_data is not Control.get_drag_data):
                    self.drag_drop.arm(target, pointer, position)
            elif event.type in (Event.MOUSE_MOVED, Event.TOUCH_MOVED):
                target._pointer_move(point, pointer)
            elif event.type in (Event.MOUSE_BUTTON_RELEASED, Event.TOUCH_ENDED):
                self.capture.pop(pointer, None)
                target._pointer_up(point, getattr(event, "button", 0), pointer)
            else:
                target._wheel(event.delta)
            return target.mouse_filter == "stop"
        if self.popup is not None and self.popup._popup_event(event):
            return True
        if event.type in (Event.KEY_PRESSED, Event.KEY_RELEASED):
            if event.type == Event.KEY_PRESSED and event.code == Keyboard.TAB:
                controls = [obj for obj in self.controls() if obj.focusable and not obj.disabled]
                if controls:
                    direction = -1 if event.shift else 1
                    index = controls.index(self.focus) if self.focus in controls else (-1 if direction == 1 else 0)
                    self.set_focus(controls[(index+direction) % len(controls)])
                    return True
            if self.focus:
                return self.focus._key(event)
        if event.type == Event.TEXT_ENTERED and self.focus:
            value = event.unicode
            text = chr(value) if isinstance(value, int) else value
            return self.focus._text_input(text)
        return False

    def draw(self, control, target, states):
        original = target.view
        if control.clip_contents:
            view = target.view
            corners = [view.transform.transform_point(states.transform.transform_point(point))
                       for point in ((0, 0), (control.size.x, 0),
                                     (0, control.size.y), tuple(control.size))]
            left = max(0, min((p.x+1)/2 for p in corners))
            top = max(0, min((1-p.y)/2 for p in corners))
            right = min(1, max((p.x+1)/2 for p in corners))
            bottom = min(1, max((1-p.y)/2 for p in corners))
            if right <= left or bottom <= top:
                return
            view.scissor = Rect((left, top), (right-left, bottom-top))
            target.view = view
        try:
            control.render(target, states)
            control._draw_focus(target, states)
        finally:
            target.view = original

    def draw_popup(self, target):
        if self.popup and self.popup.visible:
            self.popup._render_popup(target)
        self.drag_drop.draw(target)
