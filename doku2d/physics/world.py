from dataclasses import dataclass
from math import radians, degrees, exp, ceil, cos, hypot, isfinite, sin
import pymunk
from ..core.entity import Entity
from sfml.system import Vector2


@dataclass(frozen=True)
class Collision:
    collider: object
    normal: Vector2
    point: Vector2
    fraction: float = 0.0
    distance: float = 0.0


class PhysicsWorld:
    def __init__(self, game):
        self.game = game
        self._space = pymunk.Space()
        self._space.sleep_time_threshold = 0.5
        self._space.iterations = 20
        self._shapes = {}
        self._bodies = set()
        self._one_way_pairs = {}
        self._has_one_way = False
        self._substep = 0.0
        self._space.on_collision(None, None, begin=self._begin, pre_solve=self._pre_solve,
                                 post_solve=self._contact, separate=self._separate)

    @property
    def gravity(self):
        return Vector2(*self._space.gravity)

    @gravity.setter
    def gravity(self, value):
        self._space.gravity = tuple(Entity._vector(value))

    def _filter(self, entity):
        layer,mask = entity.collision_layer,entity.collision_mask
        if not (isinstance(layer,int) and isinstance(mask,int) and 0 <= layer <= 0xffffffff and 0 <= mask <= 0xffffffff):
            raise ValueError("Collision layers and masks must be 32-bit bit masks")
        return pymunk.ShapeFilter(categories=layer,mask=mask)

    def add(self, entity):
        kind = entity._body_kind
        if entity.freeze:
            kind = pymunk.Body.STATIC
        if kind == pymunk.Body.DYNAMIC:
            moment = float("inf") if entity.lock_rotation else entity.shape.moment(entity.mass,entity.scale)
            body = pymunk.Body(entity.mass,moment)
            body.velocity_func = self._velocity_function(entity)
        else:
            body = pymunk.Body(body_type=kind)
        body.position = tuple(entity.position)
        body.angle = radians(entity.rotation)
        shape = entity.shape.create(body,entity.scale)
        shape.filter = self._filter(entity)
        shape.sensor = entity._is_area
        shape.friction = entity.friction
        shape.elasticity = entity.elasticity
        self._space.add(body,shape)
        entity._last_step_rotation = body.angle
        entity._platform_angular_velocity = 0.0
        entity._last_step_position = Vector2(*body.position)
        entity._platform_velocity = Vector2(0,0)
        entity._native_body,entity._native_shape = body,shape
        self._shapes[shape] = entity
        self._bodies.add(entity)
        if kind != pymunk.Body.STATIC:
            body.velocity = tuple(entity._linear_velocity)
            body.angular_velocity = radians(entity._angular_velocity)
        if kind == pymunk.Body.DYNAMIC and entity._sleeping:
            body.sleep()

    def _velocity_function(self, entity):
        def integrate(body, gravity, damping, dt):
            pymunk.Body.update_velocity(body,gravity*entity.gravity_scale,
                                        damping*exp(-entity.linear_damp*dt),dt)
            if entity.angular_damp and body.angular_velocity:
                body.angular_velocity *= exp(-entity.angular_damp*dt)
            if getattr(entity,'_is_character',False):entity._project_motion(body)
        return integrate

    def remove(self, entity):
        if entity not in self._bodies:
            return
        body,shape = entity._native_body,entity._native_shape
        entity._position = Vector2(*body.position)
        entity._rotation = degrees(body.angle)
        entity._linear_velocity = Vector2(*body.velocity)
        entity._angular_velocity = degrees(body.angular_velocity)
        self._space.remove(shape,body)
        self._shapes.pop(shape,None)
        self._bodies.discard(entity)
        entity._native_body = entity._native_shape = None
        entity._contacts.clear()
        entity._overlaps.clear()
        for other in tuple(self._bodies):
            if other._is_area and entity in other._overlaps:
                other._overlaps.remove(entity)
                self._emit(other,"area_exited" if entity._is_area else "body_exited",entity)

    def rebuild(self, entity):
        self.remove(entity)
        self.add(entity)

    def reindex(self, entity):
        if entity._native_body is not None:
            self._space.reindex_shapes_for_body(entity._native_body)

    def _emit(self, entity, signal, other):
        if self.game.closed:
            return
        def emit():
            if entity.game is self.game and entity not in self.game._removing:
                getattr(entity,signal).emit(other)
        self.game.call_deferred(emit)

    def _pair(self, arbiter):
        return tuple(self._shapes.get(shape) for shape in arbiter.shapes)

    def _begin(self, arbiter, space, data):
        first,second = self._pair(arbiter)
        if first is None or second is None or first._is_area or second._is_area:
            return
        if not (first.one_way or second.one_way):
            self._emit(first,"body_entered",second)
            self._emit(second,"body_entered",first)

    @staticmethod
    def _one_way_up(platform):
        angle = platform._native_body.angle
        return Vector2(sin(angle), -cos(angle))

    def _pre_solve(self, arbiter, space, data):
        if not self._has_one_way:
            return
        first, second = self._pair(arbiter)
        if first is None or second is None or first._is_area or second._is_area:
            return
        if not (first.one_way or second.one_way):
            return
        platform, mover = (first, second) if first.one_way else (second, first)
        key = frozenset((platform, mover))
        previous = self._one_way_pairs.get(key)
        normal = arbiter.normal if first is platform else -arbiter.normal
        up = self._one_way_up(platform)
        allowed = previous is not False and not getattr(mover, '_drop_remaining', 0)
        allowed = allowed and normal.x*up.x + normal.y*up.y >= 0.5
        if allowed and previous is None:
            points = arbiter.contact_point_set.points
            if points:
                point = points[0].point_a if first is platform else points[0].point_b
                velocity = mover._native_body.velocity_at_world_point(point) - platform._native_body.velocity_at_world_point(point)
                speed = velocity.x*normal.x + velocity.y*normal.y
                depth = min(contact.distance for contact in points)
                allowed = speed <= 0.01 and depth - min(speed, 0)*self._substep >= -0.5
        arbiter.process_collision = allowed
        self._one_way_pairs[key] = allowed
        if previous is None and allowed:
            self._emit(first, 'body_entered', second)
            self._emit(second, 'body_entered', first)
        elif previous is True and not allowed:
            self._emit(first, 'body_exited', second)
            self._emit(second, 'body_exited', first)

    def _separate(self, arbiter, space, data):
        first,second = self._pair(arbiter)
        if first is None or second is None or first._is_area or second._is_area:
            return
        previous = self._one_way_pairs.pop(frozenset((first, second)), None)
        if previous is False or previous is None and (first.one_way or second.one_way):
            return
        self._emit(first,"body_exited",second)
        self._emit(second,"body_exited",first)

    def _contact(self, arbiter, space, data):
        first,second = self._pair(arbiter)
        if first is None or second is None:
            return
        points = arbiter.contact_point_set.points
        point = points[0].point_a if points else first._native_body.position
        normal = arbiter.normal
        first._contacts.append(Collision(second,Vector2(-normal.x,-normal.y),Vector2(*point)))
        second._contacts.append(Collision(first,Vector2(normal.x,normal.y),Vector2(*point)))

    def step(self, dt):
        if not isfinite(dt) or dt<=0:raise ValueError('Physics delta must be positive and finite')
        entities=tuple(self._bodies)
        self._has_one_way = any(entity.one_way for entity in entities)
        characters=[entity for entity in entities if getattr(entity,'_is_character',False)]
        driven=[]
        applied={entity:(entity._native_body.force,entity._native_body.torque) for entity in entities}
        for entity in entities:
            body,shape=entity._native_body,entity._native_shape
            shape_filter=self._filter(entity)
            if shape.filter!=shape_filter:shape.filter=shape_filter
            if shape.friction!=entity.friction:shape.friction=entity.friction
            if shape.elasticity!=entity.elasticity:shape.elasticity=entity.elasticity
            entity._platform_velocity=Vector2(*body.velocity)
            entity._platform_angular_velocity=body.angular_velocity
            if body.body_type==pymunk.Body.KINEMATIC and not entity._is_area:
                delta=Vector2(*body.position)-entity._last_step_position
                angle=(body.angle-entity._last_step_rotation+3.141592653589793)%(2*3.141592653589793)-3.141592653589793
                if hypot(*delta)>1e-8 or abs(angle)>1e-8:
                    driven.append((entity,Vector2(*body.velocity),body.angular_velocity))
                    entity._platform_velocity=delta/dt
                    entity._platform_angular_velocity=angle/dt
        # Navigation queries see the new position of a moved obstacle before
        # the solver rewinds it to simulate movement over the fixed step.
        for entity in characters:
            if entity.navigation is not None:
                entity.navigation._step(dt)
        for entity, _, _ in driven:
            body = entity._native_body
            body.position = tuple(entity._last_step_position)
            body.angle = entity._last_step_rotation
            body.velocity = tuple(entity._platform_velocity)
            body.angular_velocity = entity._platform_angular_velocity
            self.reindex(entity)
        for entity in characters:entity._prepare_motion(dt)
        smallest=min((min(entity._native_shape.bb.right-entity._native_shape.bb.left,
                          entity._native_shape.bb.top-entity._native_shape.bb.bottom)
                      for entity in entities if not entity._is_area),default=16)
        displacement=max((hypot(*entity._native_body.velocity)*dt for entity in entities),default=0)
        count=max(4,min(64,ceil(displacement/max(.5,smallest*.25))))
        substep=dt/count
        self._substep = substep
        for _ in range(count):
            for entity in entities:
                body=entity._native_body
                if getattr(entity,'_is_character',False):entity._motion_contacts=tuple(entity._contacts)
                if not body.is_sleeping:entity._contacts.clear()
                if body.body_type==pymunk.Body.DYNAMIC:
                    force,torque=applied[entity]
                    force=force+tuple(entity.force)
                    if force.x or force.y:body.force=force
                    if torque+entity.torque:body.torque=torque+entity.torque
            self._space.step(substep)
        for entity,velocity,angular in driven:
            entity._native_body.velocity=tuple(velocity)
            entity._native_body.angular_velocity=angular
        for entity in entities:
            body=entity._native_body
            entity._position=Vector2(*body.position)
            entity._rotation=degrees(body.angle)
            entity._linear_velocity=Vector2(*body.velocity)
            entity._angular_velocity=degrees(body.angular_velocity)
            entity._last_step_position=entity.position
            entity._last_step_rotation=body.angle
        for entity in characters:
            entity._finish_motion(dt)
            entity._drop_remaining = max(0.0, entity._drop_remaining-dt)
        self._update_areas()

    def floor_probe(self,entity,distance):
        from .body import dot
        up=entity.up_direction
        tangent=Vector2(-up.y,up.x)
        body,shape=entity._native_body,entity._native_shape
        if body is None:return None
        bb=shape.bb
        center=Vector2((bb.left+bb.right)/2,(bb.bottom+bb.top)/2)
        half=Vector2((bb.right-bb.left)/2,(bb.top-bb.bottom)/2)
        depth=abs(up.x)*half.x+abs(up.y)*half.y
        width=max(0,abs(tangent.x)*half.x+abs(tangent.y)*half.y-entity.safe_margin-.1)
        candidates=[]
        lift=max(2,entity.safe_margin+1)
        for offset in (-width,0,width):
            foot=center-up*depth+tangent*offset
            start,end=foot+up*lift,foot-up*(distance+entity.safe_margin)
            for hit in self._space.segment_query(tuple(start),tuple(end),0,
                        pymunk.ShapeFilter(categories=entity.collision_layer,mask=entity.collision_mask)):
                other=self._shapes.get(hit.shape)
                if other is None or other is entity or other._is_area or other in self.game._removing:continue
                collision=Collision(other,Vector2(*hit.normal),Vector2(*hit.point),hit.alpha,
                                    dot(foot-Vector2(*hit.point),up))
                if other.one_way:
                    same_floor = entity.is_on_floor() and entity._floor_hit.collider is other
                    if (entity._drop_remaining or self._one_way_pairs.get(frozenset((entity, other))) is False
                            or dot(collision.normal, self._one_way_up(other)) < 0.5
                            or not same_floor and dot(entity.velocity - Vector2(*other._platform_velocity), collision.normal) > 0.01):
                        continue
                if entity._floor(collision) and -.75<=collision.distance<=distance+entity.safe_margin:
                    candidates.append(collision)
        return min(candidates,key=lambda hit:hit.distance,default=None)

    def _update_areas(self):
        for entity in tuple(self._bodies):
            if entity._is_area:
                sensor = entity._native_shape
                overlaps = set()
                for shape, other in self._shapes.items():
                    if other is entity or not entity.collision_mask & other.collision_layer:
                        continue
                    if not sensor.bb.intersects(shape.bb):
                        continue
                    try:
                        touching = bool(sensor.shapes_collide(shape).points)
                    except AssertionError:
                        # Pymunk 7.x rejects the zero-contact result for disjoint
                        # shapes, even when their bounding boxes intersect.
                        touching = False
                    if touching:
                        overlaps.add(other)
                overlaps = {other for other in overlaps if not other._is_area or other.monitorable}
                if not entity.monitoring:
                    overlaps.clear()
                for other in overlaps-entity._overlaps:
                    self._emit(entity,"area_entered" if other._is_area else "body_entered",other)
                for other in entity._overlaps-overlaps:
                    self._emit(entity,"area_exited" if other._is_area else "body_exited",other)
                entity._overlaps = overlaps

    def raycast(self, start, end, *, mask=0xffffffff, exclude=(), areas=False):
        for hit in sorted(self._space.segment_query(tuple(start),tuple(end),0,pymunk.ShapeFilter(mask=mask)),key=lambda hit:hit.alpha):
            entity = self._shapes.get(hit.shape)
            if entity is not None and entity not in exclude and (areas or not entity._is_area):
                return Collision(entity,Vector2(*hit.normal),Vector2(*hit.point),hit.alpha)
        return None

    def _navigation_clear(self, start, end, radius, *, agent, ignored, tilemap):
        mask = self._filter(agent) if agent is not None else pymunk.ShapeFilter()
        start, end = tuple(start), tuple(end)
        if start == end:
            hits = self._space.point_query(start, radius, mask)
        else:
            hits = self._space.segment_query(start, end, radius, mask)
        for hit in hits:
            entity = self._shapes.get(hit.shape)
            if (entity is not None and entity is not agent and entity not in ignored
                    and entity not in self.game._removing and not hit.shape.sensor
                    and getattr(entity, '_tilemap_owner', None) is not tilemap):
                return False
        return True
