"""Inline dialogue effects built on the same callbacks used by RichLabel."""
from math import isfinite
import re
import shlex

from sfml.graphics import Color

from ..gui.effects import CharacterEffect, DEFAULT_EFFECTS
from ..gui.theme import text_object


_TAG = re.compile(r'\[(/?)([a-z_]+)([^\]]*)\]')


def compile_markup(text):
    if '[' not in text:
        return text, (), ()
    chunks, spans, pauses, stack = [], [], [], []
    position = end = 0

    def append(chunk):
        nonlocal position
        chunks.append(chunk)
        if stack and chunk:
            spans.append((position, position+len(chunk), tuple(stack)))
        position += len(chunk)

    for match in _TAG.finditer(text):
        closing, tag, args = match.groups()
        seconds = None
        if tag == 'pause' and not closing and args.startswith('='):
            try:
                seconds = float(args[1:])
            except ValueError:
                continue
            if not isfinite(seconds) or seconds <= 0:
                continue
        elif tag not in DEFAULT_EFFECTS:
            continue
        append(text[end:match.start()])
        end = match.end()
        if seconds is not None:
            pauses.append((position, seconds))
        elif closing:
            for index in range(len(stack)-1, -1, -1):
                if stack[index][0] == tag:
                    del stack[index:]
                    break
        else:
            try:
                options = dict(item.split('=', 1) for item in shlex.split(args) if '=' in item)
            except ValueError:
                options = {}
            stack.append((tag, options))
    append(text[end:])
    return ''.join(chunks), tuple(spans), tuple(pauses)


def draw_effects(owner, target, states, text, start, position, spans, elapsed):
    whole = text_object(owner, text)
    x, y = position
    for offset, value in enumerate(text):
        index = start+offset
        effect = CharacterEffect(index, elapsed, owner.theme.text)
        for begin, end, callbacks in spans:
            if begin <= index < end:
                for name, options in callbacks:
                    DEFAULT_EFFECTS[name](effect, options)
        if effect.visible:
            char = text_object(owner, value)
            advance = whole.find_character_pos(offset).x
            char.position = (x+advance+effect.offset.x, y+effect.offset.y)
            char.fill_color = Color(*effect.color)
            char.scale = (effect.scale, effect.scale)
            target.draw(char, states)
