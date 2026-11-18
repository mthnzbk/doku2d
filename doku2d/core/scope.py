"""Lifetime for a flat set of game objects and their signal connections."""
class EntityScope:
    def __init__(self, game):
        if game.closed:
            raise RuntimeError("Game is closed")
        self._game = game
        self._members = {}
        self._connections = {}
        self._closed = False
        game._scopes.add(self)

    @property
    def game(self):
        return self._game

    @property
    def closed(self):
        return self._closed

    @property
    def members(self):
        return tuple(self._members)

    def _require_open(self):
        if self.closed or self.game.closed:
            raise RuntimeError("Entity scope is closed")

    def add(self, source, *, canvas=None):
        self._require_open()
        return self.game.add(source, canvas=canvas, scope=self)

    def connect(self, signal, callback, *, one_shot=False):
        self._require_open()
        if not callable(callback):
            raise TypeError("Scoped callbacks must be callable")
        def connection(*args, **kwargs):
            if one_shot:
                self._connections.pop(connection, None)
            return self._invoke(callback, *args, **kwargs)

        signal.connect(connection, one_shot=one_shot)
        self._connections[connection] = signal
        return connection

    def defer(self, callback, *args, **kwargs):
        self._require_open()
        self.game._schedule(self._invoke, callback, *args, **kwargs)

    def _invoke(self, callback, /, *args, **kwargs):
        if not self.closed:
            with self.game._using_scope(self):
                return callback(*args, **kwargs)

    def _disconnect(self):
        self._closed = True
        for callback, signal in self._connections.items():
            signal.disconnect(callback)
        self._connections.clear()

    def close(self):
        if self.closed:
            return
        self._disconnect()
        self.game._scopes.discard(self)
        self.game._dispatching += 1
        try:
            for member in reversed(self.members):
                if member in self._members:
                    self.game.remove(member)
        finally:
            self.game._dispatching -= 1
            self.game.flush_deferred()
