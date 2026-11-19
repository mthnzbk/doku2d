"""Watch a rectangle against its Canvas's camera without drawing it."""
from math import isfinite

from ..core.entity import Entity
from ..core.signal import Signal
from .culling import ViewCuller, compose, transform_affine


class ScreenNotifier(Entity):
    screen_entered = Signal()
    screen_exited = Signal()
    _is_screen_notifier = True

    def __init__(self, target=None, *, rect=(-16, -16, 32, 32), margin=0,
                 auto_process=False, canvas=None, name=None):
        super().__init__(name)
        if target is not None and not isinstance(target, Entity):
            raise TypeError('ScreenNotifier target must be an Entity or None')
        if auto_process and target is None:
            raise ValueError('auto_process needs a target')
        self._target = target
        self._auto_process = bool(auto_process)
        self._on_screen = False
        self.rect = rect
        self.margin = margin
        self.canvas = canvas

    @property
    def target(self):
        return self._target

    @property
    def on_screen(self):
        return self._on_screen

    @property
    def auto_process(self):
        return self._auto_process

    @property
    def rect(self):
        return self._rect

    @rect.setter
    def rect(self, value):
        x, y, width, height = value
        if not all(isfinite(v) for v in (x, y, width, height)) or width < 0 or height < 0:
            raise ValueError('ScreenNotifier bounds must be finite with nonnegative dimensions')
        self._rect = (x, y, width, height)

    @property
    def margin(self):
        return self._margin

    @margin.setter
    def margin(self, value):
        if not isfinite(value) or value < 0:
            raise ValueError('ScreenNotifier margin must be nonnegative and finite')
        self._margin = value

    def on_added(self):
        owner = (self.target.game or self.target._pending_game) if self.target is not None else None
        if owner is not None and owner is not self.game:
            raise ValueError('Notifier and target must belong to the same Game')
        self.game._screen_notifiers[self] = None
        self._block(self.target is not None and owner is self.game)

    def on_removed(self):
        self.game._screen_notifiers.pop(self, None)
        self._block(False)
        self._on_screen = False

    def _block(self, blocked):
        if not self.auto_process:
            return
        target = self.target
        if blocked:
            if target._screen_blocks is None:
                target._screen_blocks = set()
            target._screen_blocks.add(self)
        elif target._screen_blocks is not None:
            target._screen_blocks.discard(self)

    def _update_visibility(self, views):
        game, target = self.game, self.target
        attached = target is None or target.game is game and target not in game._removing
        visible = False
        if attached and self.visible:
            canvas = self.canvas or (target.canvas if target is not None else None) or game.world
            if canvas not in views:
                views[canvas] = ViewCuller(game.make_view(canvas))
            matrix = transform_affine(self.transform)
            if target is not None:
                matrix = compose(transform_affine(target.transform), matrix)
            x, y, w, h = self.rect
            margin = self.margin
            visible = views[canvas].bounds((x-margin, y-margin, w+2*margin, h+2*margin), matrix)
        self._block(attached and not visible)
        if visible != self._on_screen:
            self._on_screen = visible
            return self.screen_entered if visible else self.screen_exited
        return None
