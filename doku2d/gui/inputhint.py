"""A label that follows input bindings and the active input device."""
from .text import Label
from .theme import box, disk, label


class InputHint(Label):
    def __init__(self, action, *, caption='', name=None):
        super().__init__(name)
        self.action = action
        self.caption = caption
        self.process_mode = 'always'

    def update(self, dt):
        hint = self.input.binding_hint(self.action)
        text = f'{hint}  {self.localize(self.caption)}'.rstrip()
        if self.text != text:
            self.text = text

    def render(self, target, states):
        if not self.text.startswith('Gamepad '):
            super().render(target, states)
            return
        y = self.size.y/2
        box(target, states, (2, y-7, 21, 14), self.theme.surface, self.theme.border, radius=5)
        box(target, states, (6, y-1, 6, 2), self.theme.text)
        box(target, states, (8, y-3, 2, 6), self.theme.text)
        disk(target, states, (17, y), 2, self.theme.accent)
        label(target, states, self, self.text, (30, 0, max(0, self.size.x-30), self.size.y))
