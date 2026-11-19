"""Per-game translation catalogs and explicitly marked UI text."""
from collections.abc import Mapping
from dataclasses import dataclass, field

from .signal import Signal


def _locale_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Locale must be a nonempty language tag')
    return value.strip().replace('_', '-').lower()


def _format(text, values):
    if not values:
        return text
    try:
        return text.format_map(values)
    except (KeyError, IndexError, AttributeError, ValueError, TypeError):
        return text


@dataclass(frozen=True)
class LocalizedText:
    key: str
    default: str | None = None
    values: dict = field(default_factory=dict)

    def __str__(self):
        return _format(self.key if self.default is None else self.default, self.values)


def tr(key, *, default=None, **values):
    """Mark UI text so it can be resolved in the owning game's locale."""
    if not isinstance(key, str) or not key:
        raise ValueError('Translation key must be a nonempty string')
    if default is not None and not isinstance(default, str):
        raise TypeError('Translation default must be a string')
    return LocalizedText(key, default, values)


class Localization:
    locale_changed = Signal()

    def __init__(self, resources, *, locale='en', fallback='en'):
        self._resources = resources
        self._catalogs = {}
        self._locale = _locale_name(locale)
        self.fallback_locale = fallback

    @property
    def locale(self):
        return self._locale

    @locale.setter
    def locale(self, value):
        value = _locale_name(value)
        if value != self._locale:
            self._locale = value
            self.locale_changed.emit(value)

    @property
    def fallback_locale(self):
        return self._fallback

    @fallback_locale.setter
    def fallback_locale(self, value):
        self._fallback = _locale_name(value)

    def add_catalog(self, locale, messages):
        if not isinstance(messages, Mapping) or any(not isinstance(key, str) or not isinstance(value, str)
                                                    for key, value in messages.items()):
            raise ValueError('A translation catalog must map string keys to strings')
        self._catalogs.setdefault(_locale_name(locale), {}).update(messages)

    def load_catalog(self, locale, path):
        self.add_catalog(locale, self._resources.get_json(path))

    def resolve(self, value):
        if not isinstance(value, LocalizedText):
            return str(value)
        for locale in dict.fromkeys((self.locale, self.locale.split('-')[0],
                                     self.fallback_locale, self.fallback_locale.split('-')[0])):
            catalog = self._catalogs.get(locale, {})
            if value.key in catalog:
                return _format(catalog[value.key], value.values)
        return str(value)

    def translate(self, key, *, default=None, **values):
        return self.resolve(tr(key, default=default, **values))


__all__ = ['Localization', 'LocalizedText', 'tr']
