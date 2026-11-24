"""Independent game objects registered directly with Game."""
from math import isfinite
from sfml.graphics import Transform
from sfml.system import Vector2
from .signal import Signal


class Object:
    def __init__(self,name=None):self._name=name or type(self).__name__

    @property
    def name(self):return self._name

    @name.setter
    def name(self,value):
        if not isinstance(value,str) or not value:raise ValueError('Name must be nonempty')
        self._name=value


class Entity(Object):
    added = Signal()
    removed = Signal()
    ready = Signal()

    def __init__(self, name=None):
        self._name = name or type(self).__name__
        self._game = None
        self._pending_game = None
        self._canvas = None
        self._material = None
        self._scope = None
        self._screen_blocks = None
        self._canvas_group = None
        self._position = Vector2(0, 0)
        self._rotation = 0.0
        self._scale = Vector2(1, 1)
        self._visible = True
        self._z_index = 0
        self._y_sort_offset = 0.0
        self._process_mode = "pausable"
        self._ready_called = False

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, str) or not value:
            raise ValueError("name must be a nonempty string")
        self._name = value

    @property
    def game(self):
        return self._game

    @property
    def scope(self):
        return self._scope

    @property
    def input(self):
        return self.game.input if self.game is not None else None

    def _advance(self, dt):
        pass

    @property
    def material(self):
        return self._material

    @material.setter
    def material(self, value):
        from ..rendering.shader import checked_material
        self._material = checked_material(value)

    @property
    def canvas(self):
        if self._canvas is not None:return self._canvas
        group=self._canvas_group
        if group is None:return None
        owner=group.game or group._pending_game
        return group.canvas or (owner.world if owner else None)

    @canvas.setter
    def canvas(self, value):
        from .canvas import Canvas
        if value is not None and not isinstance(value, Canvas):
            raise TypeError("canvas must be a Canvas or None")
        self._canvas = value

    @property
    def position(self):
        return Vector2(*self._position)

    @position.setter
    def position(self, value):
        self._position = self._vector(value)

    @staticmethod
    def _vector(value):
        x, y = value
        if not isfinite(x) or not isfinite(y):
            raise ValueError("Coordinates must be finite")
        return Vector2(x, y)

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        if not isfinite(value):
            raise ValueError("rotation must be finite")
        self._rotation = float(value)

    @property
    def scale(self):
        return Vector2(*self._scale)

    @scale.setter
    def scale(self, value):
        self._scale = self._vector(value)

    @property
    def transform(self):
        return self._transform_at(self.position, self.rotation)

    def _transform_at(self, position, rotation):
        transform = Transform()
        if self._canvas_group is not None:transform.combine(self._canvas_group.transform)
        transform.translate(position)
        transform.rotate(rotation)
        transform.scale(self.scale)
        return transform

    @property
    def render_position(self):
        """Position used to draw this entity."""
        return self.position

    @property
    def render_rotation(self):
        """Rotation used to draw this entity, in degrees."""
        return self.rotation

    @property
    def render_transform(self):
        """Transform used for drawing, including any physics interpolation."""
        return self.transform

    @property
    def visible(self):
        return self._visible and (self._canvas_group is None or self._canvas_group.visible)

    @visible.setter
    def visible(self, value):
        self._visible = bool(value)

    @property
    def z_index(self):
        return self._z_index

    @z_index.setter
    def z_index(self, value):
        self._z_index = int(value)

    @property
    def y_sort_offset(self):
        """Vertical offset of the world-space depth anchor, in world units."""
        return self._y_sort_offset

    @y_sort_offset.setter
    def y_sort_offset(self, value):
        if not isfinite(value):
            raise ValueError("y_sort_offset must be finite")
        self._y_sort_offset = float(value)

    @property
    def process_mode(self):
        return self._process_mode

    @process_mode.setter
    def process_mode(self, value):
        if value not in ("pausable", "always", "when_paused", "disabled"):
            raise ValueError("Invalid process mode")
        self._process_mode = value

    def can_process(self):
        if self._screen_blocks and any(notifier.game is self.game for notifier in self._screen_blocks):
            return False
        paused = self.game is not None and self.game.paused
        return (self.process_mode == "always"
                or self.process_mode == "when_paused" and paused
                or self.process_mode == "pausable" and not paused)

    def create_tween(self):
        game=self.game or self._pending_game
        if game is None:raise RuntimeError('Add the object to a Game first')
        return game.create_tween(owner=self)

    def destroy(self):
        if self.game is not None:
            self.game.remove(self)

    def on_added(self):
        """Called each time this object is registered with a game."""
        pass

    def on_ready(self):
        """Called once, after the first successful on_added."""
        pass

    def on_removed(self):
        pass

    def update(self, dt):
        pass

    def physics_update(self, dt):
        pass

    def handle_event(self, event):
        return False

    def render(self, target, states):
        pass
