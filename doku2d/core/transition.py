"""A fading scope transition with optional background preparation."""
from math import isfinite

from sfml.graphics import Color, RectangleShape, Text

from .canvas import Canvas
from .entity import Entity
from .signal import Signal


class Transition(Entity):
    finished = Signal()
    failed = Signal()

    def __init__(self, build, *, old_scope, preload, prepare, fade_out, fade_in, loading_text):
        super().__init__()
        if not callable(build) or (prepare is not None and not callable(prepare)):
            raise TypeError('Transition build and prepare must be callable')
        if any(not isfinite(duration) or duration < 0 for duration in (fade_out, fade_in)):
            raise ValueError('Transition durations must be finite and nonnegative')
        self.canvas = Canvas('Transition', order=2**31, screen_space=True)
        self.process_mode = 'always'
        self._build, self._prepare = build, prepare
        self._old_scope, self._paths = old_scope, preload
        self._fade_out, self._fade_in = fade_out, fade_in
        self._loading_text = loading_text
        self._request = self._future = None
        self._new_scope = self._error = None
        self._phase = 'out'
        self._elapsed = 0.0
        self._opacity = 0.0

    @property
    def progress(self):
        if self._request is None:
            return 0.0
        if self._future is None:
            return self._request.progress
        return (self._request.progress + self._future.done()) / 2

    @property
    def new_scope(self):
        return self._new_scope

    @property
    def error(self):
        return self._error

    def on_added(self):
        self._was_paused = self.game.paused
        self._request = self.game.resources.preload_async(*self._paths)
        if self._prepare is not None:
            self._future = self.game.resources._submit_preparation(self._prepare)
        self.game.paused = True

    def on_removed(self):
        if self._future is not None:
            self._future.cancel()
        if self.game._transition is self:
            self.game._transition = None
            if not self.game.closed:
                self.game.paused = self._was_paused

    def _step(self, dt):
        self._elapsed += dt
        if self._phase == 'out':
            self._opacity = min(1.0, self._elapsed/self._fade_out) if self._fade_out else 1.0
            if self._opacity == 1:
                self._phase = 'loading'
        elif self._phase == 'loading':
            if self._request.done and (self._future is None or self._future.done()):
                self._replace_scope()
                self._phase, self._elapsed = 'in', 0.0
        elif self._phase == 'in':
            self._opacity = max(0.0, 1-self._elapsed/self._fade_in) if self._fade_in else 0.0
            if self._opacity == 0:
                self._phase = 'done'
                self.game.remove(self)
                if self.error is None:
                    self.finished.emit(self.new_scope)
                else:
                    self.failed.emit(self.error)

    def _replace_scope(self):
        game = self.game
        scope = game.create_scope()
        camera, listener = game.camera, game.audio_listener
        try:
            errors = self._request.errors
            if errors:
                path, error = next(iter(errors.items()))
                raise RuntimeError(f'Could not preload {path}') from error
            args = () if self._future is None else (self._future.result(),)
            scope._invoke(self._build, scope, *args)
            game.flush_deferred()
        except Exception as error:
            self._error = error
            try:
                scope.close()
            except Exception as cleanup:
                self._error = ExceptionGroup('Transition build and cleanup failed', [error, cleanup])
            if camera is not None and camera.game is game:
                game.camera = camera
            if listener is not None and listener.game is game:
                game.audio_listener = listener
            return
        self._new_scope = scope
        if self._old_scope is not None:
            try:
                self._old_scope.close()
            except Exception as error:
                self._error = error
        if game.camera is None:
            from ..rendering.camera import Camera
            camera = next((member for member in scope.members if isinstance(member, Camera) and member.enabled), None)
            if camera is not None:
                camera.make_current()

    def render(self, target, states):
        size = self.game.size
        backdrop = RectangleShape(size)
        backdrop.fill_color = Color(0, 0, 0, round(255*self._opacity))
        target.draw(backdrop, states)
        if self._phase != 'loading' or not self._loading_text:
            return
        theme = self.game.ui.theme
        label = Text(theme.get_font(), f'{self._loading_text}   {self.progress:.0%}', theme.font_size)
        bounds = label.local_bounds
        label.position = (size.x/2-bounds.size.x/2-bounds.position.x, size.y/2-bounds.position.y)
        label.fill_color = Color(*theme.text)
        target.draw(label, states)
