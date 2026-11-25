"""Synchronize the Android input method with the focused Doku2D editor."""

from itertools import count
import json

from .text import LineEdit, TextEdit


_SESSIONS = count(1)


class AndroidKeyboard:
    def __init__(self, native):
        self.native = native
        self.editor = None
        self.session = 0
        self.sent = None
        self.reopen = False
        self.viewport_height = 0

    def update(self, ui):
        self.viewport_height = self.native.keyboard_viewport_height()
        focus = ui.focus
        editor = focus if isinstance(focus, (LineEdit, TextEdit)) and focus.editable else None
        show = self.reopen
        self.reopen = False
        if editor is not self.editor:
            self.editor = editor
            self.session = next(_SESSIONS)
            self.sent = None
            if editor is None:
                self.native.configure_keyboard(self.session, 0, "", 0, 0, False)
            else:
                show = True
        if editor is None:
            return

        # The Java editor supplies complete text, including composed characters,
        # and selection changes. Ignore events left over from a previous focus.
        for _ in range(128):
            event = self.native.take_keyboard_event()
            if event is None:
                break
            session, text, anchor, cursor, submitted = json.loads(event)
            if session != self.session or ui.focus is not editor:
                continue
            mode = self.sent[0] if self.sent else self._mode(editor)
            self.sent = (mode, text, anchor, cursor)
            editor._apply_android_edit(text, anchor, cursor)
            if submitted and ui.focus is editor and isinstance(editor, LineEdit):
                editor.text_submitted.emit(editor.text)

        if ui.focus is editor:
            state = (self._mode(editor), editor.text, editor._selection_anchor, editor.cursor)
            if show or state != self.sent:
                self.native.configure_keyboard(self.session, *state, show)
                self.sent = state

    @staticmethod
    def _mode(editor):
        if isinstance(editor, TextEdit):
            return 2
        return 3 if editor.secret else 1
