from sfml.window import Event, Keyboard
from ..core import Signal
from .range import Range
from .theme import box, disk, label, texture


class ProgressBar(Range):
    def __init__(self, name=None, **options):
        super().__init__(name, **options)
        self._show_percentage = True
        self._fill_mode = "left_to_right"
        self.mouse_filter = "ignore"

    def fill_rect(self):
        width, height = self.size
        if self.fill_mode in ("right_to_left", "end2begin"):
            return (width*(1-self.ratio), 0, width*self.ratio, height)
        if self.fill_mode in ("top_to_bottom", "top2bottom"):
            return (0, 0, width, height*self.ratio)
        if self.fill_mode in ("bottom_to_top", "bottom2top"):
            return (0, height*(1-self.ratio), width, height*self.ratio)
        return (0, 0, width*self.ratio, height)

    def render(self, target, states):
        box(target, states, (0, 0, *self.size), self.theme.background, radius=6)
        box(target, states, self.fill_rect(), self.theme.active, radius=6)
        if self.show_percentage:
            label(target, states, self, f"{self.ratio:.0%}", align="center")


    @property
    def show_percentage(self):
        return self._show_percentage

    @show_percentage.setter
    def show_percentage(self, value):
        self._show_percentage = value

    @property
    def fill_mode(self):
        return self._fill_mode

    @fill_mode.setter
    def fill_mode(self, value):
        self._fill_mode = value


class TextureProgressBar(ProgressBar):
    def __init__(self, name=None, **options):
        super().__init__(name, **options)
        self._nine_patch_stretch = False
        self.texture_under = None
        self.texture_progress = None
        self.texture_over = None

    def render(self, target, states):
        if self.texture_under is None and self.texture_progress is None:
            super().render(target, states)
            return
        texture(target, states, self.texture_under, (0, 0, *self.size))
        image = self.texture_progress
        x, y, width, height = self.fill_rect()
        if image is not None and self.size.x and self.size.y:
            region = (x/self.size.x*image.size.x, y/self.size.y*image.size.y,
                      width/self.size.x*image.size.x, height/self.size.y*image.size.y)
            texture(target, states, image, (x, y, width, height), region)
        texture(target, states, self.texture_over, (0, 0, *self.size))


    @property
    def fill_mode(self):
        return self._fill_mode

    @fill_mode.setter
    def fill_mode(self, value):
        self._fill_mode = value

    @property
    def nine_patch_stretch(self):
        return self._nine_patch_stretch

    @nine_patch_stretch.setter
    def nine_patch_stretch(self, value):
        self._nine_patch_stretch = value


class Slider(Range):
    drag_started = Signal()
    drag_ended = Signal()

    def __init__(self, name=None, **options):
        super().__init__(name, **options)
        self._scrollable = True
        self.vertical = False
        self.focusable = True
        self.show_focus = False
        self.size = (180, 32)

    def _set_from_point(self, point):
        extent = self.size.y if self.vertical else self.size.x
        coordinate = self.size.y-point.y if self.vertical else point.x
        self.ratio = max(0, min(1, (coordinate-10)/max(1, extent-20)))

    def _pointer_down(self, point, button=0, pointer=0):
        if button != 0:
            return False
        self._pressed = True
        self._set_from_point(point)
        self.drag_started.emit()
        return True

    def _pointer_move(self, point, pointer=0):
        if self._pressed:
            self._set_from_point(point)

    def _pointer_up(self, point, button=0, pointer=0):
        if self._pressed:
            self._set_from_point(point)
            self._pressed = False
            self.drag_ended.emit()

    def _cancel_pointer(self):
        if self._pressed:
            self._pressed = False
            self.drag_ended.emit()

    def _increment(self, amount):
        self.value += amount*(self.step or (self.max_value-self.min_value)/100)

    def _key(self, event):
        if event.type != Event.KEY_PRESSED:
            return False
        if event.code in (Keyboard.RIGHT, Keyboard.UP):
            self._increment(1)
        elif event.code in (Keyboard.LEFT, Keyboard.DOWN):
            self._increment(-1)
        elif event.code == Keyboard.HOME:
            self.value = self.min_value
        elif event.code == Keyboard.END:
            self.value = self.max_value
        else:
            return False
        return True

    def _wheel(self, delta):
        if self.scrollable:
            self._increment(delta)
        return self.scrollable

    def render(self, target, states):
        tint = self.theme.muted if self.disabled else self.theme.accent
        if self.vertical:
            y = self.size.y-10-(self.size.y-20)*self.ratio
            box(target, states, (self.size.x/2-3, 10, 6, max(0, self.size.y-20)), self.theme.background, radius=3)
            disk(target, states, (self.size.x/2, y+1), 11, (0,0,0,40))
            disk(target, states, (self.size.x/2, y), 8 if not self._pressed else 9, tint)
        else:
            x = 10+(self.size.x-20)*self.ratio
            box(target, states, (10, self.size.y/2-3, max(0, self.size.x-20), 6), self.theme.background, radius=3)
            box(target, states, (10, self.size.y/2-3, max(0, x-10), 6), tint, radius=3)
            disk(target, states, (x, self.size.y/2+1), 11, (0,0,0,40))
            disk(target, states, (x, self.size.y/2), 8 if not self._pressed else 9, tint)


    @property
    def disabled(self):
        return self._disabled

    @disabled.setter
    def disabled(self, value):
        self._disabled = value

    @property
    def scrollable(self):
        return self._scrollable

    @scrollable.setter
    def scrollable(self, value):
        self._scrollable = value


