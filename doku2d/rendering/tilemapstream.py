"""Load bounded TileMap regions and retire all their game objects together."""
from collections import OrderedDict
from contextlib import nullcontext
from dataclasses import dataclass
from functools import cache, partial
from math import ceil, cos, floor, hypot, isfinite, sin
from operator import index

from sfml.system import Vector2

from ..core import Entity
from .tilemap import TileMap, TiledParser, coordinates, dimensions


@dataclass(frozen=True)
class TileMapChunk:
    """A local TileMap and optional entities positioned relative to its origin."""

    tilemap: TileMap
    entities: tuple = ()


def _read_region(root, chunk_size, origin, size):
    cx, cy = (value // width for value, width in zip(origin, chunk_size))
    for extension in ('.tmj', '.tmx'):
        path = root / f'{cx}_{cy}{extension}'
        if path.is_file():
            return TiledParser.parse(path)
    return None


class TileMapStream(Entity):
    """Keep only nearby regions of a finite, orthogonal tile world in memory."""

    def __init__(self, loader, *, size, target, tile_size=(16, 16), chunk_size=(32, 32),
                 radius=1, loads_per_step=2, cover_view=False, prepare=None, lookahead=8,
                 position=(0, 0), name=None):
        super().__init__(name)
        if not callable(loader):
            raise TypeError('Chunk loader must be callable')
        if not isinstance(target, Entity) and not callable(target):
            raise TypeError('Stream target must be an Entity or a position callback')
        if prepare is not None and not callable(prepare):
            raise TypeError('Stream prepare must be callable or None')
        self._size = dimensions(size)
        self._tile_size = dimensions(tile_size)
        self._chunk_size = dimensions(chunk_size)
        self.position = position
        self.radius = radius
        self.loads_per_step = loads_per_step
        self.cover_view = bool(cover_view)
        self.lookahead = lookahead
        self._loader = loader
        self._target = target
        self._chunks = {}
        self._missing = set()
        self._prepare = prepare
        self._prepared = {}
        self._previous_focus = None
        self._directory = None
        self._navigation_cache = OrderedDict()
        self._navigation_pins = {}
        self._navigation_revision = 0

    @classmethod
    def from_directory(cls, folder, *, collisions=True, **options):
        """Load 0_0.tmj, 1_0.tmj and similar local Tiled maps on demand."""
        def load(origin, size, data):
            if data is not None:
                # Share textures without retaining disk-loaded map data.
                return TileMap(data, resources=stream.game.resources, collisions=collisions)
            return None

        stream = cls(load, **options)
        stream._directory = folder
        stream._directory_collisions = collisions
        return stream

    @property
    def map_size(self):
        return Vector2(*self._size)

    @Entity.position.setter
    def position(self, value):
        if self.game is not None:
            raise RuntimeError('Set the stream origin before adding it to the game')
        Entity.position.fset(self, value)

    @property
    def tile_size(self):
        return Vector2(*self._tile_size)

    @property
    def chunk_size(self):
        return Vector2(*self._chunk_size)

    @property
    def world_bounds(self):
        return (*self.position, self._size[0] * self._tile_size[0], self._size[1] * self._tile_size[1])

    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, value):
        value = index(value)
        if value < 0:
            raise ValueError('Stream radius must be nonnegative')
        self._radius = value

    @property
    def loads_per_step(self):
        return self._loads_per_step

    @loads_per_step.setter
    def loads_per_step(self, value):
        value = index(value)
        if value < 1:
            raise ValueError('Load budget must be positive')
        self._loads_per_step = value

    @property
    def loaded_chunks(self):
        """A snapshot mapping loaded region coordinates to their TileMaps."""
        return {key: tilemap for key, (tilemap, _) in self._chunks.items()}

    @property
    def lookahead(self):
        """Distance in tiles used to anticipate regions along the target's movement."""
        return self._lookahead

    @lookahead.setter
    def lookahead(self, value):
        value = index(value)
        if value < 0:
            raise ValueError('Stream lookahead must be nonnegative')
        self._lookahead = value

    def _focus(self):
        point = self._target() if callable(self._target) else self._target.position
        offset = self._vector(point) - self.position
        tw, th = self._tile_size
        return offset.x / tw, offset.y / th

    def _region_key(self, focus):
        return tuple(int(value // width) for value, width in zip(focus, self._chunk_size))

    def _region_area(self, center):
        cx, cy = center
        dx, dy = self._chunk_size
        width, height = self._size
        radius = self.radius
        return {(x, y)
                for y in range(max(0, cy - radius), min((height + dy - 1) // dy, cy + radius + 1))
                for x in range(max(0, cx - radius), min((width + dx - 1) // dx, cx + radius + 1))}

    def _region_dimensions(self, key):
        dx, dy = self._chunk_size
        x, y = key[0] * dx, key[1] * dy
        return (x, y), (min(dx, self._size[0] - x), min(dy, self._size[1] - y))

    def map_to_world(self, point):
        """Return the center of a cell in the stream's world coordinates."""
        x, y = coordinates(point)
        tw, th = self._tile_size
        return self.position + ((x+.5)*tw, (y+.5)*th)

    def world_to_map(self, point):
        """Return the global stream cell for a world-space position."""
        x, y = self._vector(point) - self.position
        tw, th = self._tile_size
        return floor(x/tw), floor(y/th)

    def find_path(self, start, goal, *, diagonal=False, blocked_layers=None, bounds=None, blocked=(),
                  radius=None, agent=None, avoid_bodies=None, ignore=(), max_nodes=16384):
        """Find a route across regions in stream cell coordinates."""
        from .tilenavigation import cell_path, tile_occupancy

        if agent is not None and not getattr(agent, '_is_physics_body', False):
            raise TypeError('Navigation agent must be a physics body')
        if radius is None:
            radius = agent._navigation_radius() if agent is not None else 0
        if not isfinite(radius) or radius < 0:
            raise ValueError('Navigation radius must be nonnegative and finite')
        if type(max_nodes) is not int or max_nodes < 1:
            raise ValueError('max_nodes must be a positive integer')
        check_bodies = agent is not None if avoid_bodies is None else bool(avoid_bodies)
        if check_bodies and agent is not None and agent.game is not self.game:
            raise ValueError('The agent and tile stream must belong to the same Game')
        left, top = 0, 0
        right, bottom = self._size
        if bounds is not None:
            x, y, width, height = bounds
            x, y = coordinates((x, y))
            width, height = dimensions((width, height))
            left, top = max(0, x), max(0, y)
            right, bottom = min(right, x+width), min(bottom, y+height)
        obstacles = {coordinates(point) for point in blocked}
        names = (blocked_layers,) if isinstance(blocked_layers, str) else (
            None if blocked_layers is None else tuple(blocked_layers))

        @cache
        def region_query(key):
            origin, size = self._region_dimensions(key)
            tilemap = self._navigation_map(key)
            if tilemap is None:
                return None
            if tuple(tilemap.tile_size) != self._tile_size:
                raise ValueError('Chunk TileMap tile size must match the stream')
            position = self.position + tuple(a*b for a, b in zip(origin, self._tile_size))
            expected = position if key in self._chunks else (0, 0)
            if tilemap.rotation % 360 or tuple(tilemap.scale) != (1, 1) or tuple(tilemap.position) != tuple(expected):
                raise ValueError('Stream navigation needs tile maps aligned to their regions')
            layers = None if names is None else tuple(name for name in names if name in tilemap.layers)
            return tile_occupancy(tilemap, (0, 0, *size), layers)

        def occupied(point):
            if point in obstacles:
                return True
            key = self._region_key(point)
            query = region_query(key)
            return query is None or query(tuple(value % width for value, width in zip(point, self._chunk_size)))

        physics = self.game._physics if check_bodies and self.game is not None else None
        profile = self.game.debug._measure('navigation') if self.game is not None else nullcontext()
        with profile:
            return cell_path(coordinates(start), coordinates(goal), occupied=occupied,
                             bounds=(left, top, right, bottom), tile_size=self._tile_size,
                             clearance=(radius, radius), world_center=self.map_to_world,
                             diagonal=diagonal, physics=physics, radius=radius, agent=agent,
                             ignored=tuple(ignore), tilemap=self, max_nodes=max_nodes)

    def find_world_path(self, start, goal, **options):
        """Find a route and return world-space cell centers."""
        return [self.map_to_world(cell) for cell in
                self.find_path(self.world_to_map(start), self.world_to_map(goal), **options)]

    def _pin_navigation(self, follower, start, upcoming=()):
        current = self._region_key(start)
        keys = {current}
        next_region = next((key for key in map(self._region_key, upcoming) if key != current), None)
        if next_region is not None:
            keys.add(next_region)
        dx, dy = self._chunk_size
        w, h = self._size
        self._navigation_pins[follower] = {key for key in keys if 0 <= key[0]*dx < w and 0 <= key[1]*dy < h}

    def _navigation_known(self, cell):
        region = self._chunks.get(self._region_key(cell))
        return region is not None and region[0].game is self.game

    def _navigation_changed(self):
        self._navigation_revision += 1

    def _navigation_map(self, key):
        if key in self._chunks:
            return self._chunks[key][0]
        if key in self._missing:
            return None
        if key not in self._navigation_cache:
            origin, size = self._region_dimensions(key)
            if self._directory is not None:
                if self.game is None:
                    raise RuntimeError('Add the tile stream before finding paths in Tiled regions')
                payload = self._take_prepared(key, origin, size)
                tilemap = TileMap(payload, collisions=self._directory_collisions) if payload is not None else None
            else:
                payload = self._build_chunk(key, origin, size)
                tilemap = payload.tilemap if payload is not None else None
            self._navigation_cache[key] = tilemap, payload
            if len(self._navigation_cache) > 16:
                self._navigation_cache.popitem(last=False)
        self._navigation_cache.move_to_end(key)
        return self._navigation_cache[key][0]

    def _prefetch(self, focus, desired):
        if self._prepare is None:
            return
        predicted = focus
        if self._previous_focus is not None and self.lookahead:
            dx, dy = (a-b for a,b in zip(focus,self._previous_focus))
            distance = hypot(dx,dy)
            if distance:
                predicted = (focus[0] + dx * self.lookahead / distance,
                             focus[1] + dy * self.lookahead / distance)
        self._previous_focus = focus
        center = self._region_key(predicted)
        candidates = ((desired | self._region_area(center)) - self._chunks.keys()
                      - self._missing - self._navigation_cache.keys())
        for key in self._prepared.keys() - candidates:
            self._prepared.pop(key).cancel()
        limit = max(2, self.loads_per_step * 2)
        priority = sorted(candidates - self._prepared.keys(),
                          key=lambda key: (key not in desired,
                                           (key[0]-center[0])**2+(key[1]-center[1])**2, key))
        for key in priority[:max(0, limit-len(self._prepared))]:
            origin, size = self._region_dimensions(key)
            self._prepared[key] = self.game.resources._submit_preparation(self._prepare, origin, size)

    def _view_regions(self):
        camera = self.game.camera
        canvas = self.canvas or self.game.world
        if not self.cover_view or camera is None or not camera.enabled or canvas.screen_space:
            return set()
        view = self.game.make_view(canvas)
        width, height = view.size
        angle = view.rotation.radians
        c, s = abs(cos(angle)), abs(sin(angle))
        half_x, half_y = (width*c + height*s)/2, (width*s + height*c)/2
        x, y = view.center - self.position
        span_x, span_y = (a*b for a,b in zip(self._chunk_size,self._tile_size))
        columns, rows = (ceil(n/d) for n,d in zip(self._size,self._chunk_size))
        return {(column,row)
                for row in range(max(0,int((y-half_y)//span_y)),min(rows,ceil((y+half_y)/span_y)))
                for column in range(max(0,int((x-half_x)//span_x)),min(columns,ceil((x+half_x)/span_x)))}

    def _cover_camera(self):
        visible = self._view_regions()
        for key in sorted(visible - self._chunks.keys() - self._missing):
            self._load(key)

    def refresh(self, *, full=False):
        """Update nearby regions now. Full refresh loads the entire local radius."""
        if self.game is None:
            raise RuntimeError('Add the stream to a Game before refreshing')
        focus = self._focus()
        cx, cy = self._region_key(focus)
        visible = self._view_regions()
        pinned = set()
        for follower in tuple(self._navigation_pins):
            if follower._body.game is not self.game or follower.state not in ('moving', 'waiting'):
                del self._navigation_pins[follower]
            else:
                pinned.update(self._navigation_pins[follower])
        desired = self._region_area((cx, cy)) | visible | pinned
        pending = sorted(desired - self._chunks.keys() - self._missing,
                         key=lambda key: (key not in visible, key not in pinned,
                                          (key[0] - cx)**2 + (key[1] - cy)**2, key[1], key[0]))
        for key in sorted(self._chunks.keys() - desired):
            _, scope = self._chunks.pop(key)
            scope.close()
        self._missing.intersection_update(desired)
        for key in (pending if full else pending[:self.loads_per_step]):
            self._load(key)
        self._prefetch(focus, desired)

    def _take_prepared(self, key, origin, size):
        prepared = self._prepared.pop(key, None)
        # Nearby collisions must exist even if preparation cannot keep up.
        if prepared is None or prepared.cancelled() or prepared.cancel():
            return self._prepare(origin, size)
        return prepared.result()

    def _build_chunk(self, key, origin, size):
        args = () if self._prepare is None else (self._take_prepared(key, origin, size),)
        return self._checked_chunk(self._loader(origin, size, *args))

    def _checked_chunk(self, chunk):
        if chunk is None:
            return None
        if isinstance(chunk, TileMap):
            chunk = TileMapChunk(chunk)
        if not isinstance(chunk, TileMapChunk) or not isinstance(chunk.tilemap, TileMap):
            raise TypeError('Chunk loader must return a TileMap, TileMapChunk or None')
        if tuple(chunk.tilemap.tile_size) != self._tile_size:
            raise ValueError('Chunk TileMap tile size must match the stream')
        return chunk

    def _load(self, key):
        cell, size = self._region_dimensions(key)
        if key in self._navigation_cache:
            _, payload = self._navigation_cache.pop(key)
            chunk = self._checked_chunk(self._loader(cell, size, payload)) if self._directory is not None else payload
        else:
            chunk = self._build_chunk(key, cell, size)
        if chunk is None:
            self._missing.add(key)
            self._navigation_changed()
            return
        entities = (chunk.tilemap, *chunk.entities)
        if any(not isinstance(obj, Entity) or obj.game is not None or obj._pending_game is not None
               for obj in entities) or len(set(entities)) != len(entities):
            raise ValueError('Chunk entities must be distinct and detached')
        scope = self.game.create_scope()
        origin = self.position + tuple(x * size for x, size in zip(cell, self._tile_size))
        try:
            for obj in entities:
                obj.position += origin
                scope.add(obj, canvas=self.canvas if obj.canvas is None else obj.canvas)
        except Exception:
            scope.close()
            raise
        self._chunks[key] = chunk.tilemap, scope
        scope.connect(chunk.tilemap.changed, self._navigation_changed)

    def on_added(self):
        if self._directory is not None:
            root = self.game.resources.resolve(self._directory)
            self._prepare = partial(_read_region, root, self._chunk_size)
        self.game._tilemap_streams[self] = None
        self.refresh()

    def on_removed(self):
        self.game._tilemap_streams.pop(self, None)
        for prepared in self._prepared.values():
            prepared.cancel()
        self._prepared.clear()
        self._navigation_cache.clear()
        self._navigation_pins.clear()
        self._previous_focus = None
        for _, scope in self._chunks.values():
            scope.close()
        self._chunks.clear()
        self._missing.clear()
