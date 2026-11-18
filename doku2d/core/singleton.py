"""Per-game named services; ordinary Python objects are welcome."""
from collections.abc import Mapping
from importlib import import_module
from .entity import Entity


def instantiate(source):
    if isinstance(source, str):
        module, separator, name = source.partition(":")
        if not separator:
            raise ValueError("Use 'package.module:factory' for code references")
        source = getattr(import_module(module), name)
    return source() if callable(source) else source


class Services(Mapping):
    def __init__(self, game):
        self._game = game
        self._objects = {}

    def __getitem__(self, name):
        return self._objects[name]

    def __iter__(self):
        return iter(self._objects)

    def __len__(self):
        return len(self._objects)

    def add(self, name, source):
        if name in self:
            raise ValueError(f"Service already registered: {name}")
        if self._game.closed:
            raise RuntimeError("Game is closed")
        instance = instantiate(source)
        if isinstance(instance, Entity) and (instance.game is not None or instance._pending_game is not None):
            raise ValueError("Service entity already belongs to a game")
        self._objects[name] = instance
        try:
            if isinstance(instance, Entity):
                self._game.add(instance, persistent=True)
        except Exception:
            self._objects.pop(name, None)
            raise
        return instance

    def remove(self, name):
        instance = self._objects.pop(name)
        if isinstance(instance, Entity) and instance.game is self._game:
            self._game.remove(instance)
        return instance

    def _forget(self, entity):
        for name, instance in tuple(self.items()):
            if instance is entity:
                del self._objects[name]
