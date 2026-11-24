"""Read Doku2D dialogue files into a validated graph of named sections."""
from dataclasses import dataclass, replace
import json
from math import isfinite
from pathlib import Path
import re
import shlex
from types import MappingProxyType


_ID = re.compile(r'[A-Za-z_][A-Za-z0-9_.-]*\Z')
_END = 'END'
_TARGET = re.compile(r'([^\s]+)(?:\s+\[if\s+(.+)\])?\Z')
_CONDITION = re.compile(r'(not\s+)?([A-Za-z_][A-Za-z0-9_.-]*)(?:\s*(==|!=)\s*(.+))?\Z')
_LOCK = re.compile(r'\s+\[locked\s+("(?:[^"\\]|\\.)*")\]\Z')
_TRANSLATION = re.compile(r'\[tr\s+([A-Za-z_][A-Za-z0-9_.-]*)\]\s+(.+)')


class DialogueFormatError(ValueError):
    """A dialogue file has a syntax error or an unresolved branch."""


@dataclass(frozen=True)
class DialogueAssetReference:
    source: str
    line: int
    path: str


@dataclass(frozen=True)
class DialogueTranslationReference:
    source: str
    line: int
    key: str


@dataclass(frozen=True)
class DialogueLine:
    speaker: str
    text: str
    expression: str | None = None
    pause: float = 0.0
    voice: str | None = None
    translation_key: str | None = None


@dataclass(frozen=True)
class DialogueChoice:
    text: str
    target: str | None
    condition: tuple | None = None
    translation_key: str | None = None
    locked_reason: str | None = None
    source_line: int = 0

    def allowed(self, state):
        if self.condition is None:
            return True
        key, compare, *value = self.condition
        if not value:
            return bool(state.get(key)) == compare
        return (state.get(key) == value[0]) == compare


@dataclass(frozen=True)
class DialogueCall:
    path: str
    entry: str
    return_to: str | None = None


@dataclass(frozen=True)
class DialogueInput:
    key: str
    kind: str
    prompt: str
    minimum: float | None = None
    maximum: float | None = None

    def parse(self, text):
        text = str(text).strip()
        if not text:
            raise ValueError('Enter a value')
        if self.kind == 'number':
            value = float(text)
            if not isfinite(value):
                raise ValueError('Enter a finite number')
            value = int(value) if value.is_integer() else value
            size = value
        else:
            value, size = text, len(text)
        if self.minimum is not None and size < self.minimum:
            raise ValueError(f'Minimum: {self.minimum:g}')
        if self.maximum is not None and size > self.maximum:
            raise ValueError(f'Maximum: {self.maximum:g}')
        return value


@dataclass(frozen=True)
class DialogueSection:
    lines: tuple[DialogueLine, ...]
    choices: tuple[DialogueChoice, ...] = ()
    next_section: str | None = None
    branches: tuple[DialogueChoice, ...] = ()
    events: tuple[tuple[int, str], ...] = ()
    timeout: tuple[float, str | None] | None = None
    call: DialogueCall | None = None
    input: DialogueInput | None = None
    source_line: int = 0


