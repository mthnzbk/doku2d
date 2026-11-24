"""Analyze possible routes without launching a game."""
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class DialogueWarning:
    source: str
    line: int
    section: str
    message: str
    state: dict | None = None


def _witness(constraints):
    grouped = defaultdict(list)
    for choice, enabled in constraints:
        if choice.condition is None:
            if not enabled:
                return None
        else:
            grouped[choice.condition[0]].append((choice, enabled))
    state = {}
    for key, conditions in grouped.items():
        mentioned = [choice.condition[2] for choice, _ in conditions if len(choice.condition) == 3]
        other = '__value__'
        while other in mentioned:
            other += '_'
        for value in (*mentioned, None, False, '', 0, True, other):
            if all(choice.allowed({key: value}) == enabled for choice, enabled in conditions):
                state[key] = value
                break
        else:
            return None
    return state


def routes(section, *, include_end=False):
    """Return locally possible targets and their display captions."""
    if section.call:
        if section.call.return_to is not None or include_end:
            yield section.call.return_to, f'↩ {section.call.entry}'
        return
    previous = []
    for choice in (*section.choices, *section.branches):
        if _witness([*previous, (choice, True)]) is not None and (choice.target is not None or include_end):
            if choice.condition is None:
                note = choice.text
            else:
                key, expected, *value = choice.condition
                if value:
                    note = f'{key} {"=" if expected else "≠"} {value[0]}'
                else:
                    note = f'{"" if expected else "!"}{key}'
            yield choice.target, note
        if section.branches:
            previous.append((choice, False))
    if section.timeout is not None and (section.timeout[1] is not None or include_end):
        yield section.timeout[1], f'{section.timeout[0]:g} s'
    if not section.branches and not section.choices and section.next_section is not None:
        yield section.next_section, ''


def depths(tree, entry):
    result = {entry: 0}
    pending = deque((entry,))
    while pending:
        section = pending.popleft()
        for target, _ in routes(tree.sections[section]):
            if target not in result:
                result[target] = result[section]+1
                pending.append(target)
    return result


def analyze_dialogue(tree, *, entry=None):
    """Report unreachable local sections and a state that disables all answers."""
    entry = tree.start if entry is None else entry
    reachable = depths(tree, entry)
    warnings = []
    for name, section in tree.sections.items():
        if name not in reachable:
            warnings.append(DialogueWarning(tree.source, section.source_line, name, f'{entry} → {name}: erişilemiyor'))
        if section.choices:
            state = _witness([(choice, False) for choice in section.choices])
            if state is not None:
                warnings.append(DialogueWarning(tree.source, section.choices[0].source_line, name,
                                                f'{name}: seçilebilir cevap yok', state))
    return tuple(warnings)
