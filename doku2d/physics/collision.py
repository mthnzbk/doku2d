"""Collision filters and a working ray query entity. Shapes live in shapes.py."""
from sfml.system import Vector2
from ..core import Object,Entity


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


class RayCast(Entity):
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
    def force_update(self):
        if self.game is None:raise RuntimeError('Register the ray before querying')
        self._collision=self.game.physics.raycast(self.transform.transform_point((0,0)),
            self.transform.transform_point(self.target_position),mask=self.collision_mask,
            exclude=self.exclude,areas=self.include_areas) if self.enabled else None
        return self.collision
    def _advance(self,dt):self.force_update()
    def is_colliding(self):return self.collision is not None
    def get_collider(self):return self.collision.collider if self.collision else None
    def get_collision_point(self):return Vector2(*self.collision.point) if self.collision else None
    def get_collision_normal(self):return Vector2(*self.collision.normal) if self.collision else None


__all__=['CollisionObject','RayCast']
