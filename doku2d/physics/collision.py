"""Collision filters and reusable physics query entities."""
from math import atan2, degrees

from sfml.system import Vector2
from ..core import Object,Entity
from .shapes import Circle
from .sweep import checked_shape


def bitmask(value):
    if not isinstance(value,int) or not 0<=value<=0xffffffff:raise ValueError('Expected a 32-bit collision mask')
    return value


class CollisionObject(Object):
    def __init__(self,name=None,*,layer=1,mask=1):
        super().__init__(name);self.layer=layer;self.mask=mask
    @property
    def layer(self):return self._layer
    @layer.setter
    def layer(self,value):self._layer=bitmask(value)
    @property
    def mask(self):return self._mask
    @mask.setter
    def mask(self,value):self._mask=bitmask(value)


class _Cast(Entity):
    def __init__(self,name=None,*,position=(0,0),target_position=(0,50),collision_mask=1,include_areas=False,exclude=()):
        super().__init__(name)
        self._target_position=Vector2(0,50);self._collision_mask=1;self._collision=None
        self.position=position;self.target_position=target_position;self.collision_mask=collision_mask
        self.enabled=True;self.include_areas=bool(include_areas);self.exclude=tuple(exclude)
    @property
    def target_position(self):return Vector2(*self._target_position)
    @target_position.setter
    def target_position(self,value):self._target_position=self._vector(value)
    @property
    def collision_mask(self):return self._collision_mask
    @collision_mask.setter
    def collision_mask(self,value):self._collision_mask=bitmask(value)
    @property
    def collision(self):return self._collision if self.enabled else None
    def _advance(self,dt):self.force_update()
    def is_colliding(self):return self.collision is not None
    def get_collider(self):return self.collision.collider if self.collision else None
    def get_collision_point(self):return Vector2(*self.collision.point) if self.collision else None
    def get_collision_normal(self):return Vector2(*self.collision.normal) if self.collision else None


class RayCast(_Cast):
    def force_update(self):
        if self.game is None:raise RuntimeError('Register the ray before querying')
        self._collision=self.game.physics.raycast(self.transform.transform_point((0,0)),
            self.transform.transform_point(self.target_position),mask=self.collision_mask,
            exclude=self.exclude,areas=self.include_areas) if self.enabled else None
        return self.collision


class ShapeCast(_Cast):
    """Sweep a circle or box each update and keep the first contact."""

    def __init__(self, shape=Circle(), *, name=None, position=(0, 0), target_position=(0, 50),
                 target=None, collision_mask=1, include_areas=False, exclude=()):
        super().__init__(name, position=position, target_position=target_position,
                         collision_mask=collision_mask, include_areas=include_areas, exclude=exclude)
        self.shape = shape
        self.target = target

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, value):
        self._shape = checked_shape(value)

    @property
    def target(self):
        """Optional entity whose coordinate system the cast follows."""
        return self._target

    @target.setter
    def target(self, value):
        if value is not None and (not isinstance(value, Entity) or value is self):
            raise TypeError('ShapeCast target must be another Entity or None')
        self._target = value

    def force_update(self):
        """Refresh and return the first contact, if any."""
        if self.game is None:
            raise RuntimeError('Register the shape cast before querying')
        if not self.enabled or (self.target is not None and self.target.game is not self.game):
            self._collision = None
            return None

        transform = self.transform
        excluded = tuple(self.exclude)
        if self.target is not None:
            parent = self.target.transform
            parent.combine(transform)
            transform = parent
            excluded += (self.target,)
        start = transform.transform_point((0, 0))
        end = transform.transform_point(self.target_position)
        right = transform.transform_point((1, 0)) - start
        rotation = degrees(atan2(right.y, right.x))
        self._collision = self.game.physics.shapecast(
            self.shape, start, end, rotation=rotation, mask=self.collision_mask,
            exclude=excluded, areas=self.include_areas)
        return self.collision


__all__=['CollisionObject','RayCast','ShapeCast']
