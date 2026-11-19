from math import atan2, degrees, hypot
from sfml.graphics import RectangleShape
from sfml.window import Event, Keyboard
from ..core import Signal
from .base import Control
from .theme import box, disk, label, texture, mix, color


class BaseButton(Control):
    toggled = Signal()
    pressed = Signal()
    button_up = Signal()
    button_down = Signal()

    def __init__(self, name=None, *, text="", fit_text=False):
        super().__init__(name)
        self._text = self._caption(text)
        self.fit_text = bool(fit_text)
        self._toggle_mode = False
        self._button_pressed = False
        self._text_alignment = "center"
        self._icon = None
        self._icon_alignment = "left"
        self.focusable = True
        self._hover_blend = 0.0
        self._toggle_blend = 0.0

    @property
    def toggle_mode(self):
        return self._toggle_mode

    @toggle_mode.setter
    def toggle_mode(self, value):
        self._toggle_mode = bool(value)

    @property
    def text_alignment(self):
        return self._text_alignment

    @text_alignment.setter
    def text_alignment(self, value):
        self._text_alignment = value

    @property
    def icon(self):
        return self._icon

    @icon.setter
    def icon(self, value):
        self._icon = value

    @property
    def icon_alignment(self):
        return self._icon_alignment

    @icon_alignment.setter
    def icon_alignment(self, value):
        self._icon_alignment = value



    @property
    def text(self):
        return self.localize(self._text)

    @text.setter
    def text(self, value):
        self._text = self._caption(value)

    @property
    def button_pressed(self):
        return self._button_pressed

    @button_pressed.setter
    def button_pressed(self, value):
        value = bool(value)
        if value != self._button_pressed:
            self._button_pressed = value
            self.toggled.emit(value)

    def _activate(self):
        if self.toggle_mode:
            self.button_pressed = not self.button_pressed
        self.pressed.emit()

    def _pointer_down(self, point, button=0, pointer=0):
        if button != 0:
            return False
        self._pressed = True
        self.button_down.emit()
        return True

    def _pointer_up(self, point, button=0, pointer=0):
        was_pressed = self._pressed
        self._pressed = False
        if was_pressed:
            self.button_up.emit()
            if button == 0 and 0 <= point.x < self.size.x and 0 <= point.y < self.size.y:
                self._activate()

    def _cancel_pointer(self):
        if self._pressed:
            self._pressed = False
            self.button_up.emit()

    def _key(self, event):
        if event.code not in (Keyboard.RETURN, Keyboard.SPACE):
            return False
        if event.type == Event.KEY_PRESSED and not self._pressed:
            self._pressed = True
            self.button_down.emit()
        elif event.type == Event.KEY_RELEASED and self._pressed:
            self._pressed = False
            self.button_up.emit()
            self._activate()
        return True

    def update(self, dt):
        speed = min(1, dt*16)
        self._hover_blend += (float(self.hovered)-self._hover_blend)*speed
        self._toggle_blend += (float(self.button_pressed)-self._toggle_blend)*speed

    @property
    def _caption_width_extra(self):
        return max(0, min(self.size.y-12, 24)) + 8 if self.icon is not None else 0

    def render(self, target, states):
        theme = self.theme
        fill = theme.disabled if self.disabled else (
            theme.active if self._pressed or self.button_pressed else mix(theme.surface, theme.hover, self._hover_blend))
        box(target, states, (0, 2, *self.size), (0, 0, 0, 35), radius=theme.radius)
        box(target, states, (0, 0, *self.size), fill, theme.border, radius=theme.radius)
        left = theme.padding
        width = self.size.x-2*left
        if self.icon is not None:
            edge = min(self.size.y-12, 24)
            x = left if self.icon_alignment == "left" else self.size.x-left-edge
            texture(target, states, self.icon, (x, (self.size.y-edge)/2, edge, edge))
            if self.icon_alignment == "left":
                left += edge+8
            width -= edge+8
        label(target, states, self, self.text, (left, 0, width, self.size.y),
              align=self.text_alignment, tint=theme.muted if self.disabled else theme.text)


class Button(BaseButton):
    pass


class CheckBox(BaseButton):
    _caption_width_extra = 32

    def __init__(self, name=None, *, text="", fit_text=False):
        super().__init__(name, text=text, fit_text=fit_text)
        self._toggle_mode = True
        self.show_focus = False

    def render(self, target, states):
        y = round((self.size.y-20)/2)
        if self.button_pressed:
            fill = self.theme.disabled if self.disabled else self.theme.accent
            box(target,states,(1,y,20,20),fill,radius=5)
            tint = self.theme.muted if self.disabled else self.theme.background
            points = ((6,y+10),(10,y+14),(17,y+6))
            for first,second in zip(points,points[1:]):
                dx,dy = second[0]-first[0],second[1]-first[1]
                stroke = RectangleShape((hypot(dx,dy),2.4))
                stroke.origin = (0,1.2)
                stroke.position = first
                stroke.rotation = degrees(atan2(dy,dx))
                stroke.fill_color = color(tint)
                target.draw(stroke,states)
            for point in points:
                disk(target,states,point,1.2,tint)
        else:
            border = self.theme.muted if self.hovered and not self.disabled else self.theme.border
            box(target,states,(1,y,20,20),self.theme.background,border,radius=5)
        label(target,states,self,self.text,(32,0,self.size.x-32,self.size.y),
              tint=self.theme.muted if self.disabled else self.theme.text)


class CheckButton(CheckBox):
    _caption_width_extra = 52

    def render(self, target, states):
        y = (self.size.y-22)/2
        box(target, states, (1, y, 40, 22), mix(self.theme.border,self.theme.active,self._toggle_blend), radius=11)
        disk(target, states, (12+18*self._toggle_blend, y+11), 8,
             self.theme.accent if self.button_pressed else self.theme.muted)
        label(target, states, self, self.text, (52, 0, self.size.x-52, self.size.y))


class TextureButton(BaseButton):
    def __init__(self, name=None):
        super().__init__(name)
        self._texture_normal = None
        self._texture_hover = None
        self._texture_pressed = None
        self._texture_disabled = None

    @property
    def texture_normal(self):
        return self._texture_normal

    @texture_normal.setter
    def texture_normal(self, value):
        self._texture_normal = value

    @property
    def texture_hover(self):
        return self._texture_hover

    @texture_hover.setter
    def texture_hover(self, value):
        self._texture_hover = value

    @property
    def texture_pressed(self):
        return self._texture_pressed

    @texture_pressed.setter
    def texture_pressed(self, value):
        self._texture_pressed = value

    @property
    def texture_disabled(self):
        return self._texture_disabled

    @texture_disabled.setter
    def texture_disabled(self, value):
        self._texture_disabled = value

    def render(self, target, states):
        image = self.texture_normal
        if self.disabled:
            image = self.texture_disabled or image
        elif self._pressed or self.button_pressed:
            image = self.texture_pressed or image
        elif self.hovered:
            image = self.texture_hover or image
        if image is None:
            super().render(target, states)
        else:
            texture(target, states, image, (0, 0, *self.size))
