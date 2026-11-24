"""Pointer drag sessions, with an optional caption or image preview."""
from dataclasses import dataclass
from math import hypot

from sfml.graphics import RenderStates, Texture

from ..rendering.atlas import AtlasRegion
from .theme import box, label, texture


@dataclass(frozen=True)
class DragData:
    data: object
    preview: str | Texture | AtlasRegion | None = None


@dataclass
class _Drag:
    source: object
    pointer: int
    position: tuple
    payload: DragData
    target: object = None


class _DragDrop:
    def __init__(self, ui):
        self.ui = ui
        self.candidate = None
        self.active = None
        self._suppressed = set()

    @property
    def target(self):
        return self.active.target if self.active is not None else None

    def _usable(self, control):
        return (control.game is self.ui.game and control not in self.ui.game._removing
                and control.visible and not control.disabled and control.can_process())

    def arm(self, source, pointer, position):
        if self.candidate is None and self.active is None and self._usable(source):
            self.candidate = source, pointer, position

    def release(self, control):
        if self.candidate is not None and self.candidate[0] is control:
            self.candidate = None
        if self.active is not None:
            if self.active.source is control:
                self.cancel()
            elif self.active.target is control:
                self.active.target = None

    def prune(self):
        if self.candidate is not None and not self._usable(self.candidate[0]):
            self.candidate = None
        if self.active is not None:
            if not self._usable(self.active.source):
                self.cancel()
            elif self.target is not None and not self._usable(self.target):
                self.active.target = None

    def cancel(self, *, lost_focus=False):
        self.candidate = None
        drag, self.active = self.active, None
        if lost_focus:
            self._suppressed.clear()
        elif drag is not None and drag.pointer in self.ui._down_pointers:
            self._suppressed.add(drag.pointer)
        if drag is not None:
            drag.source.drag_finished.emit(drag.payload.data, False)

    def _drop_target(self, drag, position, inside):
        control = self.ui._hit(position) if inside else None
        if control is not None and self._usable(control):
            if control.can_drop_data(control.local_point(position), drag.payload.data) and self._usable(control):
                return control
        return None

    def pointer(self, pointer, position, *, inside, moved, released):
        if pointer in self._suppressed:
            if released:
                self._suppressed.discard(pointer)
            return True
        if self.active is None and self.candidate is not None and self.candidate[1] == pointer:
            source, _, origin = self.candidate
            if released:
                self.candidate = None
            elif moved and hypot(position[0]-origin[0], position[1]-origin[1]) >= 5:
                self.candidate = None
                payload = source.get_drag_data(source.local_point(origin))
                if payload is None or not self._usable(source):
                    return False
                if not isinstance(payload, DragData):
                    payload = DragData(payload)
                self.ui.capture.pop(pointer, source)._cancel_pointer()
                if not self._usable(source):
                    self._suppressed.add(pointer)
                    return True
                self.active = _Drag(source, pointer, position, payload)
                source.drag_started.emit(payload.data)
                if self.active is None:
                    return True
        drag = self.active
        if drag is None or drag.pointer != pointer:
            return False
        if moved or released:
            drag.position = position
            try:
                drag.target = self._drop_target(drag, position, inside)
            except Exception:
                self.cancel()
                raise
        if released and self.active is drag:
            self.active = None
            accepted = False
            try:
                if drag.target is not None:
                    drag.target.drop_data(drag.target.local_point(position), drag.payload.data)
                    accepted = True
            finally:
                drag.source.drag_finished.emit(drag.payload.data, accepted)
        return True

    def draw(self, target):
        drag = self.active
        if drag is None:
            return
        original = target.view
        game, theme = self.ui.game, self.ui.theme
        try:
            if drag.target is not None:
                control = drag.target
                target.view = game.make_view(control.canvas or game.world)
                states = RenderStates(transform=control.render_transform)
                box(target, states, (2, 2, control.size.x-4, control.size.y-4), (0, 0, 0, 0),
                    theme.accent, 2, radius=theme.radius)
            target.view = game._pixel_view(game.size)
            states = RenderStates()
            preview = drag.payload.preview
            image = isinstance(preview, (Texture, AtlasRegion))
            if not image:
                preview = preview if isinstance(preview, str) else getattr(drag.source, 'text', drag.source.name)
                preview = str(preview).split('\n', 1)[0]
                if len(preview) > 24:
                    preview = preview[:23] + '…'
            x, y = drag.position
            w = min(game.size.x, 48 if image else max(56, len(preview)*drag.source.font_size*.64+20))
            h = min(game.size.y, 48 if image else drag.source.font_size+16)
            rect = (max(0, min(game.size.x-w, x+13)), max(0, min(game.size.y-h, y+13)), w, h)
            box(target, states, rect, theme.surface, theme.accent, radius=theme.radius)
            if image:
                pw, ph = preview.size
                scale = max(0, min((w-8)/pw, (h-8)/ph))
                texture(target, states, preview,
                        (rect[0]+(w-pw*scale)/2, rect[1]+(h-ph*scale)/2, pw*scale, ph*scale))
            else:
                label(target, states, drag.source, preview, rect, align='center')
        finally:
            target.view = original