class ScrollBar(Slider):
    scrolling = Signal()

    def __init__(self, name=None, **options):
        super().__init__(name, **options)
        self.page = 10.0
        self._drag_offset = 0.0
        self.value_changed.connect(self._on_scroll)

    def _on_scroll(self, value):
        self.scrolling.emit()

    def thumb_rect(self):
        extent = self.size.y if self.vertical else self.size.x
        total = max(0,self.max_value-self.min_value)+max(0,self.page)
        fraction = min(1,self.page/total) if total else 1
        length = min(extent,max(20,extent*fraction))
        offset = max(0,extent-length)*self.ratio
        if self.vertical:
            return (2,offset,max(0,self.size.x-4),length)
        return (offset,2,length,max(0,self.size.y-4))

    def _pointer_down(self, point, button=0, pointer=0):
        if button != 0:
            return False
        x,y,width,height = self.thumb_rect()
        coordinate = point.y if self.vertical else point.x
        start = y if self.vertical else x
        length = height if self.vertical else width
        if start <= coordinate <= start+length:
            self._drag_offset = coordinate-start
            self._pressed = True
            self.drag_started.emit()
        else:
            self.value += (self.page or 1)*(-1 if coordinate < start else 1)
            self._pressed = False
        return True

    def _pointer_move(self, point, pointer=0):
        if not self._pressed:
            return
        _,_,width,height = self.thumb_rect()
        extent = self.size.y if self.vertical else self.size.x
        length = height if self.vertical else width
        coordinate = point.y if self.vertical else point.x
        self.ratio = max(0,min(1,(coordinate-self._drag_offset)/max(1,extent-length)))

    def _pointer_up(self, point, button=0, pointer=0):
        if self._pressed:
            self._pointer_move(point,pointer)
            self._pressed = False
            self.drag_ended.emit()

    def _wheel(self, delta):
        self.value -= delta*max(1,self.page/4)
        return True

    def render(self, target, states):
        box(target, states, (0,0,*self.size), self.theme.background, radius=4)
        tint = self.theme.muted if self._pressed or self.hovered else self.theme.border
        box(target, states, self.thumb_rect(), tint, radius=4)


class SpinBox(Range):
    def __init__(self, name=None, **options):
        super().__init__(name, **options)
        self._alignment = "center"
        self._prefix = ""
        self._suffix = ""
        self.focusable = True
        self._editing = ""
        self.focus_exited.connect(self._commit)

    def _commit(self):
        if self._editing:
            try:
                self.value = float(self._editing)
            except ValueError:
                pass
        self._editing = ""

    def _wheel(self, delta):
        self.value += delta*(self.step or 1)
        return True

    def _pointer_down(self, point, button=0, pointer=0):
        if button != 0:
            return False
        if point.x >= self.size.x-26:
            self.value += (self.step or 1)*(1 if point.y < self.size.y/2 else -1)
        return True

    def _text_input(self, text):
        if text and all(ch in "0123456789.-+eE" for ch in text):
            self._editing += text
        return True

    def _key(self, event):
        if event.type != Event.KEY_PRESSED:
            return False
        if event.code in (Keyboard.UP, Keyboard.DOWN):
            self.value += (self.step or 1)*(1 if event.code == Keyboard.UP else -1)
        elif event.code == Keyboard.BACK_SPACE:
            self._editing = self._editing[:-1]
        elif event.code == Keyboard.RETURN:
            self._commit()
        elif event.code == Keyboard.ESCAPE:
            self._editing = ""
        else:
            return False
        return True

    def render(self, target, states):
        box(target, states, (0, 0, *self.size), self.theme.background, self.theme.border, radius=self.theme.radius)
        value = self._editing if self.focused and self._editing else f"{self.value:g}"
        label(target, states, self, f"{self.prefix}{value}{self.suffix}",
              (8, 0, self.size.x-42, self.size.y), align=self.alignment)
        label(target, states, self, "+", (self.size.x-26, 0, 26, self.size.y/2), align="center")
        label(target, states, self, "-", (self.size.x-26, self.size.y/2, 26, self.size.y/2), align="center")


    @property
    def alignment(self):
        return self._alignment

    @alignment.setter
    def alignment(self, value):
        self._alignment = value

    @property
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        self._prefix = value

    @property
    def suffix(self):
        return self._suffix

    @suffix.setter
    def suffix(self, value):
        self._suffix = value
