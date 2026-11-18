"""Instance-local signals, also usable as standalone objects."""
from weakref import WeakMethod


class Signal:
    def __init__(self):
        self._connections = []
        self._name = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        key = f"__signal_{self._name}"
        if key not in instance.__dict__:
            instance.__dict__[key] = Signal()
        return instance.__dict__[key]

    @staticmethod
    def _resolve(reference):
        return reference() if isinstance(reference, WeakMethod) else reference

    def connect(self, callback, *, one_shot=False):
        if not callable(callback):
            raise TypeError("Signal callbacks must be callable")
        if self.is_connected(callback):
            raise ValueError("Callback is already connected")
        reference = callback
        if getattr(callback, "__self__", None) is not None:
            try:
                reference = WeakMethod(callback)
            except TypeError:
                pass
        self._connections.append((reference, one_shot))
        return callback

    def disconnect(self, callback):
        self._connections[:] = [item for item in self._connections
                                if self._resolve(item[0]) not in (None, callback)]

    def is_connected(self, callback):
        return any(self._resolve(ref) == callback for ref, _ in self._connections)

    def emit(self, *args, **kwargs):
        for connection in tuple(self._connections):
            if connection not in self._connections:
                continue
            reference, one_shot = connection
            callback = self._resolve(reference)
            if callback is None or one_shot:
                self._connections.remove(connection)
            if callback is not None:
                callback(*args, **kwargs)

    def clear(self):
        self._connections.clear()
