"""Optional dialogue presentation controls."""
from math import isfinite

from ..gui import Control, ItemList
from ..gui.theme import box, clipped, label, measure
from .box import DialogueHistoryEntry


class DialogueHistory(ItemList):
    def __init__(self, dialogue):
        super().__init__()
        self.dialogue = dialogue
        self.visible = False
        self.process_mode = 'always'
        self._shown = None

    def open(self):
        self.dialogue.history_open = self.visible = True
        self._refresh()
        self.grab_focus()

    def close(self):
        self.visible = self.dialogue.history_open = False
        self.release_focus()
        self.dialogue.focus_response()

    def _refresh(self):
        history = self.dialogue.history
        if self.dialogue.visible_text:
            history = (*history, DialogueHistoryEntry(self.dialogue.line.speaker, self.dialogue.visible_text))
        if history != self._shown:
            self._shown = history
            self.items = [f'↳ {entry.text}' if entry.kind == 'choice' else
                          f'{entry.speaker}: {entry.text}' if entry.speaker else entry.text for entry in history]
            if not self.items:
                self.add_item('Geçmiş boş')
            if self.items:
                self.select(len(self.items)-1)

    def update(self, dt):
        super().update(dt)
        if self.visible:
            self._refresh()

    def on_removed(self):
        self.dialogue.history_open = False
        super().on_removed()


class SpeechBubble(Control):
    """A brief localized line anchored to a world entity."""
    def __init__(self, target, text='', *, offset=(0, -24), duration=2.5, characters_per_second=40):
        super().__init__()
        self.target = target
        self.offset = self._vector(offset)
        if not isfinite(characters_per_second) or characters_per_second < 0:
            raise ValueError('Bubble typing speed must be finite and nonnegative')
        self.characters_per_second = characters_per_second
        self.mouse_filter = 'ignore'
        self.process_mode = 'always'
        self.say(text, duration=duration)

    def say(self, text, *, duration=2.5):
        if not isfinite(duration) or duration < 0:
            raise ValueError('Bubble duration must be finite and nonnegative')
        self.text = text
        self._elapsed = 0.0
        self._duration = duration
        self.visible = False

    def update(self, dt):
        self._elapsed += dt
        text = self.localize(self.text)
        rate = self.characters_per_second
        self._shown = text[:int(self._elapsed*rate)] if rate else text
        expires = self._duration + (len(text)/rate if rate else 0)
        self.visible = bool(text) and self.target.game is self.game and self._elapsed < expires
        if self.visible:
            self.arrange()

    def arrange(self):
        if not self.visible or self.target.game is not self.game:
            return
        anchor = self._anchor_point()
        text = self.localize(self.text)
        width = min(self.game.size.x, max(76, measure(self, text)+24))
        height = self.font_size+20
        self.size = width, height
        self.position = min(max(0, anchor.x-width/2), self.game.size.x-width), max(0, anchor.y-height)

    def _anchor_point(self):
        x, y = self.target.position
        dx, dy = self.offset
        return self.game.world_to_screen((x+dx, y+dy), self.target.canvas)

    def render(self, target, states):
        anchor = self._anchor_point()
        if not (0 <= anchor.x <= self.game.size.x and 0 <= anchor.y <= self.game.size.y):
            return
        box(target, states, (0, 0, *self.size), self.theme.surface, self.theme.border, radius=self.theme.radius)
        with clipped(target, states, (0, 0, *self.size)) as draw:
            if draw:
                label(target, states, self, self._shown, (10, 0, self.size.x-20, self.size.y), align='center')
