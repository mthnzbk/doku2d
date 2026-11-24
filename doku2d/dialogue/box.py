"""The skippable typewriter dialogue control, drawn with the game's UI theme."""
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from math import isfinite
import re

from sfml.window import Event, Keyboard

from ..audio import AudioPlayer
from ..core import Signal
from ..gui import Control, LineEdit
from ..gui.theme import box, clipped, color, label, text_object, texture
from .tree import DialogueTree
from .markup import compile_markup, draw_effects


_PLACEHOLDER = re.compile(r'\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}')


@dataclass(frozen=True)
class DialogueHistoryEntry:
    speaker: str
    text: str
    kind: str = 'line'


class DialogueBox(Control):
    line_changed = Signal()
    choice_selected = Signal()
    event_triggered = Signal()
    finished = Signal()
    failed = Signal()

    def __init__(self, *, characters_per_second=45, width=720, height=260, name=None):
        super().__init__(name)
        if not all(isfinite(value) and value > 0 for value in (width, height)):
            raise ValueError('Dialogue dimensions must be positive and finite')
        self.characters_per_second = characters_per_second
        self.size = width, height
        self._preferred_size = width, height
        self.process_mode = 'always'
        self.focusable = True
        self.visible = False
        self.continue_text = 'Continue'
        self._tree = self._section = self._line = self._portrait = None
        self._section_name = None
        self._portrait_side = None
        self._line_index = 0
        self._display_text = ''
        self._markup_text = ''
        self._effects = self._pauses = ()
        self._pause_index = 0
        self._inline_wait = self._effect_time = 0.0
        self._revealed = 0.0
        self._selection = self._choice_offset = 0
        self._text_offset = None
        self._wrap_cache = None
        self._click = None
        self._revision = 0
        self._state = {}
        self._dispatching_events = False
        self._emitted_events = set()
        self._entry_pending = False
        self._advance_pending = False
        self._pending_choice = None
        self._delay = 0.0
        self._voice_buffer = self._voice_player = None
        self._voice_started = False
        self._history = []
        self._calls = []
        self._time_left = None
        self._input_entry = None
        self._input_error = ''
        self._ignore_enter_release = False
        self.subdialogue_loader = None
        self.history_open = False
        self.input_actions = None
        self._input_context = None
        self.voice_bus = 'SFX'
        self.voice_enabled = True

    @property
    def characters_per_second(self):
        return self._characters_per_second

    @characters_per_second.setter
    def characters_per_second(self, value):
        if not isfinite(value) or value < 0:
            raise ValueError('characters_per_second must be finite and nonnegative')
        self._characters_per_second = float(value)
        if not value and getattr(self, '_line', None) is not None and not self._delay:
            self.skip()

    @property
    def active(self):
        return self._line is not None

    @property
    def line(self):
        return self._line

    @property
    def display_text(self):
        """Current line after resolving its translation and state values."""
        if not self.active:
            return ''
        text = self._resolve_text(self.line, self._state)
        if text != self._markup_text:
            presentation, self._effects, self._pauses = compile_markup(text)
            if not self._delay:
                self._revealed = self._rescale_reveal(self._revealed, len(self._display_text), len(presentation))
            self._markup_text, self._display_text = text, presentation
            self._pause_index = sum(position < self._revealed for position, _ in self._pauses)
            self._inline_wait = 0
            self._text_offset = None
        return self._display_text

    @staticmethod
    def _rescale_reveal(revealed, old_length, new_length):
        if old_length == new_length:
            return revealed
        if revealed == old_length:
            return float(new_length)
        return revealed / old_length * new_length

    def _resolve_text(self, entry, state):
        text = entry.text
        if entry.translation_key is not None:
            text = self.game.localization.translate(entry.translation_key, default=text)

        def substitute(match):
            name = match[1]
            if name is None:
                return match[0][0]
            return str(state[name]) if name in state else match[0]

        return _PLACEHOLDER.sub(substitute, text)

    @property
    def visible_text(self):
        return self.display_text[:int(self._revealed)]

    @property
    def typing(self):
        text = self.display_text
        return self.active and (self._delay > 0 or self._inline_wait > 0 or self._revealed < len(text))

    @property
    def choices(self):
        if self._response_ready:
            return tuple(choice for choice in self._section.choices
                         if choice.locked_reason is not None or self.is_choice_enabled(choice))
        return ()

    @property
    def _response_ready(self):
        return self.active and not self.typing and self._line_index == len(self._section.lines)-1

    @property
    def time_left(self):
        return self._time_left if self._response_ready else None

    @property
    def history(self):
        return tuple(self._history)

    def is_choice_enabled(self, choice):
        return choice.allowed(self._state)

    def choice_text(self, choice):
        """Resolve a choice caption in the active language and dialogue state."""
        return self._resolve_text(choice, self._state)

    @property
    def portrait_side(self):
        return self._portrait_side

    def start(self, dialogue, *, section=None, state=None):
        """Show a DialogueTree or load a .dialogue file from the game's resources."""
        tree = self._load_tree(dialogue, state)
        self._show_line(tree, tree.start if section is None else section, 0,
                        new_section=True, state={} if state is None else state)
        self._history.clear()
        self._calls.clear()
        self._show_and_focus()
        self._announce_section()
        return self

    def _load_tree(self, dialogue, state):
        if self.game is None:
            raise RuntimeError('Add the DialogueBox to a Game before starting')
        if state is not None and not isinstance(state, Mapping):
            raise TypeError('Dialogue state must be a mapping')
        return dialogue if isinstance(dialogue, DialogueTree) else DialogueTree.load(dialogue, resources=self.game.resources)

    def _show_and_focus(self):
        self.visible = True
        self.grab_focus()
        if self.input_actions is not None and self._input_context is None:
            self._input_context = self.input.push_context(*self.input_actions, allow_gui=True)

    def _release_context(self):
        if self._input_context is not None:
            self.input.pop_context(self._input_context)
            self._input_context = None

    def _choice_index(self, choice):
        return next((index for index, option in enumerate(self._section.choices)
                     if option is choice), None)

    def snapshot(self):
        """Return a JSON-compatible checkpoint of the current conversation, or None."""
        if not self.active:
            return None
        options = self.choices
        selected = options[min(self._selection, len(options)-1)] if options else None
        player = self._voice_player
        return {
            'version': 1, 'section': self._section_name, 'line': self._line_index,
            'revealed': self._revealed, 'delay': self._delay,
            'text_length': len(self._display_text), 'locale': self.game.locale,
            'selected_choice': self._choice_index(selected),
            'text_offset': self._text_offset,
            'events': sorted(self._emitted_events),
            'entry_pending': self._entry_pending, 'advance_pending': self._advance_pending,
            'pending_choice': self._choice_index(self._pending_choice),
            'voice_started': self._voice_started,
            'voice_position': player.get_playback_position() if player is not None and player.playing else None,
            'history': [[item.speaker, item.text, item.kind] for item in self._history],
            'calls': [name for _, name in self._calls], 'time_left': self._time_left,
            'pause_index': self._pause_index, 'inline_wait': self._inline_wait,
        }

    def restore(self, dialogue, checkpoint, *, state=None):
        """Restore a checkpoint against its dialogue tree without replaying past events."""
        tree = self._load_tree(dialogue, state)
        if not isinstance(checkpoint, Mapping) or type(checkpoint.get('version')) is not int or checkpoint['version'] != 1:
            raise ValueError('Unsupported dialogue checkpoint')
        call_names = checkpoint.get('calls', [])
        if not isinstance(call_names, list) or len(call_names) > 32:
            raise ValueError('Invalid dialogue call stack')
        calls = []
        for caller in call_names:
            if not isinstance(caller, str) or caller not in tree.sections or tree.sections[caller].call is None:
                raise ValueError('Invalid dialogue call stack')
            calls.append((tree, caller))
            tree = self._load_call(tree, tree.sections[caller].call)
        history = checkpoint.get('history', [])
        if not isinstance(history, list) or any(not isinstance(item, list) or len(item) != 3
                                                or not all(isinstance(value, str) for value in item)
                                                or item[2] not in ('line', 'choice') for item in history):
            raise ValueError('Invalid dialogue history')
        name = checkpoint.get('section')
        index = checkpoint.get('line')
        if not isinstance(name, str) or name not in tree.sections:
            raise ValueError('Dialogue checkpoint references an unknown section')
        section = tree.sections[name]
        if type(index) is not int or not 0 <= index < len(section.lines):
            raise ValueError('Dialogue checkpoint references an unknown line')
        line = section.lines[index]

        def number(key, limit=float('inf'), *, optional=False):
            value = checkpoint.get(key)
            if value is None and optional:
                return None
            if type(value) not in (int, float) or not 0 <= value <= limit or not isfinite(value):
                raise ValueError(f'Invalid dialogue checkpoint value: {key}')
            return value

        def choice(key):
            value = checkpoint.get(key)
            if value is None:
                return None
            if type(value) is not int or not 0 <= value < len(section.choices):
                raise ValueError(f'Invalid dialogue checkpoint choice: {key}')
            return section.choices[value]

        old_length = checkpoint.get('text_length', len(line.text))
        if type(old_length) is not int or old_length < 0:
            raise ValueError('Invalid dialogue checkpoint text length')
        revealed = number('revealed', old_length)
        delay = number('delay', line.pause)
        voice_position = number('voice_position', optional=True)
        time_left = number('time_left', section.timeout[0] if section.timeout else 0, optional=True)
        inline_wait = number('inline_wait', optional=True) or 0.0
        pause_index = checkpoint.get('pause_index', 0)
        if type(pause_index) is not int or pause_index < 0:
            raise ValueError('Invalid dialogue inline pause')
        if time_left is not None and section.timeout is None:
            raise ValueError('Checkpoint references a missing choice timer')
        selection = choice('selected_choice')
        pending = choice('pending_choice')
        text_offset = checkpoint.get('text_offset')
        if text_offset is not None and (type(text_offset) is not int or text_offset < 0):
            raise ValueError('Invalid dialogue checkpoint text offset')
        events = checkpoint.get('events')
        flags = [checkpoint.get(key) for key in ('entry_pending', 'advance_pending', 'voice_started')]
        if (not isinstance(events, list)
                or any(type(entry) is not int or not 0 <= entry < len(section.events)
                       or section.events[entry][0] > index+1 for entry in events)
                or any(type(flag) is not bool for flag in flags)):
            raise ValueError('Invalid dialogue checkpoint event state')
        entry_pending, advance_pending, voice_started = flags
        if ((entry_pending and index != 0) or (advance_pending and (delay or revealed != old_length))
                or (pending is not None and (not advance_pending or index != len(section.lines)-1))
                or (delay and (revealed or voice_started)) or (voice_position is not None and not voice_started)):
            raise ValueError('Inconsistent dialogue checkpoint')

        self._show_line(tree, name, index, new_section=True, state={} if state is None else state)
        self._calls = calls
        self._history = [DialogueHistoryEntry(*item) for item in history]
        self._time_left = time_left
        new_length = len(self._display_text)
        self._revealed = 0.0 if delay else self._rescale_reveal(revealed, old_length, new_length)
        self._delay = delay
        self._entry_pending, self._advance_pending, self._voice_started = flags
        self._emitted_events.update(events)
        self._pending_choice = pending
        if new_length == old_length and checkpoint.get('locale', self.game.locale) == self.game.locale:
            self._text_offset = text_offset
            if pause_index <= len(self._pauses):
                self._pause_index = pause_index
                if pause_index and inline_wait <= self._pauses[pause_index-1][1]:
                    self._inline_wait = inline_wait
        else:
            self._pause_index = sum(position < self._revealed for position, _ in self._pauses)
        if self.choices:
            self._selection = next((i for i, option in enumerate(self.choices) if option is selection), 0)
            self._choice_offset = max(0, self._selection-self._layout_boxes()[1]+1)
        self._show_and_focus()
        if voice_position is not None and self._voice_started:
            self._start_voice(voice_position)
        return self

    def _show_line(self, tree, section_name, index, *, new_section=False, state=None):
        section = tree.sections[section_name]
        line = section.lines[index]
        side, portrait = None, None
        source = (tree.expressions.get((line.speaker, line.expression))
                  if line.expression is not None else tree.portraits.get(line.speaker))
        if source is not None:
            side, path = source
            portrait = self.game.resources.get_texture(tree.asset_path(path))
        voice = self.game.resources.get_sound(tree.asset_path(line.voice)) if self.voice_enabled and line.voice else None
        state = self._state if state is None else state
        text = self._resolve_text(line, state)
        presentation, effects, pauses = compile_markup(text)
        self._stop_voice()
        self._remove_input()
        self._tree, self._section, self._line = tree, section, line
        self._state = state
        self._markup_text, self._display_text = text, presentation
        self._effects, self._pauses = effects, pauses
        self._pause_index = 0
        self._inline_wait = self._effect_time = 0.0
        self._section_name = section_name
        self._line_index = index
        self._portrait, self._portrait_side = portrait, side
        self._delay = line.pause
        self._time_left = None
        self._voice_buffer = voice
        self._voice_started = False
        self._revealed = 0.0 if self.characters_per_second or self._delay else len(presentation)
        self._selection = self._choice_offset = 0
        self._text_offset = self._wrap_cache = None
        self._entry_pending = new_section
        self._advance_pending = False
        self._pending_choice = None
        if new_section:
            self._emitted_events.clear()
        self._revision += 1

    def _start_voice(self, offset=0.0):
        self._voice_started = True
        buffer = self._voice_buffer
        if buffer is None or not self.voice_enabled or offset >= buffer.duration.seconds:
            return
        game = self.game
        player = self._voice_player
        if player is None or (player.game is not game and player._pending_game is not game):
            player = self._voice_player = AudioPlayer(bus=self.voice_bus)
            player.process_mode = 'always'
            with game._using_scope(self.scope):
                game.add(player)
        player.bus = self.voice_bus
        player.audio = buffer
        player.play(offset)

    def _stop_voice(self):
        if self._voice_player is not None:
            self._voice_player.stop()

    def on_removed(self):
        self._stop_voice()
        self._remove_input()
        self._release_context()
        player, self._voice_player = self._voice_player, None
        if player is not None and not self.game.closed and (player.game is self.game or player._pending_game is self.game):
            self.game.remove(player)
        super().on_removed()

    def close(self):
        if self.active:
            self._stop_voice()
            self._remove_input()
            self._release_context()
            self._tree = self._section = self._line = self._portrait = None
            self._voice_buffer = None
            self._portrait_side = None
            self._state = {}
            self._calls.clear()
            self._time_left = None
            self._revision += 1
            self.release_focus()
            self.visible = False
            self.finished.emit()

    def skip(self):
        if self.typing:
            self._delay = 0
            self._revealed = len(self._display_text)
            self._pause_index = len(self._pauses)
            self._inline_wait = 0
            if not self._voice_started:
                self._start_voice()

    def confirm(self):
        """Finish typing, advance one line, or confirm the selected choice."""
        if not self.active or self._advance_pending or self._dispatching_events or self.history_open:
            return False
        if self.typing:
            self.skip()
        elif self._response_ready and self._section.input is not None:
            self._refresh_input()
        elif self._response_ready and self._section.choices:
            if self.choices:
                return self.choose(min(self._selection, len(self.choices)-1))
            if self._section.timeout is not None:
                return False
            self._advance_pending = True
            self._complete_advance()
        else:
            self._advance_pending = True
            self._complete_advance()
        return True

    def choose(self, index):
        options = self.choices
        if self._advance_pending or type(index) is not int or not 0 <= index < len(options):
            return False
        choice = options[index]
        if not self.is_choice_enabled(choice) or self.history_open:
            return False
        revision = self._revision
        self._advance_pending = True
        self._pending_choice = choice
        self.choice_selected.emit(choice)
        if self._revision == revision:
            self._complete_advance()
        return True

    def _complete_advance(self):
        line_text = self.display_text
        choice = self._pending_choice
        reply = self.choice_text(choice) if choice is not None else None
        if not self._emit_events(self._line_index+1):
            return
        self._history.append(DialogueHistoryEntry(self.line.speaker, line_text))
        if choice is not None:
            self._history.append(DialogueHistoryEntry('', reply, 'choice'))
            self._follow(choice.target)
        elif self._line_index + 1 < len(self._section.lines):
            self._show_line(self._tree, self._section_name, self._line_index+1)
            self._announce_line()
        else:
            self._advance_section()

    def _advance_section(self):
        if self._time_left == 0 and self._section.timeout is not None:
            self._follow(self._section.timeout[1])
        elif self._section.call is not None:
            try:
                if len(self._calls) >= 32:
                    raise RuntimeError('Dialogue call depth exceeds 32')
                tree = self._load_call(self._tree, self._section.call)
                parent = self._tree, self._section_name
                self._show_line(tree, self._section.call.entry, 0, new_section=True)
            except (ValueError, OSError, RuntimeError) as error:
                self.close()
                self.failed.emit(error)
                return
            self._calls.append(parent)
            self._announce_section()
        else:
            target = next((branch.target for branch in self._section.branches if branch.allowed(self._state)),
                          self._section.next_section)
            self._follow(target)

    def _load_call(self, tree, call):
        path = tree.asset_path(call.path)
        child = (DialogueTree.load(path, resources=self.game.resources) if self.subdialogue_loader is None
                 else self.subdialogue_loader(path))
        if call.entry not in child.sections:
            raise ValueError(f'{child.source}: Unknown section {call.entry!r}')
        return child

    def _follow(self, target):
        tree = self._tree
        while target is None and self._calls:
            tree, caller = self._calls.pop()
            target = tree.sections[caller].call.return_to
        if target is None:
            self.close()
        else:
            self._show_line(tree, target, 0, new_section=True)
            self._announce_section()

    def submit_input(self, text):
        """Validate and store a response in the current dialogue state."""
        if (self.history_open or not self._response_ready or self._section.input is None
                or self._advance_pending or self._dispatching_events):
            return False
        rule = self._section.input
        try:
            value = rule.parse(text)
            if not isinstance(self._state, MutableMapping):
                raise ValueError('Dialogue input requires a mutable state mapping')
        except ValueError as error:
            self._input_error = str(error)
            return False
        self._state[rule.key] = value
        self._advance_pending = True
        self._complete_advance()
        if self.active:
            self.grab_focus()
        return True

    def _refresh_input(self):
        if self._input_entry is None:
            entry = LineEdit()
            entry.placeholder = self._section.input.prompt
            entry.text_submitted.connect(self._submit_entry)
            entry.z_index = self.z_index+1
            entry.process_mode = 'always'
            self._input_entry = self.game.add(entry, canvas=self.canvas, scope=self.scope)
            self.game.call_deferred(self._focus_input, entry)
        self._arrange_input()

    def _submit_entry(self, text):
        if self.submit_input(text):
            self._ignore_enter_release = True

    def focus_response(self):
        """Restore focus after closing a secondary dialogue panel."""
        entry = self._input_entry
        if entry is not None and entry.game is self.game:
            entry.grab_focus()
        elif self.active:
            self.grab_focus()

    def _focus_input(self, entry):
        if self._input_entry is entry and entry.game is self.game:
            entry.grab_focus()

    def _arrange_input(self):
        if self._input_entry is not None:
            x, y, width, height = self._layout_boxes()[2]
            self._input_entry.position = self.position.x+x, self.position.y+y
            self._input_entry.size = width, height

    def _remove_input(self):
        entry, self._input_entry = self._input_entry, None
        self._input_error = ''
        if entry is not None and not self.game.closed and (entry.game is self.game or entry._pending_game is self.game):
            self.game.remove(entry)

    def _announce_section(self):
        if self._emit_events(0):
            self._entry_pending = False
            self._announce_line()

    def _announce_line(self):
        if not self._delay:
            self._start_voice()
        self.line_changed.emit(self.line)

    def _emit_events(self, boundary):
        if self._dispatching_events:
            return False
        revision = self._revision
        self._dispatching_events = True
        try:
            for index, (when, event) in enumerate(self._section.events):
                if when == boundary and index not in self._emitted_events:
                    self._emitted_events.add(index)
                    self.event_triggered.emit(event)
                    if self._revision != revision:
                        return False
            return True
        finally:
            self._dispatching_events = False

    def arrange(self):
        if self.game is not None:
            width, height = self.game.size
            margin = min(18, width*.04, height*.04)
            self.size = tuple(min(preferred, available-2*margin)
                              for preferred, available in zip(self._preferred_size, (width, height)))
            self.position = (round((width-self.size.x)/2), round(height-self.size.y-margin))
            self._arrange_input()

    def update(self, dt):
        if not self.active or self.history_open:
            return
        if self._entry_pending:
            if not self._emit_events(0):
                return
            self._entry_pending = False
        if self._advance_pending:
            self._complete_advance()
            return
        self._effect_time += dt
        if self._delay:
            elapsed = min(dt, self._delay)
            self._delay -= elapsed
            dt -= elapsed
            if self._delay > 0:
                return
        if not self._voice_started:
            self._start_voice()
        was_typing = self.typing
        if was_typing:
            self._advance_typewriter(dt)
        if self.choices:
            self._selection = min(self._selection, len(self.choices)-1)
            self._choice_offset = min(self._choice_offset, self._selection)
        if self._response_ready:
            if self._section.input is not None:
                self._refresh_input()
            if self._section.timeout is not None:
                if self._time_left is None:
                    self._time_left = self._section.timeout[0]
                if not was_typing:
                    self._time_left = max(0, self._time_left-dt)
                if self._time_left == 0:
                    self._advance_pending = True
                    self._complete_advance()

    def _advance_typewriter(self, dt):
        rate = self.characters_per_second
        length = len(self._display_text)
        if not rate:
            self._revealed = length
            self._inline_wait = 0
            return
        while True:
            elapsed = min(dt, self._inline_wait)
            self._inline_wait -= elapsed
            dt -= elapsed
            if self._inline_wait:
                return
            if self._pause_index >= len(self._pauses):
                self._revealed = min(length, self._revealed+dt*rate)
                return
            position, seconds = self._pauses[self._pause_index]
            travel = max(0, position-self._revealed)/rate
            if travel > dt:
                self._revealed += dt*rate
                return
            self._revealed = max(self._revealed, position)
            self._pause_index += 1
            self._inline_wait = seconds
            dt -= travel

    def _layout_boxes(self):
        width, height = self.size
        pad = min(16, width*.075, height*.09)
        row = min(self.font_size+12, height*.26)
        shown = max(1, min(len(self.choices), 4, int(height*.40/row)))
        footer = (pad, height-pad-shown*row, width-2*pad, row)
        heading = row if self.active and self.line.speaker else 0
        portrait_width = min(128, width*.24, height*.45) if self._portrait is not None else 0
        gutter = portrait_width + pad if portrait_width else 0
        x = pad + gutter if self.portrait_side == 'left' else pad
        body = (x, pad+heading, max(1, width-2*pad-gutter), max(0, footer[1]-2*pad-heading))
        return pad, shown, footer, body, portrait_width

    def _wrap(self, width):
        font = self.font or self.theme.get_font()
        key = self.display_text, width, self.font_size, id(font)
        if self._wrap_cache is not None and self._wrap_cache[0] == key:
            return self._wrap_cache[1]

        rows = []
        offset = 0
        for paragraph in self._display_text.split('\n'):
            start, end = 0, 0
            for word in re.finditer(r'\S+', paragraph):
                pos, stop = word.span()
                if end > start and self._width(paragraph[start:stop]) > width:
                    rows.append((offset+start, offset+end))
                    start = pos
                while self._width(paragraph[start:stop]) > width and stop-start > 1:
                    # Split a single long token at the largest prefix that fits.
                    low, high = start+1, stop
                    while low+1 < high:
                        mid = (low+high)//2
                        if self._width(paragraph[start:mid]) <= width:
                            low = mid
                        else:
                            high = mid
                    rows.append((offset+start, offset+low))
                    start = low
                end = stop
            rows.append((offset+start, offset+end))
            offset += len(paragraph)+1
        self._wrap_cache = key, rows
        return rows

    def _width(self, text):
        return text_object(self, text).find_character_pos(len(text)).x

    def _draw_text(self, target, states, body):
        x, y, width, height = body
        rows = self._wrap(width)
        pitch = self.font_size * 1.42
        visible_rows = max(1, int(height/pitch))
        reveal = int(self._revealed)
        limit = sum(start < reveal for start, _ in rows)
        last_page = max(0, limit-visible_rows)
        offset = last_page if self._text_offset is None else min(last_page, self._text_offset)
        baseline = text_object(self, 'Hg').local_bounds.position.y
        with clipped(target, states, body) as draw:
            if draw:
                for index, (start, end) in enumerate(rows[offset:offset+visible_rows]):
                    if start >= reveal:
                        break
                    value = self._display_text[start:min(end,reveal)]
                    position = (x, y+index*pitch-baseline)
                    if self._effects:
                        draw_effects(self, target, states, value, start, position, self._effects, self._effect_time)
                    else:
                        text = text_object(self, value)
                        text.position = position
                        text.fill_color = color(self.theme.text)
                        target.draw(text, states)

    def render(self, target, states):
        if not self.active:
            return
        theme = self.theme
        pad, shown, footer, body, edge = self._layout_boxes()
        box(target, states, (0, 0, *self.size), theme.background, theme.border, radius=theme.radius+4)
        if self._portrait is not None:
            px = pad if self.portrait_side == 'left' else self.size.x-pad-edge
            box(target, states, (px, pad, edge, edge), theme.surface, theme.border, radius=theme.radius)
            pw, ph = self._portrait.size
            scale = min(max(0, edge-4)/pw, max(0, edge-4)/ph)
            sw, sh = pw*scale, ph*scale
            texture(target, states, self._portrait, (px+(edge-sw)/2, pad+(edge-sh)/2, sw, sh))
        if self.line.speaker:
            heading = (body[0], pad, body[2], footer[3])
            with clipped(target, states, heading) as draw:
                if draw:
                    label(target, states, self, self.line.speaker, heading, tint=theme.accent)
        self._draw_text(target, states, body)
        if self.time_left is not None:
            _, y, _, row = footer
            label(target, states, self, f'{self.time_left:.1f} s', (self.size.x-94, y-row, 76, row), align='right')
        if self.choices:
            for index in range(self._choice_offset, min(len(self.choices), self._choice_offset+shown)):
                self._draw_choice(target, states, footer, index)
        elif self._response_ready and self._section.input is not None:
            x, y, width, height = footer
            label(target, states, self, self._input_error, (x, y-height, width, height), tint=theme.accent)
        elif not self.typing and self.time_left is None:
            x, y, w, h = footer
            box(target, states, (x, y, w, h), theme.surface, theme.border, radius=theme.radius)
            label(target, states, self, self.localize(self.continue_text), footer, align='center')

    def _draw_choice(self, target, states, footer, index):
        theme = self.theme
        x, y, w, h = footer
        rect = (x, y+(index-self._choice_offset)*h, w, h-2)
        selected = index == self._selection
        choice = self.choices[index]
        enabled = self.is_choice_enabled(choice)
        box(target, states, rect, theme.active if selected else theme.surface,
            theme.accent if selected else theme.border, radius=theme.radius)
        with clipped(target, states, rect) as draw:
            if draw:
                text = self.choice_text(choice)
                if not enabled:
                    text = f'{text} · {choice.locked_reason}'
                label(target, states, self, text, (rect[0]+theme.padding, rect[1], rect[2]-theme.padding, rect[3]),
                      tint=None if enabled else theme.muted)

    def _move_selection(self, amount):
        if self.choices:
            self._selection = (self._selection+amount) % len(self.choices)
            shown = self._layout_boxes()[1]
            self._choice_offset = max(self._selection-shown+1, min(self._choice_offset, self._selection))

    def _scroll_text(self, amount):
        if not self.typing:
            body = self._layout_boxes()[3]
            last_page = max(0, len(self._wrap(body[2]))-max(1, int(body[3]/(self.font_size*1.42))))
            offset = last_page if self._text_offset is None else self._text_offset
            self._text_offset = max(0, min(last_page, offset+amount))

    def _key(self, event):
        key = event.code
        if key == Keyboard.RETURN and self._ignore_enter_release:
            self._ignore_enter_release = False
            if event.type == Event.KEY_RELEASED:
                return True
        if key in (Keyboard.RETURN, Keyboard.SPACE, Keyboard.ESCAPE):
            if event.type == Event.KEY_RELEASED:
                self.close() if key == Keyboard.ESCAPE else self.confirm()
            return True
        if key in (Keyboard.UP, Keyboard.DOWN, Keyboard.PAGE_UP, Keyboard.PAGE_DOWN):
            if event.type == Event.KEY_PRESSED:
                amount = -1 if key in (Keyboard.UP, Keyboard.PAGE_UP) else 1
                if key in (Keyboard.PAGE_UP, Keyboard.PAGE_DOWN):
                    self._scroll_text(amount)
                else:
                    self._move_selection(amount)
            return True
        return False

    def _wheel(self, delta):
        if delta:
            amount = -1 if delta > 0 else 1
            if self.choices:
                self._move_selection(amount)
            else:
                self._scroll_text(amount)

    def _target_at(self, point):
        _, shown, footer, _, _ = self._layout_boxes()
        x, y, w, h = footer
        if self.choices:
            if x <= point.x < x+w and y <= point.y < y+shown*h:
                index = self._choice_offset+int((point.y-y)/h)
                return self.choices[index] if index < len(self.choices) else None
            return None
        return 'skip' if self.typing else 'continue'

    def _pointer_down(self, point, button=0, pointer=0):
        if button == 0:
            self._click = pointer, self._target_at(point), self._revision
            return True
        return False

    def _pointer_up(self, point, button=0, pointer=0):
        click, self._click = self._click, None
        if (click is None or button != 0 or click[0] != pointer or click[2] != self._revision
                or not 0 <= point.x < self.size.x or not 0 <= point.y < self.size.y):
            return
        action = click[1]
        if action == 'skip':
            self.skip()
        elif action == 'continue' and not self.choices:
            self.confirm()
        elif action is not None and action is self._target_at(point):
            self.choose(next(index for index, option in enumerate(self.choices) if option is action))

    def _cancel_pointer(self):
        self._click = None
