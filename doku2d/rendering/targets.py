"""SFML targets that count Python draw submissions without changing drawing APIs."""
from sfml.graphics import RenderTexture, RenderWindow


class _MeasuredTarget:
    _debug = None

    def draw(self, drawable, states=None):
        result = super().draw(drawable, states)
        debug = self._debug
        if debug is not None and debug._counting_draws:
            debug._working_draw_calls += 1
        return result


class MeasuredTexture(_MeasuredTarget, RenderTexture):
    pass


class MeasuredWindow(_MeasuredTarget, RenderWindow):
    pass
