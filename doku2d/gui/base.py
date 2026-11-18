from enum import Enum
from sfml.system import Vector2
from ..core import Entity, Signal
from .theme import Theme, box


class Anchor(Enum):
    TOP_LEFT = (0, 0)
    TOP = (0.5, 0)
    TOP_RIGHT = (1, 0)
    LEFT = (0, 0.5)
    CENTER = (0.5, 0.5)
    RIGHT = (1, 0.5)
    BOTTOM_LEFT = (0, 1)
    BOTTOM = (0.5, 1)
    BOTTOM_RIGHT = (1, 1)


_default_theme = Theme()


class Control(Entity):
    mouse_entered = Signal()
    mouse_exited = Signal()
    resized = Signal()
    gui_input = Signal()
    focus_entered = Signal()
    focus_exited = Signal()
    _is_control = True

    def __init__(self, name=None):
        super().__init__(name)
        self._font = None
        self._theme = None
        self._font_size = None
        self._size = Vector2(160, 36)
        self._min_size = Vector2(0, 0)
        self._max_size = Vector2(float("inf"), float("inf"))
        self._anchor = None
        self._offset = Vector2(0, 0)
        self._layout = None
        self.focusable = False
        self.show_focus = False
        self.mouse_filter = "stop"
        self.clip_contents = True
        self.hovered = False
        self._pressed = False
        self._disabled = False

    @property
    def visible(self):
        return Entity.visible.fget(self) and (self._layout is None or self._layout.visible)

    @visible.setter
    def visible(self, value):
        self._visible = bool(value)
        if not self.visible and self.game and self.game._ui:
            self.game._ui.arrange()

    @property
    def disabled(self):
        return self._disabled

    @disabled.setter
    def disabled(self, value):
        self._disabled = bool(value)
        if self._disabled and self.game and self.game._ui:
            self.game._ui.release(self)

    @property
    def anchor(self):
        return self._anchor

    @anchor.setter
    def anchor(self, value):
        if value is not None and not isinstance(value, Anchor):
            raise TypeError("anchor must be an Anchor or None")
        self._anchor = value

    def on_added(self):
        from .runtime import UI
        if self.game._ui is None:
            self.game._ui = UI(self.game)
        if self.canvas is None:
            self.canvas = self.game._ui.canvas
        self.arrange()

    def on_removed(self):
        if self.game._ui:
            self.game._ui.release(self)

    def arrange(self):
        if self.anchor is not None and self._layout is None and self.game is not None:
            x, y = self.anchor.value
            self.position = (self.game.size.x*x-self.size.x*x+self.offset.x,
                             self.game.size.y*y-self.size.y*y+self.offset.y)

    @property
    def font(self):
        return self._font

    @font.setter
    def font(self, value):
        self._font = value

    @property
    def theme(self):
        if self._theme is not None:
            return self._theme
        if self._layout is not None:
            return self._layout.theme
        if self.game is not None:
            return self.game.ui.theme
        return _default_theme

    @theme.setter
    def theme(self, value):
        if value is not None and not isinstance(value, Theme):
            raise TypeError("theme must be a Theme")
        self._theme = value

    @property
    def font_size(self):
        return self.theme.font_size if self._font_size is None else self._font_size

    @font_size.setter
    def font_size(self, value):
        if value is None:
            self._font_size = None
            return
        if value <= 0 or int(value) != value:
            raise ValueError("font_size must be a positive integer")
        self._font_size = int(value)

    @property
    def size(self):
        return Vector2(*self._size)

    @size.setter
    def size(self, value):
        size = self._vector(value)
        if size.x < 0 or size.y < 0:
            raise ValueError("Control size cannot be negative")
        size = Vector2(max(self.min_size.x, min(self.max_size.x, size.x)),
                       max(self.min_size.y, min(self.max_size.y, size.y)))
        if tuple(size) != tuple(self._size):
            self._size = size
            self.resized.emit()

    @property
    def min_size(self):
        return Vector2(*self._min_size)

    @min_size.setter
    def min_size(self, value):
        value = self._vector(value)
        if value.x < 0 or value.y < 0 or value.x > self.max_size.x or value.y > self.max_size.y:
            raise ValueError("Invalid minimum size")
        self._min_size = value
        self.size = self.size

    @property
    def max_size(self):
        return Vector2(*self._max_size)

    @max_size.setter
    def max_size(self, value):
        x, y = value
        if x != x or y != y or x < self.min_size.x or y < self.min_size.y:
            raise ValueError("Invalid maximum size")
        self._max_size = Vector2(x, y)
        self.size = self.size

    @property
    def offset(self):
        return Vector2(*self._offset)

    @offset.setter
    def offset(self, value):
        self._offset = self._vector(value)





    @property
    def focused(self):
        return self.game is not None and self.game._ui.focus is self

    def grab_focus(self):
        if self.game:
            self.game._ui.set_focus(self)

    def release_focus(self):
        if self.focused:
            self.game._ui.set_focus(None)




    def local_point(self, pixel):
        if self.game is None:
            return Vector2(*pixel)
        view = self.game.make_view(self.canvas or self.game.world)
        point = view.inverse_transform.transform_point(
            (pixel[0]*2/self.game.size.x-1, 1-pixel[1]*2/self.game.size.y))
        return self.transform.inverse.transform_point(point)

    def contains(self, pixel):
        if self.scale.x == 0 or self.scale.y == 0:
            return False
        point = self.local_point(pixel)
        return 0 <= point.x < self.size.x and 0 <= point.y < self.size.y

    def _pointer_down(self, point, button=0, pointer=0):
        return False

    def _pointer_move(self, point, pointer=0):
        pass

    def _pointer_up(self, point, button=0, pointer=0):
        pass

    def _cancel_pointer(self):
        self._pressed = False

    def _key(self, event):
        return False

    def _text_input(self, text):
        return False

    def _wheel(self, delta):
        return False

    def _popup_event(self, event):
        return False

    def _render_popup(self, target):
        pass

    def _draw_focus(self, target, states):
        if self.focused and self.show_focus:
            box(target, states, (1, 1, self.size.x-2, self.size.y-2),
                (0, 0, 0, 0), self.theme.accent, 1, radius=self.theme.radius)
