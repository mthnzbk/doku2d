from math import floor, isfinite
from ..core import Signal
from .base import Control


class Range(Control):
    """Shared finite, clamped and optionally stepped numeric value."""
    changed = Signal()
    value_changed = Signal()

    def __init__(self, name=None, *, min_value=0.0, max_value=100.0,
                 value=1.0, step=0.01, rounded=False):
        super().__init__(name)
        self._min_value = self._finite(min_value)
        self._max_value = self._finite(max_value)
        self._step = self._finite(step)
        if self._min_value > self._max_value or self._step < 0:
            raise ValueError("Range requires min <= max and step >= 0")
        self._rounded = bool(rounded)
        self._value = self._normalize(value)

    @staticmethod
    def _finite(value):
        value = float(value)
        if not isfinite(value):
            raise ValueError("Range values must be finite")
        return value

    def _normalize(self, value):
        value = self._finite(value)
        if self.step:
            value = self.min_value + floor((value - self.min_value) / self.step + 0.5) * self.step
        if self.rounded:
            value = floor(value + 0.5)
        return max(self.min_value, min(self.max_value, value))

    def _reconfigure(self):
        self.value = self.value
        self.changed.emit()

    @property
    def min_value(self):
        return self._min_value

    @min_value.setter
    def min_value(self, value):
        value = self._finite(value)
        if value > self.max_value:
            raise ValueError("min_value cannot exceed max_value")
        if value != self.min_value:
            self._min_value = value
            self._reconfigure()

    @property
    def max_value(self):
        return self._max_value

    @max_value.setter
    def max_value(self, value):
        value = self._finite(value)
        if value < self.min_value:
            raise ValueError("max_value cannot be below min_value")
        if value != self.max_value:
            self._max_value = value
            self._reconfigure()

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        value = self._normalize(value)
        if value != self.value:
            self._value = value
            self.value_changed.emit(value)

    @property
    def step(self):
        return self._step

    @step.setter
    def step(self, value):
        value = self._finite(value)
        if value < 0:
            raise ValueError("step cannot be negative")
        if value != self.step:
            self._step = value
            self._reconfigure()

    @property
    def rounded(self):
        return self._rounded

    @rounded.setter
    def rounded(self, value):
        if bool(value) != self.rounded:
            self._rounded = bool(value)
            self._reconfigure()

    @property
    def ratio(self):
        span = self.max_value - self.min_value
        return (self.value - self.min_value) / span if span else 0.0

    @ratio.setter
    def ratio(self, value):
        self.value = self.min_value + self._finite(value) * (self.max_value - self.min_value)