class DialogueTree:
    def __init__(self, sections, portraits, *, start, directory=None, expressions=None,
                 asset_references=(), translation_references=(), source='<dialogue>'):
        self.sections = MappingProxyType(dict(sections))
        self.portraits = MappingProxyType(dict(portraits))
        self.start = start
        self.directory = directory
        self.expressions = MappingProxyType(dict(expressions or {}))
        self.asset_references = tuple(asset_references)
        self.translation_references = tuple(translation_references)
        self.source = source

    def asset_path(self, path):
        if self.directory is not None and not path.startswith('res://'):
            return Path(self.directory) / path
        return path

    @classmethod
    def load(cls, path, *, resources=None):
        path = resources.resolve(path) if resources is not None else Path(path).resolve()
        return cls.parse(path.read_text(encoding='utf-8-sig'), source=str(path), directory=path.parent)

    @classmethod
    def parse(cls, text, *, source='<dialogue>', directory=None):
        sections = {}
        portraits = {}
        expressions = {}
        asset_references = []
        translation_references = []
        links = []
        name = None
        lines, choices, branches, events = [], [], [], []
        header_line = 0
        timeout = call = user_input = None

        def fail(number, message):
            raise DialogueFormatError(f'{source}:{number}: {message}')

        def finish_section():
            if name is not None:
                if not lines:
                    fail(header_line, f'Section {name!r} needs at least one dialogue line')
                fallback = branches[-1].target if branches and branches[-1].condition is None else None
                if timeout is not None and not choices:
                    fail(header_line, '@timeout needs at least one choice')
                if user_input is not None and choices:
                    fail(header_line, '@input uses jumps after submission')
                if call is not None and (branches or choices or timeout):
                    fail(header_line, '@call replaces the choices or jumps in a section')
                sections[name] = DialogueSection(tuple(lines), tuple(choices), fallback, tuple(branches),
                                                 tuple(events), timeout, call, user_input, header_line)

        def destination(value, number):
            match = _TARGET.fullmatch(value)
            if not match:
                fail(number, 'Expected a section name, optionally followed by [if flag] or [if not flag]')
            target, predicate = match.groups()
            if target != _END:
                if not _ID.fullmatch(target):
                    fail(number, 'Invalid section name after =>')
                links.append((number, target))
            condition = None
            if predicate is not None:
                match = _CONDITION.fullmatch(predicate)
                if not match or (match[1] and match[3]):
                    fail(number, 'Invalid dialogue condition')
                negate, key, operator, value = match.groups()
                if operator:
                    try:
                        value = json.loads(value)
                    except ValueError:
                        fail(number, 'Use a JSON value in the comparison')
                    if value is not None and (type(value) not in (str, bool, int, float)
                                              or (type(value) is float and not isfinite(value))):
                        fail(number, 'A comparison needs a string, number, boolean or null')
                    condition = key, operator == '==', value
                else:
                    condition = key, not bool(negate)
            return (None if target == _END else target), condition

        def tokens(row, number):
            try:
                return shlex.split(row, posix=True)
            except ValueError as error:
                fail(number, str(error))

        def scalar(value, number):
            try:
                value = float(value)
            except ValueError:
                fail(number, 'Expected a finite number')
            if not isfinite(value):
                fail(number, 'Expected a finite number')
            return value

        def caption(value, number):
            if not re.match(r'\[tr(?:\s|\]|$)', value):
                return value, None
            match = _TRANSLATION.fullmatch(value)
            if not match:
                fail(number, 'Use [tr translation.key] followed by the default text')
            key, value = match.groups()
            translation_references.append(DialogueTranslationReference(source, number, key))
            return value, key

        for number, raw in enumerate(text.splitlines(), 1):
            row = raw.strip()
            if not row or row.startswith('#'):
                continue
            if row.startswith('@portrait '):
                if name is not None:
                    fail(number, 'Declare portraits before the first section')
                try:
                    parts = shlex.split(row, posix=True)
                except ValueError as error:
                    fail(number, str(error))
                if (len(parts) not in (4, 5) or parts[2] not in ('left', 'right')
                        or not parts[1].strip() or not parts[3].strip()
                        or (len(parts) == 5 and not _ID.fullmatch(parts[4]))):
                    fail(number, 'Use @portrait "Speaker" left|right "image.png" [expression]')
                _, speaker, side, path, *variant = parts
                collection, key = (expressions, (speaker, variant[0])) if variant else (portraits, speaker)
                if key in collection:
                    fail(number, f'Duplicate portrait for {speaker!r}')
                collection[key] = side, path
                asset_references.append(DialogueAssetReference(source, number, path))
                continue
            if row.startswith('~'):
                finish_section()
                name = row[1:].strip()
                if not _ID.fullmatch(name) or name == _END:
                    fail(number, 'Invalid section name')
                if name in sections:
                    fail(number, f'Duplicate section {name!r}')
                lines, choices, branches, events = [], [], [], []
                timeout = call = user_input = None
                header_line = number
                continue
            if name is None:
                fail(number, 'Start dialogue with a named section, for example ~ start')
            if row.startswith('@event '):
                event = row[7:].strip()
                if branches or choices or not _ID.fullmatch(event):
                    fail(number, 'Use @event name before choices or jumps')
                events.append((len(lines), event))
            elif row.startswith('@timeout '):
                parts = tokens(row, number)
                if timeout is not None or len(parts) != 3:
                    fail(number, 'Use @timeout seconds section|END once per section')
                seconds = scalar(parts[1], number)
                if seconds <= 0:
                    fail(number, 'Timeout must be positive')
                timeout = (seconds, destination(parts[2], number)[0])
            elif row.startswith('@input '):
                parts = tokens(row, number)
                if (user_input is not None or len(parts) not in (4, 6) or not _ID.fullmatch(parts[1])
                        or parts[3] == '' or parts[2] not in ('text', 'number')):
                    fail(number, 'Use @input key text|number "Prompt" [minimum maximum]')
                limits = [scalar(value, number) for value in parts[4:]]
                if limits and (limits[0] > limits[1] or (parts[2] == 'text'
                        and any(value < 0 or not value.is_integer() for value in limits))):
                    fail(number, 'Invalid input limits')
                user_input = DialogueInput(*parts[1:4], *limits)
            elif row.startswith('@call '):
                parts = tokens(row, number)
                if call is not None or len(parts) != 4 or not parts[1] or not _ID.fullmatch(parts[2]):
                    fail(number, 'Use @call "path.dialogue" section return_section|END')
                call = DialogueCall(parts[1], parts[2], destination(parts[3], number)[0])
            elif row.startswith('- '):
                if branches:
                    fail(number, 'Choose either response choices or jumps in this section')
                text, separator, target = row[2:].rpartition('=>')
                if not separator or not text.strip():
                    fail(number, 'Use - Choice text => target')
                locked = _LOCK.search(target)
                reason = None
                if locked:
                    try:
                        reason = json.loads(locked[1])
                    except ValueError:
                        fail(number, 'Use a quoted lock reason')
                    target = target[:locked.start()]
                text, key = caption(text.strip(), number)
                choices.append(DialogueChoice(text, *destination(target.strip(), number), translation_key=key,
                                              locked_reason=reason, source_line=number))
            elif row.startswith('=>'):
                if choices:
                    fail(number, 'Choose either response choices or a jump in this section')
                if branches and branches[-1].condition is None:
                    fail(number, 'An unconditional jump must be the last branch')
                branches.append(DialogueChoice('', *destination(row[2:].strip(), number), source_line=number))
            elif choices or branches:
                fail(number, 'Choices and jumps must follow the dialogue lines in a section')
            elif row.startswith('|'):
                if not lines:
                    fail(number, 'A continuation must follow a dialogue line')
                previous = lines[-1]
                lines[-1] = replace(previous, text=previous.text + '\n' + row[1:].lstrip())
            elif row.startswith('@'):
                if not lines:
                    fail(number, 'A line directive must follow dialogue text')
                try:
                    parts = shlex.split(row, posix=True)
                except ValueError as error:
                    fail(number, str(error))
                if len(parts) != 2 or parts[0] not in ('@expression', '@pause', '@voice'):
                    fail(number, 'Use @expression name, @pause seconds, or @voice "audio.ogg"')
                command, value = parts
                previous = lines[-1]
                if command == '@expression':
                    if (previous.speaker, value) not in expressions:
                        fail(number, f'Unknown expression {value!r} for {previous.speaker!r}')
                    lines[-1] = replace(previous, expression=value)
                elif command == '@pause':
                    try:
                        duration = float(value)
                    except ValueError:
                        fail(number, 'Pause must be a finite, nonnegative number of seconds')
                    if not isfinite(duration) or duration < 0:
                        fail(number, 'Pause must be a finite, nonnegative number of seconds')
                    lines[-1] = replace(previous, pause=duration)
                else:
                    if not value.strip():
                        fail(number, 'Voice needs an audio file path')
                    lines[-1] = replace(previous, voice=value)
                    asset_references.append(DialogueAssetReference(source, number, value))
            else:
                speaker, colon, message = row.partition(':')
                if not colon:
                    speaker, message = '', row
                if not message.strip():
                    fail(number, 'Dialogue text cannot be empty')
                message, key = caption(message.strip(), number)
                lines.append(DialogueLine(speaker.strip(), message, translation_key=key))

        finish_section()
        if not sections:
            fail(1, 'No dialogue sections found')
        for number, target in links:
            if target not in sections:
                fail(number, f'Unknown section {target!r}')
        return cls(sections, portraits, start='start' if 'start' in sections else next(iter(sections)),
                   directory=directory, expressions=expressions, asset_references=asset_references,
                   translation_references=translation_references, source=source)
