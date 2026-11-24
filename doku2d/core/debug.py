"""Optional in-engine diagnostics, independent of game content and UI focus."""
from collections import deque
from contextlib import contextmanager
from math import cos, isfinite, sin, tau
from time import perf_counter

from sfml.graphics import Color, PrimitiveType, RectangleShape, Text, Vertex, VertexArray
from sfml.window import Event, Keyboard


class DebugOverlay:
    _profile_sections = ('events', 'physics', 'update', 'streaming', 'render', 'navigation', 'present')

    def __init__(self, game, *, enabled=False, key=Keyboard.F3):
        from .console import DebugConsole

        self._game = game
        self.console = DebugConsole(self)
        self._visible = self._held = False
        self._frame_time = 0.0
        self._chunks = {}
        self._chunk_count = 0
        self._font = None
        self._counting_draws = False
        self._working_draw_calls = self._last_draw_calls = 0
        self._reset_profile()
        self.enabled = enabled
        self.key = key
        self.show_stats = True
        self.show_collisions = True
        self.show_camera = True
        self.show_chunks = True
        self.show_profile = True

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = bool(value)
        if not self.enabled:
            self.console.close()
            self._visible = self._held = False
            self._counting_draws = False
            self._working_draw_calls = self._last_draw_calls = 0
            self._begin_frame()
            self._reset_profile()

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        self._visible = self.enabled and bool(value)
        if not self._visible:
            self.console.close()
            self._begin_frame()

    @property
    def key(self):
        return self._key

    @key.setter
    def key(self, value):
        if isinstance(value, str):
            value = getattr(Keyboard, value.upper(), None)
            if value is None:
                raise ValueError('Unknown debug shortcut key')
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise TypeError('Debug key must be a Key, key name or None')
        self._key = value
        self._held = False

    @property
    def frame_ms(self):
        return self._frame_time * 1000

    @property
    def fps(self):
        return 1 / self._frame_time if self._frame_time else 0

    @property
    def tile_chunks(self):
        return self._chunk_count

    @property
    def show_profile(self):
        return self._show_profile

    @show_profile.setter
    def show_profile(self, value):
        self._show_profile = bool(value)
        if not self._show_profile:
            self._reset_profile()

    @property
    def profile_ms(self):
        """Elapsed milliseconds by section, excluding time in nested sections."""
        return dict(self._last_profile)

    @property
    def peak_frame_ms(self):
        """Longest frame interval among the last 120 samples."""
        return max(self._frame_intervals, default=0.0)

    @property
    def path_queries(self):
        return self._last_queries

    @property
    def draw_calls(self):
        """Draw submissions to game-managed targets in the last frame."""
        return self._last_draw_calls

    def _reset_profile(self):
        self._frame_intervals = deque(maxlen=120)
        self._working_profile = dict.fromkeys(self._profile_sections, 0.0)
        self._last_profile = self._working_profile.copy()
        self._working_queries = self._last_queries = 0

    @contextmanager
    def _measure(self, section):
        if not self.enabled or not self.show_profile:
            yield
            return
        profile = self._working_profile
        previous = sum(profile.values())
        started = perf_counter()
        try:
            yield
        finally:
            elapsed = (perf_counter() - started) * 1000
            if self._working_profile is profile:
                if section == 'navigation':
                    self._working_queries += 1
                # Nested sections have already recorded their exclusive time.
                profile[section] += max(0, elapsed - (sum(profile.values()) - previous))

    def _publish_profile(self):
        if self.enabled and self.show_profile:
            self._last_profile = self._working_profile
            self._last_queries = self._working_queries
            self._working_profile = dict.fromkeys(self._profile_sections, 0.0)
            self._working_queries = 0

    def toggle(self):
        self.visible = not self.visible
        return self.visible

    def _event(self, event):
        if not self.enabled:
            return False
        if (self.visible and self.key != Keyboard.F4 and event.type in (Event.KEY_PRESSED, Event.KEY_RELEASED)
                and event.code == Keyboard.F4):
            if event.type == Event.KEY_RELEASED:
                self.console.toggle()
            return True
        if self.key is None:
            return False
        if event.type == Event.LOST_FOCUS:
            self._held = False
        if event.type not in (Event.KEY_PRESSED, Event.KEY_RELEASED) or event.code != self.key:
            return False
        if event.type == Event.KEY_PRESSED:
            if not self._held:
                self.toggle()
            self._held = True
        else:
            self._held = False
        return True

    def _sample(self, dt):
        if dt > 0:
            self._frame_time += (dt - self._frame_time) * (0.15 if self._frame_time else 1)
            if self.show_profile:
                self._frame_intervals.append(dt * 1000)

    def _begin_frame(self):
        self._chunks.clear()
        self._chunk_count = 0

    @staticmethod
    def _rect(x, y, w, h):
        return ((x, y), (x+w, y), (x+w, y+h), (x, y+h))

    @staticmethod
    def _outline(mesh, points, tint):
        if len(points) == 2:
            mesh.append(Vertex(points[0], tint))
            mesh.append(Vertex(points[1], tint))
            return
        for a, b in zip(points, points[1:] + points[:1]):
            mesh.append(Vertex(a, tint))
            mesh.append(Vertex(b, tint))

    @staticmethod
    def _mesh(meshes, canvas):
        if canvas not in meshes:
            meshes[canvas] = VertexArray(PrimitiveType.LINES)
        return meshes[canvas]

    def _tile_chunk(self, canvas, transform, rect):
        self._chunk_count += 1
        if self.show_chunks:
            points = [transform.transform_point(point) for point in self._rect(*rect)]
            self._outline(self._mesh(self._chunks, canvas), points, Color(131, 188, 255, 185))

    def _collisions(self, meshes):
        from pymunk import Circle, Poly, Segment

        for shape, entity in self._game._physics._shapes.items():
            body = shape.body
            if isinstance(shape, Circle):
                x, y = shape.offset
                points = [(x+cos(i*tau/32)*shape.radius, y+sin(i*tau/32)*shape.radius) for i in range(32)]
            elif isinstance(shape, Segment):
                points = [shape.a, shape.b]
            elif isinstance(shape, Poly):
                points = shape.get_vertices()
            else:
                continue
            world = [tuple(body.local_to_world(point)) for point in points]
            tint = Color(255, 179, 112, 220) if shape.sensor else Color(117, 255, 159, 220)
            self._outline(self._mesh(meshes, entity.canvas or self._game.world), world, tint)

    def _draw(self, target, visible_count):
        game = self._game
        meshes = self._chunks.copy()
        if self.show_collisions and game._physics is not None:
            self._collisions(meshes)
        camera = game.camera
        if self.show_camera and camera is not None and camera.enabled:
            bounds = camera.bounds
            if all(isfinite(value) for value in bounds):
                self._outline(self._mesh(meshes, game.world), self._rect(*bounds), Color(255, 206, 104))
        for canvas, mesh in meshes.items():
            target.view = game.make_view(canvas)
            target.draw(mesh)
        if self.show_stats:
            self._draw_stats(target, visible_count)

    def _draw_stats(self, target, visible_count):
        if self._font is None:
            from ..gui.theme import Theme
            self._font = Theme(resources=self._game.resources).get_font()
        target.view = self._game._pixel_view(self._game.size)
        lines = [f'DEBUG  {self.fps:.0f} FPS  {self.frame_ms:.1f} ms',
                 f'Objects: {visible_count}/{len(self._game.objects)}  Tile chunks: {self.tile_chunks}',
                 f'Draw calls: {self.draw_calls}']
        if self.key != Keyboard.F4:
            lines.append('F4: Developer console')
        if self.show_profile:
            times = self._last_profile
            lines += [f'Physics: {times["physics"]:.2f} ms  Update: {times["update"]:.2f} ms',
                      f'Streaming: {times["streaming"]:.2f} ms  Events: {times["events"]:.2f} ms',
                      f'Draw: {times["render"]:.2f} ms  Present: {times["present"]:.2f} ms',
                      f'A*: {times["navigation"]:.2f} ms ({self.path_queries})  Peak: {self.peak_frame_ms:.1f} ms']
        text = Text(self._font, '\n'.join(lines), 13)
        backdrop = RectangleShape((text.local_bounds.size.x + 20, text.local_bounds.size.y + 20))
        backdrop.position = (8, 8)
        backdrop.fill_color = Color(10, 16, 25, 230)
        text.position = (18, 13)
        target.draw(backdrop)
        target.draw(text)
