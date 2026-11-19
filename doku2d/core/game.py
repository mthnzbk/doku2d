from collections import deque
from weakref import WeakKeyDictionary
from pathlib import Path
from contextlib import contextmanager
import re
from math import isfinite
from sfml.graphics import Color, Rect, RenderStates, Sprite, View
from sfml.system import Clock, Vector2
from sfml.window import Event, VideoMode
from .canvas import Canvas
from .entity import Entity
from .resource import Resources
from .storage import SaveStore, Settings
from .scope import EntityScope
from .signal import Signal
from .singleton import Services, instantiate
from .input import Input, Key
from .debug import DebugOverlay
from .localization import Localization


class Game:
    """A flat object registry, frame loop and renderer owned by one game."""
    object_added = Signal()
    object_removed = Signal()
    updated = Signal()
    physics_updated = Signal()

    def __init__(self, title="Doku2D", size=(960, 540), *, fps_limit=60,
                 physics_fps=60, services=None, project_root=None, asset_root=None,
                 save_dir=None, app_id=None, window_size=None, scale_mode="fit",
                 bar_color=Color.BLACK, theme=None, debug=False, debug_key=Key.F3,
                 persist_preferences=False, locale="en", fallback_locale="en", catalogs=None):
        self._window = None
        self._closed = False
        self._running = True
        self._paused = False
        self._objects = {}
        self._pending = {}
        self._scopes = set()
        self._active_scope = None
        self._surface = None
        self.batching = True
        self.culling = True
        self._sprite_batches = WeakKeyDictionary()
        self._screen_notifiers = {}
        self._window_size = None
        self.scale_mode = scale_mode
        self.bar_color = bar_color
        self._theme_source = theme
        self._removing = set()
        self._deferred = deque()
        self._dispatching = 0
        self._flushing = False
        self._camera = None
        self._audio_listener = None
        self._audio = None
        self._ui = None
        self._input = Input()
        self._debug = DebugOverlay(self, enabled=debug, key=debug_key)
        self._physics = None
        self._lighting = None
        self._canvas_effect = None
        self._world = Canvas()
        self._project_root=Path(project_root or Path.cwd()).resolve()
        self._resources=Resources(self._project_root/Path(asset_root or '.'))
        self._app_id=app_id or re.sub(r'[^A-Za-z0-9_.-]+','-',str(title)).strip('.-') or 'doku2d-game'
        self._saves=SaveStore(self._project_root/Path(save_dir) if save_dir is not None else None,app_id=self._app_id)
        self._settings=None
        self._persist_preferences = bool(persist_preferences)
        if self._persist_preferences:
            self.input._restore_preferences(self._preferences('input'),
                                            lambda data: self._remember_preferences('input', data))
            saved_locale = self._preferences('locale')
            if isinstance(saved_locale, str) and saved_locale.strip():
                locale = saved_locale
        self._localization = Localization(self.resources, locale=locale, fallback=fallback_locale)
        for language, path in (catalogs or {}).items():
            self.localization.load_catalog(language, path)
        if self._persist_preferences:
            self.localization.locale_changed.connect(self._save_locale)
        self._services = Services(self)
        self._accumulator = 0.0
        self._clear_color = Color(18, 24, 38)
        self.title = title
        self.size = size
        if window_size is not None:
            self.window_size = window_size
        self.fps_limit = fps_limit
        self.physics_fps = physics_fps
        for name, source in (services or {}).items():
            self.services.add(name, source)

    @classmethod
    def from_project(cls,path='doku2d.toml',**overrides):
        from ..config import ProjectConfig
        config=ProjectConfig.load(path)
        return cls(**dict(config.game_options,**overrides))

    @property
    def project_root(self):return self._project_root
    @property
    def app_id(self):return self._app_id
    @property
    def saves(self):return self._saves
    @property
    def settings(self):
        if self._settings is None:self._settings=Settings(self.saves)
        return self._settings

    def _preferences(self, section):
        data = self.settings.get('doku2d', {})
        return data.get(section, {}) if isinstance(data, dict) else {}

    def _remember_preferences(self, section, value):
        data = self.settings.get('doku2d', {})
        sections = dict(data) if isinstance(data, dict) else {}
        sections[section] = value
        self.settings['doku2d'] = sections

    def _save_locale(self, locale):
        self._remember_preferences('locale', locale)

    @property
    def localization(self):
        return self._localization

    @property
    def locale(self):
        return self.localization.locale

    @locale.setter
    def locale(self, value):
        self.localization.locale = value

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = str(value)
        if self.window:
            self.window.set_title(self.title)

    @property
    def size(self):
        return Vector2(*self._size)

    @size.setter
    def size(self, value):
        self._size = self._dimensions(value)

    @staticmethod
    def _dimensions(value):
        x, y = Entity._vector(value)
        if x <= 0 or y <= 0 or int(x) != x or int(y) != y:
            raise ValueError("Dimensions must be positive integers")
        return Vector2(int(x), int(y))

    @property
    def window_size(self):
        if self.window is not None:
            return self.window.size
        return Vector2(*(self._window_size or self.size))

    @window_size.setter
    def window_size(self, value):
        self._window_size = self._dimensions(value)
        if self.window is not None:
            self.window.size = self._window_size

    @property
    def scale_mode(self):
        return self._scale_mode

    @scale_mode.setter
    def scale_mode(self, value):
        if value not in ("fit", "integer", "stretch"):
            raise ValueError("scale_mode must be fit, integer or stretch")
        self._scale_mode = value

    def content_rect(self, output_size=None):
        """Presentation rectangle in physical pixels: x, y, width, height."""
        width, height = self.window_size if output_size is None else output_size
        if width <= 0 or height <= 0:
            return (0, 0, 0, 0)
        if self.scale_mode == "stretch":
            return (0, 0, width, height)
        scale = min(width / self.size.x, height / self.size.y)
        if self.scale_mode == "integer" and scale >= 1:
            scale = int(scale)
        w, h = self.size.x * scale, self.size.y * scale
        return ((width - w) / 2, (height - h) / 2, w, h)

    def window_to_screen(self, point, *, output_size=None, allow_outside=False):
        """Convert a physical window pixel to logical screen coordinates."""
        px, py = Entity._vector(point)
        x, y, w, h = self.content_rect(output_size)
        if not w or not h or (not allow_outside and not (x <= px < x+w and y <= py < y+h)):
            return None
        return Vector2((px-x)*self.size.x/w, (py-y)*self.size.y/h)

    def screen_to_window(self, point, *, output_size=None):
        px, py = Entity._vector(point)
        x, y, w, h = self.content_rect(output_size)
        return Vector2(x+px*w/self.size.x, y+py*h/self.size.y)

    def screen_to_world(self, point, canvas=None):
        x, y = Entity._vector(point)
        view = self.make_view(canvas or self.world)
        return view.transform.inverse.transform_point((2*x/self.size.x-1, 1-2*y/self.size.y))

    def world_to_screen(self, point, canvas=None):
        view = self.make_view(canvas or self.world)
        x, y = view.transform.transform_point(Entity._vector(point))
        return Vector2((x+1)*self.size.x/2, (1-y)*self.size.y/2)

    def window_to_world(self, point, canvas=None, *, output_size=None):
        screen = self.window_to_screen(point, output_size=output_size)
        return None if screen is None else self.screen_to_world(screen, canvas)

    def world_to_window(self, point, canvas=None, *, output_size=None):
        return self.screen_to_window(self.world_to_screen(point, canvas), output_size=output_size)

    @property
    def window(self):
        return self._window

    @property
    def objects(self):
        return tuple(self._objects)

    @property
    def world(self):
        return self._world

    @property
    def services(self):
        return self._services

    @property
    def resources(self):
        return self._resources

    @property
    def closed(self):
        return self._closed

    @property
    def running(self):
        return self._running

    @property
    def paused(self):
        return self._paused

    @paused.setter
    def paused(self, value):
        self._paused = bool(value)

    @property
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, value):
        if value is not None and value.game is not self:
            raise ValueError("Camera must be registered with this game")
        self._camera = value

    @property
    def audio_listener(self):
        return self._audio_listener

    @audio_listener.setter
    def audio_listener(self, value):
        if value is not None and value.game is not self:
            raise ValueError("Listener must be registered with this game")
        self._audio_listener = value

    @property
    def input(self):
        return self._input

    @property
    def audio(self):
        if self._audio is None:
            from ..audio.mixer import AudioMixer
            if self._persist_preferences:
                self._audio = AudioMixer(self, preferences=self._preferences('audio'),
                                         save=lambda data: self._remember_preferences('audio', data))
            else:
                self._audio = AudioMixer(self)
        return self._audio

    @property
    def debug(self):
        return self._debug

    @property
    def physics(self):
        if self._physics is None:
            from ..physics.world import PhysicsWorld
            self._physics = PhysicsWorld(self)
        return self._physics

    @property
    def ui(self):
        from ..gui.runtime import UI
        if self._ui is None:
            self._ui = UI(self)
        return self._ui

    @property
    def fps_limit(self):
        return self._fps_limit

    @fps_limit.setter
    def fps_limit(self, value):
        if not isfinite(value) or int(value) != value or value < 0:
            raise ValueError("fps_limit must be a nonnegative integer")
        self._fps_limit = int(value)
        if self.window:
            self.window.set_framerate_limit(self.fps_limit)

    @property
    def physics_fps(self):
        return self._physics_fps

    @physics_fps.setter
    def physics_fps(self, value):
        if not isfinite(value) or value <= 0:
            raise ValueError("physics_fps must be positive and finite")
        self._physics_fps = float(value)

    @property
    def clear_color(self):
        return self._clear_color

    @clear_color.setter
    def clear_color(self, value):
        self._clear_color = value

    def create_tween(self,*,owner=None):
        from ..animation.tween import Tween
        if owner is not None and (owner.game or owner._pending_game) is not self:raise ValueError('Tween owner must belong to this game')
        return self.add(Tween(owner=owner), scope=owner.scope if owner else None)

    def create_scope(self):
        return EntityScope(self)

    @contextmanager
    def _using_scope(self, scope):
        previous, self._active_scope = self._active_scope, scope
        try:
            yield
        finally:
            self._active_scope = previous

    def add(self, source, *, canvas=None, persistent=False, scope=None):
        if self.closed:
            raise RuntimeError("Game is closed")
        entity = instantiate(source)
        if not isinstance(entity, Entity):
            raise TypeError("Game.add expects an Entity, class or factory")
        if entity.game is not None or getattr(entity, "_pending_game", None) is not None:
            raise ValueError("Object is already registered or waiting to be added")
        scope = None if persistent else (scope or self._active_scope)
        if scope is not None and (scope.game is not self or scope.closed):
            raise ValueError("Scope must be open and belong to this game")
        if canvas is not None:
            entity.canvas = canvas
        entity._scope = scope
        if scope is not None:
            scope._members[entity] = None
        self._pending[entity] = bool(persistent)
        entity._pending_game = self
        self._schedule(self._add_now, entity, bool(persistent))
        if not self._dispatching:
            self.flush_deferred()
        return entity

    def _forget_scope(self, entity):
        if entity._scope is not None:
            entity._scope._members.pop(entity, None)
            entity._scope = None

    def _add_now(self, entity, persistent):
        with self._using_scope(entity._scope):
            self._register_now(entity, persistent)

    def _register_now(self, entity, persistent):
        if entity not in self._pending:
            return
        del self._pending[entity]
        entity._pending_game = None
        self._objects[entity] = persistent
        entity._game = self
        self._dispatching += 1
        pending_before = set(self._pending)
        try:
            if hasattr(entity,'_bind_resources'):entity._bind_resources(self.resources)
            if getattr(entity, "_is_physics_body", False):
                self.physics.add(entity)
            entity.on_added()
            entity.added.emit()
            if not entity._ready_called:
                entity.on_ready()
                entity._ready_called = True
                entity.ready.emit()
            self.object_added.emit(entity)
        except Exception:
            for pending in set(self._pending) - pending_before:
                pending._pending_game = None
                del self._pending[pending]
                self.services._forget(pending)
                self._forget_scope(pending)
            self._remove_now(entity)
            raise
        finally:
            self._dispatching -= 1

    def remove(self, entity):
        if entity in self._pending:
            del self._pending[entity]
            entity._pending_game = None
            self.services._forget(entity)
            self._forget_scope(entity)
            if getattr(entity,'_is_canvas_group',False):
                for member in entity.members:
                    if member.game is self or member._pending_game is self:self.remove(member)
            return
        if entity.game is not self:
            raise ValueError("Object is not registered with this game")
        if entity not in self._removing:
            self._removing.add(entity)
            self._schedule(self._remove_now, entity)
        if not self._dispatching:
            self.flush_deferred()

    def _remove_now(self, entity):
        if entity not in self._objects:
            return
        self._dispatching += 1
        try:
            entity.on_removed()
            entity.removed.emit()
        finally:
            if self._physics is not None and getattr(entity, "_is_physics_body", False):
                self.physics.remove(entity)
            self.input.release_source(entity)
            if not self.closed:
                for obj in self.objects:
                    if getattr(obj,'_tween_owner',None) is entity:obj.kill()
            self._objects.pop(entity, None)
            self._removing.discard(entity)
            self.services._forget(entity)
            if self.camera is entity:
                self._camera = None
            if self.audio_listener is entity:
                self._audio_listener = None
            group=entity._canvas_group
            if group is not None and group.game is self and group not in self._removing:group._forget(entity)
            entity._game = None
            self._forget_scope(entity)
            self._dispatching -= 1
        self.object_removed.emit(entity)

    def replace(self, *sources):
        """Replace temporary content; persistent objects and services survive."""
        entities = [instantiate(source) for source in sources]
        if len(set(map(id, entities))) != len(entities):
            raise ValueError("An object cannot be supplied twice")
        for entity in entities:
            if not isinstance(entity, Entity) or entity.game or getattr(entity, "_pending_game", None):
                raise ValueError("Replacement objects must be unregistered Entities")
        if self.closed:
            raise RuntimeError("Game is closed")
        for entity in entities:
            self._pending[entity] = False
            entity._pending_game = self
        self._schedule(self._replace_now, entities)
        if not self._dispatching:
            self.flush_deferred()

    def _replace_now(self, entities):
        outgoing_scopes = tuple(self._scopes)
        previous = [(obj, obj.canvas, obj.scope) for obj, persistent in self._objects.items() if not persistent]
        # Content queued by the outgoing objects must not leak into the new set.
        for obj, persistent in tuple(self._pending.items()):
            if not persistent and obj not in entities:
                del self._pending[obj]
                obj._pending_game = None
                self._forget_scope(obj)
        self._dispatching += 1
        try:
            for obj, _, _ in reversed(previous):
                self._remove_now(obj)
            try:
                for entity in entities:
                    self._add_now(entity, False)
            except Exception:
                for entity in entities:
                    if entity.game is self:
                        self._remove_now(entity)
                    if entity in self._pending:
                        del self._pending[entity]
                        entity._pending_game = None
                for obj, canvas, scope in previous:
                    obj.canvas = canvas
                    if scope is not None and not scope.closed:
                        obj._scope = scope
                        scope._members[obj] = None
                    self._pending[obj] = False
                    obj._pending_game = self
                    self._add_now(obj, False)
                raise
            for scope in outgoing_scopes:
                scope.close()
        finally:
            self._dispatching -= 1

    def call_deferred(self, callback, *args, **kwargs):
        scope = self._active_scope
        if scope is None:
            self._schedule(callback, *args, **kwargs)
        elif not scope.closed:
            self._schedule(scope._invoke, callback, *args, **kwargs)

    def _schedule(self, callback, *args, **kwargs):
        if self.closed:
            raise RuntimeError("Game is closed")
        self._deferred.append((callback, args, kwargs))

    def flush_deferred(self):
        if self._dispatching or self._flushing:
            return
        self._flushing = True
        try:
            # Newly queued work waits for the next boundary, preventing recursive loops.
            for _ in range(len(self._deferred)):
                callback, args, kwargs = self._deferred.popleft()
                callback(*args, **kwargs)
        finally:
            self._flushing = False

    def _process(self, method, dt, signal):
        self._dispatching += 1
        try:
            signal.emit(dt)
            for obj in self.objects:
                if obj.game is self and obj not in self._removing and obj.can_process():
                    with self._using_scope(obj.scope):
                        if method == "update":
                            obj._advance(dt)
                        getattr(obj, method)(dt)
        finally:
            self._dispatching -= 1
            self.flush_deferred()

    def update(self, dt):
        if self.closed:
            raise RuntimeError("Game is closed")
        if not isfinite(dt) or dt < 0:
            raise ValueError("Delta time must be finite and nonnegative")
        self.flush_deferred()
        self._refresh_screen_notifiers()
        if self._ui:
            self._ui.arrange()
        self.input.set_gui_captured(self._ui is not None and self._ui.keyboard_captured)
        if self.debug.enabled:
            self.debug._sample(dt)
        dt = min(dt,0.25)
        step = 1/self.physics_fps
        self._accumulator += dt
        try:
            steps = int((self._accumulator+step*1e-9)/step)
            if steps:
                with self.debug._measure('physics'):
                    for _ in range(steps):
                        if not self.running:
                            break
                        self._fixed_update(step)
                        self._accumulator = max(0, self._accumulator-step)
            if self.running:
                with self.debug._measure('update'):
                    self._process("update", dt, self.updated)
                    # Resolve followers after gameplay, independently of registration order.
                    for obj in self.objects:
                        if hasattr(obj, "_camera_update") and obj.can_process():
                            obj._camera_update(dt)
                    for obj in self.objects:
                        if hasattr(obj, "_listener_update") and obj.can_process():
                            obj._listener_update()
                    for obj in self.objects:
                        if getattr(obj, "_is_audio_player", False):
                            obj._audio_update(suspended=not obj.can_process())
        finally:
            self.input._end_frame()

    def _fixed_update(self, step):
        self.input._begin_physics()
        try:
            self._process("physics_update", step, self.physics_updated)
            for obj in self.objects:
                if hasattr(obj, "_sync_collisions"):
                    obj._sync_collisions()
            self.flush_deferred()
            if self._physics is not None and not self.paused:
                self._dispatching += 1
                try:
                    self.physics.step(step)
                finally:
                    self._dispatching -= 1
                self.flush_deferred()
        finally:
            self.input._end_physics()

    def draw_list(self):
        # A Canvas is one composited surface; equal orders keep registration order.
        indices={}
        for obj in self.objects:
            if not getattr(obj, '_is_screen_notifier', False):
                indices.setdefault(obj.canvas or self.world, len(indices))
        return sorted((obj for obj in self.objects if not getattr(obj, '_is_screen_notifier', False)
                       and obj.visible and obj not in self._removing),
                      key=lambda obj:((obj.canvas or self.world).order,indices[obj.canvas or self.world],obj.z_index))

    def _refresh_screen_notifiers(self):
        if not self._screen_notifiers:
            return
        views = {}
        self._dispatching += 1
        try:
            with self.debug._measure('update'):
                changes = []
                for notifier in tuple(self._screen_notifiers):
                    if notifier not in self._removing:
                        signal = notifier._update_visibility(views)
                        if signal is not None:
                            changes.append((notifier, signal))
                for notifier, signal in changes:
                    if notifier not in self._removing:
                        with self._using_scope(notifier.scope):
                            signal.emit()
        finally:
            self._dispatching -= 1
            self.flush_deferred()

    @staticmethod
    def _pixel_view(size):
        # SFML's default window view retains the dimensions from window creation.
        return View(Rect((0, 0), size))

    def make_view(self, canvas):
        view = self._pixel_view(self.size)
        camera = self.camera
        if not canvas.screen_space and camera is not None and camera.enabled:
            displacement = camera.screen_center - self.size / 2
            view.center = (self.size.x / 2 + displacement.x * canvas.parallax.x,
                           self.size.y / 2 + displacement.y * canvas.parallax.y)
            view.size = (self.size.x / camera.zoom.x, self.size.y / camera.zoom.y)
            view.rotation = camera.view_rotation
        return view

    def _draw_canvas_objects(self, target, objects, canvas, *, batch_owner=None):
        from ..rendering.batching import SpriteBatch, sprite_source, supports_pose
        from ..rendering.culling import ViewCuller, affine, pose

        view = self.make_view(canvas)
        batch = None
        known_pose = batch_owner is None or supports_pose(batch_owner)
        culler = ViewCuller(view) if self.culling and known_pose else None
        group = affine(pose(batch_owner)) if culler is not None and batch_owner is not None else None
        if self.batching and known_pose:
            owner = canvas if batch_owner is None else batch_owner
            batch = self._sprite_batches.get(owner)
            if batch is None:
                batch = self._sprite_batches[owner] = SpriteBatch()
            batch.begin(target, view, owner)
        try:
            for obj in objects:
                if getattr(obj, '_is_light', False) or getattr(obj, '_is_occluder', False) or getattr(obj, '_is_canvas_modulate', False):
                    continue
                sprite = sprite_source(obj) if batch is not None or culler is not None else None
                if sprite is not None:
                    position, quad = pose(obj), sprite._batch_quad()
                    if culler is not None and obj.cullable and not culler.sprite(quad, position, group):
                        continue
                    if batch is not None and obj.batchable:
                        batch.add(obj, sprite, position, quad)
                        continue
                if batch is not None:
                    batch.flush()
                target.view = view
                shader = obj.material._resolve(self.resources) if obj.material is not None else None
                states = RenderStates(transform=obj.transform, shader=shader)
                if getattr(obj, '_is_control', False) and self._ui:
                    self._ui.draw(obj, target, states)
                else:
                    obj.render(target, states)
            if batch is not None:
                batch.flush()
        finally:
            if batch is not None:
                batch.end()

    def create_render_texture(self, size=None):
        """Create an SFML render texture included in this game's debug draw count."""
        from ..rendering.targets import MeasuredTexture
        target = MeasuredTexture(*(self.size if size is None else self._dimensions(size)))
        target._debug = self.debug
        return target

    def render(self, target):
        self.debug._working_draw_calls = 0
        self.debug._counting_draws = self.debug.enabled
        try:
            with self.debug._measure('render'):
                self._render_frame(target)
        finally:
            self.debug._counting_draws = False
        self.debug._last_draw_calls = self.debug._working_draw_calls
        self.debug._publish_profile()

    def _render_frame(self, target):
        output_size = target.size
        if tuple(output_size) == tuple(self.size):
            self._render_content(target)
            return
        x, y, w, h = self.content_rect(output_size)
        if not w or not h:
            return
        if self._surface is None or tuple(self._surface.size) != tuple(self.size):
            self._surface = self.create_render_texture()
        surface = self._surface
        surface.reset_GL_states()
        surface.clear(self.clear_color)
        self._render_content(surface)
        surface.display()
        sprite = Sprite(surface.texture)
        sprite.position = (x, y)
        sprite.scale = (w/self.size.x, h/self.size.y)
        original = target.view
        target.reset_GL_states()
        target.view = self._pixel_view(output_size)
        try:
            target.clear(self.bar_color)
            target.draw(sprite)
        finally:
            target.view = original

    def _render_content(self, target):
        self.flush_deferred()
        original_view=target.view
        self._dispatching+=1
        try:
            if self._ui:self._ui.arrange()
            groups={}
            visible = self.draw_list()
            if self.debug.visible:
                self.debug._begin_frame()
            for obj in visible:
                if obj._canvas_group is None:groups.setdefault(obj.canvas or self.world,[]).append(obj)
            added_canvas = False
            for canvas in (self.world, self._ui.canvas if self._ui is not None else None):
                if canvas is not None and canvas.material is not None and canvas not in groups:
                    groups[canvas] = []
                    added_canvas = True
            layers = sorted(groups.items(), key=lambda pair: pair[0].order) if added_canvas else groups.items()
            for canvas, objects in layers:
                if canvas.material is None:
                    self._draw_layer(target, canvas, objects)
                else:
                    if self._canvas_effect is None:
                        from ..rendering.shader import CanvasEffect
                        self._canvas_effect = CanvasEffect(self)
                    self._canvas_effect.render(target, canvas.material,
                                               lambda surface: self._draw_layer(surface, canvas, objects))
            if self._ui:self._ui.draw_popup(target)
            if self.debug.visible:
                counting = self.debug._counting_draws
                self.debug._counting_draws = False
                try:
                    self.debug._draw(target, len(visible))
                finally:
                    self.debug._counting_draws = counting and self.debug.enabled
        finally:
            target.view=original_view
            self._dispatching-=1
            self.flush_deferred()

    def _draw_layer(self, target, canvas, objects):
        tint = canvas.ambient
        lit = canvas.lighting and ((tint.r, tint.g, tint.b, tint.a) != (255, 255, 255, 255) or any(
            (getattr(obj, '_is_canvas_modulate', False) or getattr(obj, '_is_light', False)) and obj.enabled
            for obj in objects))
        if lit:
            if self._lighting is None:
                from ..rendering.lighting import LightingRenderer
                self._lighting = LightingRenderer(self)
            self._lighting.render(target, canvas, objects, self._draw_canvas_objects)
        else:
            self._draw_canvas_objects(target, objects, canvas)

    def handle_event(self, event):
        self._dispatching += 1
        try:
            if self.debug._event(event):
                if event.type == Event.KEY_RELEASED:
                    self.input.handle_event(event, consumed=True)
                return True
            consumed = self._ui is not None and self._ui.handle_event(event)
            self.input.set_gui_captured(self._ui is not None and self._ui.keyboard_captured)
            self.input.handle_event(event,consumed=consumed)
            if consumed:
                return True
            for obj in reversed(self.draw_list()):
                if getattr(obj, "_is_control", False):
                    continue
                if obj not in self._removing and obj.can_process():
                    with self._using_scope(obj.scope):
                        if obj.handle_event(event):
                            return True
            return False
        finally:
            self._dispatching -= 1
            self.flush_deferred()

    def quit(self):
        self._running = False

    def close(self):
        if self.closed:
            return
        self._closed = True
        self.quit()
        for scope in tuple(self._scopes):
            scope._disconnect()
        self._scopes.clear()
        for obj in self._pending:
            self._forget_scope(obj)
            obj._pending_game = None
        self._pending.clear()
        self._deferred.clear()
        errors = []
        # Persistent services remain available during temporary objects' cleanup.
        ordered = sorted(self.objects, key=lambda obj: self._objects[obj])
        for obj in ordered:
            try:
                self._remove_now(obj)
            except Exception as error:
                errors.append(error)
        self.services._objects.clear()
        self.input.clear()
        if self._settings is not None:
            try:self._settings.flush()
            except Exception as error:errors.append(error)
        self.resources.clear()
        self._lighting=None
        self._canvas_effect = None
        self._surface=None
        self._sprite_batches.clear()
        if errors:
            raise errors[0]

    def run(self, *objects, max_frames=None):
        if self.window is not None or self.closed or not self.running:
            raise RuntimeError("Create a new Game before starting another run")
        if max_frames is not None and (int(max_frames) != max_frames or max_frames < 0):
            raise ValueError("max_frames must be a nonnegative integer")
        from ..rendering.targets import MeasuredWindow
        self._window = MeasuredWindow(VideoMode(*self.window_size), self.title)
        self._window._debug = self.debug
        try:
            self.window.set_framerate_limit(self.fps_limit)
            for obj in objects:
                self.add(obj)
            clock, frames = Clock(), 0
            while self.window.is_open and self.running:
                if max_frames is not None and frames >= max_frames:
                    break
                for event in self.window.events:
                    if event.type == Event.CLOSED:
                        self.quit()
                    self.handle_event(event)
                if not self.running:
                    break
                self.update(clock.restart().seconds)
                if not self.running:
                    break
                self.window.clear(self.clear_color)
                self.render(self.window)
                self.window.display()
                frames += 1
        finally:
            try:
                self.close()
            finally:
                self.window.close()
                self._window = None
