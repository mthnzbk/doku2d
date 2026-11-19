from math import radians, degrees, hypot, isfinite
import pymunk
from sfml.graphics import Color, CircleShape, RectangleShape, ConvexShape, RenderStates, Transform
from sfml.system import Vector2
from ..core.entity import Entity
from ..core.signal import Signal
from .collision import CollisionObject
from .shapes import Box, Circle, Polygon, Segment


class PhysicsBody(Entity):
    body_entered = Signal()
    body_exited = Signal()
    _is_physics_body = True
    _is_area = False
    _body_kind = pymunk.Body.DYNAMIC

    def __init__(self, name=None, *, position=(0,0), size=(32,32), radius=None,
                 shape=None, color=None, mass=1, one_way=False):
        super().__init__(name)
        self._native_body = None
        self._native_shape = None
        self.collision_object = CollisionObject()
        self._shape = shape or (Circle(radius) if radius is not None else Box(size))
        if not isinstance(self._shape,(Box,Circle,Polygon,Segment)):
            raise TypeError("shape must be a Box, Circle, Polygon or Segment")
        self._mass = 1.0
        self.mass = mass
        self._gravity_scale = 1.0
        self._linear_velocity = Vector2(0,0)
        self._angular_velocity = 0.0
        self._linear_damp = 0.0
        self._angular_damp = 0.0
        self._lock_rotation = False
        self._freeze = False
        self._sleeping = False
        self._force = Vector2(0,0)
        self._torque = 0.0
        self._friction = 0.7
        self._elasticity = 0.0
        self._color = color
        self._sprite = None
        self._contacts = []
        self._overlaps = set()
        self.one_way = one_way
        self.position = position

    @property
    def one_way(self):
        """Allow passage from underneath a static or moving platform."""
        return self._one_way

    @one_way.setter
    def one_way(self, value):
        if value and (self._is_area or self._body_kind == pymunk.Body.DYNAMIC):
            raise ValueError('One-way platforms must be StaticBody or AnimatableBody objects')
        self._one_way = bool(value)

    @property
    def collision_object(self):return self._collision_object

    @collision_object.setter
    def collision_object(self,value):
        if not isinstance(value,CollisionObject):raise TypeError('collision_object must be a CollisionObject')
        self._collision_object=value

    @property
    def position(self):
        return Entity.position.fget(self)

    @position.setter
    def position(self, value):
        Entity.position.fset(self,value)
        if self._native_body is not None:
            self._native_body.position = tuple(self._position)
            self._native_body.activate()
            self.game.physics.reindex(self)

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        Entity.rotation.fset(self,value)
        if self._native_body is not None:
            self._native_body.angle = radians(self._rotation)
            self._native_body.activate()
            self.game.physics.reindex(self)

    @property
    def scale(self):
        return Entity.scale.fget(self)

    @scale.setter
    def scale(self, value):
        value = self._vector(value)
        if value.x <= 0 or value.y <= 0:
            raise ValueError("Physics scale must be positive")
        if isinstance(self.shape,Circle) and value.x != value.y:
            raise ValueError("Circle physics shapes require uniform scale")
        self._scale = value
        if self._native_body is not None:
            self.game.physics.rebuild(self)

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, value):
        if not isinstance(value,(Box,Circle,Polygon,Segment)):
            raise TypeError("shape must be a Box, Circle, Polygon or Segment")
        if isinstance(value,Circle) and self.scale.x != self.scale.y:
            raise ValueError("Circle physics shapes require uniform scale")
        self._shape = value
        if self._native_body is not None:
            self.game.physics.rebuild(self)

    def _navigation_radius(self):
        shape = self.shape
        sx, sy = self.scale
        if isinstance(shape, Circle):
            return shape.radius * sx
        if isinstance(shape, Box):
            return hypot(shape.size[0] * sx, shape.size[1] * sy) / 2
        if isinstance(shape, Segment):
            return max(hypot(x*sx, y*sy) for x, y in (shape.start, shape.end)) + shape.radius * min(sx, sy)
        return max(hypot(x*sx, y*sy) for x, y in shape.vertices)

    @property
    def mass(self):
        return self._mass

    @mass.setter
    def mass(self, value):
        if not isfinite(value) or value <= 0:
            raise ValueError("mass must be positive and finite")
        self._mass = float(value)
        if getattr(self,"_native_body",None) is not None and self._native_body.body_type == pymunk.Body.DYNAMIC:
            self._native_body.mass = self.mass
            self._native_body.moment = float("inf") if self.lock_rotation else self.shape.moment(self.mass,self.scale)

    @property
    def lock_rotation(self):
        return self._lock_rotation

    @lock_rotation.setter
    def lock_rotation(self, value):
        self._lock_rotation = bool(value)
        if self._native_body is not None and self._native_body.body_type == pymunk.Body.DYNAMIC:
            self._native_body.moment = float("inf") if self.lock_rotation else self.shape.moment(self.mass,self.scale)
            if self.lock_rotation:
                self.angular_velocity = 0

    @property
    def freeze(self):
        return self._freeze

    @freeze.setter
    def freeze(self, value):
        value = bool(value)
        if value != self._freeze:
            self._freeze = value
            if self._native_body is not None:
                self.game.physics.rebuild(self)

    @property
    def sleeping(self):
        if self._native_body is not None:
            return self._native_body.is_sleeping
        return self._sleeping

    @sleeping.setter
    def sleeping(self, value):
        self._sleeping = bool(value)
        if self._native_body is not None and self._native_body.body_type == pymunk.Body.DYNAMIC:
            if value:
                self._native_body.sleep()
            else:
                self._native_body.activate()

    @property
    def linear_velocity(self):
        if self._native_body is not None:
            return Vector2(*self._native_body.velocity)
        return Vector2(*self._linear_velocity)

    @linear_velocity.setter
    def linear_velocity(self, value):
        self._linear_velocity = self._vector(value)
        if self._native_body is not None:
            self._native_body.velocity = tuple(self._linear_velocity)
            self._native_body.activate()

    @property
    def velocity(self):
        return self.linear_velocity

    @velocity.setter
    def velocity(self, value):
        self.linear_velocity = value

    @property
    def angular_velocity(self):
        if self._native_body is not None:
            return degrees(self._native_body.angular_velocity)
        return self._angular_velocity

    @angular_velocity.setter
    def angular_velocity(self, value):
        if not isfinite(value):
            raise ValueError("Angular velocity must be finite")
        self._angular_velocity = float(value)
        if self._native_body is not None:
            self._native_body.angular_velocity = radians(value)

    @property
    def collision_layer(self):
        return self.collision_object.layer

    @collision_layer.setter
    def collision_layer(self, value):
        if not isinstance(value,int) or not 0 <= value <= 0xffffffff:
            raise ValueError("Collision layer must be a 32-bit mask")
        self.collision_object.layer = value

    @property
    def collision_mask(self):
        return self.collision_object.mask

    @collision_mask.setter
    def collision_mask(self, value):
        if not isinstance(value,int) or not 0 <= value <= 0xffffffff:
            raise ValueError("Collision mask must be a 32-bit mask")
        self.collision_object.mask = value

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value

    @property
    def sprite(self):
        return self._sprite

    @sprite.setter
    def sprite(self, value):
        if value is not None and (not isinstance(value,Entity) or value.game is not None):
            raise TypeError("sprite must be an unregistered visual Entity")
        self._sprite = value
        if value is not None and self.game is not None and hasattr(value,'_bind_resources'):
            value._bind_resources(self.game.resources)

    def _bind_resources(self,resources):
        if self.sprite is not None and hasattr(self.sprite,'_bind_resources'):self.sprite._bind_resources(resources)

    @property
    def contacts(self):
        return tuple(self._contacts)

    def apply_impulse(self, impulse):
        impulse = self._vector(impulse)
        if self._native_body is None:
            self.velocity += impulse/self.mass
        elif self._native_body.body_type == pymunk.Body.DYNAMIC:
            self._native_body.apply_impulse_at_local_point(tuple(impulse))

    def apply_force(self, force):
        if self._native_body is None:
            raise RuntimeError("Add the body to a Game before applying a force")
        self._native_body.apply_force_at_local_point(tuple(self._vector(force)))

    def _advance(self, dt):
        if self.sprite is not None and hasattr(self.sprite,"advance"):
            self.sprite.advance(dt)

    def render(self, target, states):
        if self.sprite is not None:
            transform = Transform()
            transform.combine(states.transform)
            transform.combine(self.sprite.transform)
            material = self.sprite.material
            shader = material._resolve(self.game.resources if self.game else None) if material else states.shader
            if self.game is not None and self.game.culling and shader is None and getattr(self.sprite, 'cullable', False):
                from ..rendering.batching import sprite_source
                from ..rendering.culling import ViewCuller, transform_affine
                visual = sprite_source(self.sprite)
                if visual is not None and not ViewCuller(target.view).rectangle(visual._batch_quad(), transform_affine(transform)):
                    return
            self.sprite.render(target,RenderStates(transform=transform, shader=shader))
            return
        if self.color is None:
            return
        if isinstance(self.shape,Box):
            drawable = RectangleShape(self.shape.size)
            drawable.origin = (self.shape.size[0]/2,self.shape.size[1]/2)
        elif isinstance(self.shape,Polygon):
            drawable = ConvexShape(len(self.shape.vertices))
            for index,point in enumerate(self.shape.vertices): drawable.set_point(index,point)
        elif isinstance(self.shape,Segment):
            from math import atan2, hypot
            a,b = self.shape.start,self.shape.end
            drawable = RectangleShape((hypot(b[0]-a[0],b[1]-a[1]),2*self.shape.radius))
            drawable.origin = (0,self.shape.radius)
            drawable.position = a
            drawable.rotation = degrees(atan2(b[1]-a[1],b[0]-a[0]))
        else:
            drawable = CircleShape(self.shape.radius,40)
            drawable.origin = (self.shape.radius,self.shape.radius)
        drawable.fill_color = self.color if isinstance(self.color,Color) else Color(*self.color)
        target.draw(drawable,states)

    @property
    def gravity_scale(self):
        return self._gravity_scale

    @gravity_scale.setter
    def gravity_scale(self, value):
        if not isfinite(value):
            raise ValueError("Physics values must be finite")
        self._gravity_scale = float(value)

    @property
    def linear_damp(self):
        return self._linear_damp

    @linear_damp.setter
    def linear_damp(self, value):
        if not isfinite(value):
            raise ValueError("Physics values must be finite")
        if value < 0:
            raise ValueError("Physics coefficients cannot be negative")
        self._linear_damp = float(value)

    @property
    def angular_damp(self):
        return self._angular_damp

    @angular_damp.setter
    def angular_damp(self, value):
        if not isfinite(value):
            raise ValueError("Physics values must be finite")
        if value < 0:
            raise ValueError("Physics coefficients cannot be negative")
        self._angular_damp = float(value)

    @property
    def force(self):
        return self._force

    @force.setter
    def force(self, value):
        self._force = self._vector(value)

    @property
    def torque(self):
        return self._torque

    @torque.setter
    def torque(self, value):
        if not isfinite(value):
            raise ValueError("Physics values must be finite")
        self._torque = float(value)

    @property
    def friction(self):
        return self._friction

    @friction.setter
    def friction(self, value):
        if not isfinite(value):
            raise ValueError("Physics values must be finite")
        if value < 0:
            raise ValueError("Physics coefficients cannot be negative")
        self._friction = float(value)

    @property
    def elasticity(self):
        return self._elasticity

    @elasticity.setter
    def elasticity(self, value):
        if not isfinite(value):
            raise ValueError("Physics values must be finite")
        if value < 0:
            raise ValueError("Physics coefficients cannot be negative")
        self._elasticity = float(value)
