"""Drive a floating CharacterBody along a regular or streamed TileMap path."""
from math import hypot, isfinite

from ..core.entity import Entity
from ..core.signal import Signal


class PathFollower:
    arrived = Signal()
    path_failed = Signal()

    def __init__(self, body, tilemap, target, *, speed=120, tolerance=1,
                 repath_interval=0.25, diagonal=False, blocked_layers=None,
                 bounds=None, blocked=(), radius=None, avoid_bodies=True):
        from ..rendering.tilemap import TileMap
        from ..rendering.tilemapstream import TileMapStream

        if not isinstance(tilemap, (TileMap, TileMapStream)):
            raise TypeError('Navigation needs a TileMap or TileMapStream')
        if body.motion_mode != 'floating':
            raise ValueError('TileMap navigation needs a floating CharacterBody')
        owner = body.game or body._pending_game
        map_owner = tilemap.game or tilemap._pending_game
        if owner is not None and map_owner is not None and owner is not map_owner:
            raise ValueError('The character and tile map must belong to the same Game')
        self._body = body
        self._tilemap = tilemap
        self._stream = tilemap if isinstance(tilemap, TileMapStream) else None
        self._options = dict(diagonal=diagonal, bounds=None if bounds is None else tuple(bounds),
                             blocked_layers=(blocked_layers if blocked_layers is None or isinstance(blocked_layers, str)
                                             else tuple(blocked_layers)))
        self._blocked = blocked if callable(blocked) else tuple(tuple(cell) for cell in blocked)
        self._tolerance = self._positive(tolerance, 'Tolerance')
        self._repath_interval = self._positive(repath_interval, 'Repath interval')
        self.radius = radius
        self.avoid_bodies = bool(avoid_bodies)
        self.speed = speed
        self.target = target

    @staticmethod
    def _positive(value, name):
        if not isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be positive and finite')
        return float(value)

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, value):
        self._speed = self._positive(value, 'Navigation speed')

    @property
    def radius(self):
        """World-space clearance. Assign None to use the collision shape again."""
        return self._body._navigation_radius() if self._radius is None else self._radius

    @radius.setter
    def radius(self, value):
        if value is not None and (not isfinite(value) or value < 0):
            raise ValueError('Navigation radius must be nonnegative and finite')
        self._radius = value
        self._remaining = 0

    @property
    def target(self):
        return self._target if isinstance(self._target, Entity) else Entity._vector(self._target)

    @target.setter
    def target(self, value):
        self._target = value if isinstance(value, Entity) else Entity._vector(value)
        self._state = 'waiting'
        self._reported_failure = False
        self._remaining = 0.0
        self._cells = ()
        self._index = 0
        self._planned_goal = None
        self._planned_revision = None

    @property
    def state(self):
        """One of waiting, moving, arrived, or stopped."""
        return self._state

    @property
    def path(self):
        """Remaining waypoints in world coordinates."""
        if not self._cells or self._index >= len(self._cells):
            return ()
        points = [self._tilemap.map_to_world(cell) for cell in self._cells[self._index:-1]]
        target = self._target_point()
        last = self._cells[-1]
        if self._tilemap.world_to_map(target) != last:
            target = self._tilemap.map_to_world(last)
        return (*points, target)

    def _target_point(self):
        return self._target.position if isinstance(self._target, Entity) else Entity._vector(self._target)

    def _halt(self):
        if self._body.navigation is self:
            self._body.velocity = (0, 0)

    def stop(self):
        if self._state in ('waiting', 'moving'):
            self._halt()
        self._cells = ()
        self._index = 0
        self._state = 'stopped'

    def _plan(self, start, goal):
        self._remaining = self._repath_interval
        blocked = self._blocked() if callable(self._blocked) else self._blocked
        path = tuple(self._tilemap.find_path(start, goal, blocked=blocked, radius=self.radius,
                                           agent=self._body, avoid_bodies=self.avoid_bodies,
                                           ignore=(self._target,) if isinstance(self._target, Entity) else (),
                                           **self._options))
        if path:
            remainder = self._cells[self._index:]
            # Keep progress toward a waypoint when a fresh search agrees with the route.
            if not remainder or remainder not in (path, path[1:]):
                self._cells, self._index = path, 0
            self._state = 'moving'
            self._planned_goal = goal
            if self._stream is not None:
                self._planned_revision = self._stream._navigation_revision
            self._reported_failure = False
            return True
        self._cells, self._index = (), 0
        self._state = 'waiting'
        self._halt()
        if not self._reported_failure:
            self._reported_failure = True
            self.path_failed.emit()
        return False

    def _step(self, dt):
        if self.state not in ('waiting', 'moving'):
            return
        body = self._body
        if body.motion_mode != 'floating' or self._tilemap.game is not body.game or (
                isinstance(self._target, Entity) and self._target.game is not body.game):
            self.stop()
            self.path_failed.emit()
            return
        if not body.can_process():
            self._halt()
            return

        target = self._target_point()
        goal = self._tilemap.world_to_map(target)
        start = self._tilemap.world_to_map(body.position)
        stream = self._stream
        self._remaining -= dt
        if stream is not None:
            limit = max(stream._chunk_size)+1
            stream._pin_navigation(self, start, self._cells[self._index:self._index+limit])
        route_changed = stream is not None and self._cells and (
            self._planned_goal != goal or self._planned_revision != stream._navigation_revision)
        if route_changed or (self._remaining <= 0 and (stream is None or not self._cells or callable(self._blocked))):
            if not self._plan(start, goal):
                return
            if stream is not None:
                stream._pin_navigation(self, start, self._cells[self._index:self._index+limit])
        if not self._cells:
            self._halt()
            return

        while self._index < len(self._cells):
            cell = self._cells[self._index]
            final = self._index == len(self._cells)-1 and cell == goal
            waypoint = target if final else self._tilemap.map_to_world(cell)
            delta = waypoint - body.position
            distance = hypot(*delta)
            if distance > (self._arrival_distance() if final else self._tolerance):
                if stream is not None and (not stream._navigation_known(start) or not stream._navigation_known(cell)):
                    self._halt()
                    return
                velocity = delta * (min(self.speed, distance/dt) / distance)
                if self.avoid_bodies and not body.game.physics._navigation_clear(
                        body.position, body.position+velocity*dt, self.radius, agent=body,
                        ignored=(self._target,) if isinstance(self._target, Entity) else (),
                        tilemap=self._tilemap):
                    self._halt()
                    self._cells, self._index = (), 0
                    self._state = 'waiting'
                    self._remaining = min(self._remaining, 0.05)
                    return
                body.velocity = velocity
                body.move_and_slide()
                return
            self._index += 1

        self._halt()
        if goal != self._cells[-1]:
            self._remaining = 0
            self._cells = ()
            self._state = 'waiting'
            return
        self._cells, self._index = (), 0
        self._state = 'arrived'
        self.arrived.emit()

    def _arrival_distance(self):
        target, body = self._target, self._body
        if (getattr(target, '_is_physics_body', False) and not target._is_area
                and body.collision_layer & target.collision_mask
                and target.collision_layer & body.collision_mask):
            return max(self.radius, body._navigation_radius()) + target._navigation_radius() + self._tolerance
        return self._tolerance
