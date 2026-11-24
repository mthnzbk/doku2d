from math import cos, radians, acos, degrees, hypot, isfinite
import pymunk
from sfml.system import Vector2
from ..core.signal import Signal
from .physical import PhysicsBody
from .pathfollower import PathFollower


def dot(a,b):return a.x*b.x+a.y*b.y


def number(value,name,minimum=0,maximum=float('inf')):
    if not isfinite(value) or not minimum<=value<=maximum:raise ValueError(f'{name} must be finite and in [{minimum},{maximum}]')
    return float(value)


class CharacterBody(PhysicsBody):
    """Velocity-driven motor; floating by default, grounded for platform games."""
    _body_kind=pymunk.Body.DYNAMIC
    _is_character=True

    def __init__(self,name=None,*,motion_mode='floating',coyote_time=0,jump_buffer=0,**options):
        super().__init__(name,**options)
        self._up_direction=Vector2(0,-1)
        self._slide_on_ceiling=True
        self._stop_on_slope=True
        self._constant_speed=False
        self._block_on_wall=True
        self._max_angle=45.0
        self._snap_length=4.0
        self._on_leave='add_velocity'
        self._floor_layers=0xffffffff
        self._wall_layers=0
        self._safe_margin=.08
        self._lock_rotation=True
        self._friction=0.0
        self._floor_hit=None
        self._carry=Vector2(0,0)
        self._motion_start=self.position
        self._real_velocity=Vector2(0,0)
        self._last_velocity=Vector2(0,0)
        self._motion_contacts=()
        self._jump_requested=False
        self._motor_active=False
        self._motor_velocity=Vector2(0,0)
        self._navigation = None
        self._drop_remaining = 0.0
        self._coyote_remaining = 0.0
        self._buffered_jump = None
        self.coyote_time = coyote_time
        self.jump_buffer = jump_buffer
        self.motion_mode=motion_mode

    @property
    def navigation(self):
        return self._navigation

    def navigate_to(self, tilemap, target, **options):
        """Follow a TileMap or TileMapStream route to a world point or an Entity."""
        follower = PathFollower(self, tilemap, target, **options)
        if self.navigation is not None:
            self.navigation.stop()
        self._navigation = follower
        return follower

    @property
    def motion_mode(self):return self._motion_mode
    @motion_mode.setter
    def motion_mode(self,value):
        if value not in ('grounded','floating'):raise ValueError('motion_mode must be grounded or floating')
        self._motion_mode=value
        self.gravity_scale=1 if value=='grounded' else 0
        self._floor_hit=None
        self._coyote_remaining = 0.0
        self._buffered_jump = None

    @property
    def coyote_time(self):
        """Seconds during which a jump is allowed after walking off the floor."""
        return self._coyote_time

    @coyote_time.setter
    def coyote_time(self, value):
        self._coyote_time = number(value, 'coyote_time')
        self._coyote_remaining = min(self._coyote_remaining, self._coyote_time)

    @property
    def jump_buffer(self):
        """Seconds during which an airborne jump request can wait for landing."""
        return self._jump_buffer

    @jump_buffer.setter
    def jump_buffer(self, value):
        self._jump_buffer = number(value, 'jump_buffer')
        if self._jump_buffer == 0:
            self._buffered_jump = None
        elif self._buffered_jump is not None:
            speed, remaining = self._buffered_jump
            self._buffered_jump = (speed, min(remaining, self._jump_buffer))

    @property
    def up_direction(self):return Vector2(*self._up_direction)
    @up_direction.setter
    def up_direction(self,value):
        value=self._vector(value);length=hypot(*value)
        if not length:raise ValueError('Up direction cannot be zero')
        self._up_direction=value/length
    @property
    def max_angle(self):return self._max_angle
    @max_angle.setter
    def max_angle(self,value):self._max_angle=number(value,'max_angle',0,89.9)
    @property
    def snap_length(self):return self._snap_length
    @snap_length.setter
    def snap_length(self,value):self._snap_length=number(value,'snap_length')
    @property
    def safe_margin(self):return self._safe_margin
    @safe_margin.setter
    def safe_margin(self,value):self._safe_margin=number(value,'safe_margin')
    @property
    def on_leave(self):return self._on_leave
    @on_leave.setter
    def on_leave(self,value):
        if value not in ('add_velocity','add_upward_velocity','none'):raise ValueError('Unknown platform leave behavior')
        self._on_leave=value
    @property
    def floor_layers(self):return self._floor_layers
    @floor_layers.setter
    def floor_layers(self,value):
        if not isinstance(value,int) or not 0<=value<=0xffffffff:raise ValueError('floor_layers must be a 32-bit mask')
        self._floor_layers=value
    @property
    def wall_layers(self):return self._wall_layers
    @wall_layers.setter
    def wall_layers(self,value):
        if not isinstance(value,int) or not 0<=value<=0xffffffff:raise ValueError('wall_layers must be a 32-bit mask')
        self._wall_layers=value
    @property
    def slide_on_ceiling(self):return self._slide_on_ceiling
    @slide_on_ceiling.setter
    def slide_on_ceiling(self,value):self._slide_on_ceiling=bool(value)
    @property
    def stop_on_slope(self):return self._stop_on_slope
    @stop_on_slope.setter
    def stop_on_slope(self,value):self._stop_on_slope=bool(value)
    @property
    def constant_speed(self):return self._constant_speed
    @constant_speed.setter
    def constant_speed(self,value):self._constant_speed=bool(value)
    @property
    def block_on_wall(self):return self._block_on_wall
    @block_on_wall.setter
    def block_on_wall(self,value):self._block_on_wall=bool(value)

    def _floor(self,hit):return self.motion_mode=='grounded' and dot(hit.normal,self.up_direction)>=cos(radians(self.max_angle))-1e-7
    def _ceiling(self,hit):return self.motion_mode=='grounded' and dot(hit.normal,self.up_direction)<=-cos(radians(self.max_angle))+1e-7
    def is_on_floor(self):return self._floor_hit is not None and self._floor_hit.collider.game is self.game and self.game is not None
    def is_on_ceiling(self):return any(self._ceiling(hit) for hit in self.contacts)
    def is_on_wall(self):return any(not self._floor(hit) and not self._ceiling(hit) for hit in self.contacts)
    def get_floor_normal(self):return Vector2(*self._floor_hit.normal) if self.is_on_floor() else Vector2(0,0)
    def get_floor_angle(self):return degrees(acos(max(-1,min(1,dot(self.get_floor_normal(),self.up_direction))))) if self.is_on_floor() else 0.0
    def get_platform_velocity(self):return self._platform(self._floor_hit) if self.is_on_floor() else Vector2(0,0)
    def get_real_velocity(self):return Vector2(*self._real_velocity)
    def get_slide_collision_count(self):return len(self.contacts)
    def get_slide_collision(self,index):return self.contacts[index]

    def _platform(self,hit):
        if hit is None or hit.collider.game is not self.game:return Vector2(0,0)
        other=hit.collider
        velocity=Vector2(*getattr(other,'_platform_velocity',other.linear_velocity))
        angular=getattr(other,'_platform_angular_velocity',0)
        radius=hit.point-other.position
        return velocity+Vector2(-radius.y,radius.x)*angular

    def teleport(self,position):
        self.position=position
        self.reset_physics_interpolation()
        self.velocity=(0,0)
        self._last_velocity=Vector2(0,0)
        self._floor_hit=None
        self._contacts.clear()
        self._jump_requested=False
        self._drop_remaining = 0.0
        self._coyote_remaining = 0.0
        self._buffered_jump = None

    def drop_through(self, duration=0.2):
        """Release a one-way floor and ignore one-way surfaces briefly."""
        if not isfinite(duration) or duration <= 0:
            raise ValueError('Drop duration must be positive and finite')
        if not self.is_on_floor() or not self._floor_hit.collider.one_way:
            return False
        self._drop_remaining = float(duration)
        self._floor_hit = None
        self._coyote_remaining = 0.0
        self._buffered_jump = None
        self._contacts[:] = [hit for hit in self._contacts if not hit.collider.one_way]
        self._motion_contacts = tuple(hit for hit in self._motion_contacts if not hit.collider.one_way)
        if dot(self.velocity, self.up_direction) > 0:
            self.velocity -= self.up_direction * dot(self.velocity, self.up_direction)
        return True

    def jump(self,speed=360):
        """Start a jump and return True, or queue it when jump buffering is enabled."""
        speed = number(speed, 'Jump speed')
        if self.game is None or self._jump_requested:
            return False
        if self.is_on_floor() or self._coyote_remaining > 0:
            self._start_jump(speed)
            return True
        if self.motion_mode == 'grounded' and self.jump_buffer > 0:
            self._buffered_jump = (speed, self.jump_buffer)
        return False

    def _start_jump(self, speed):
        velocity = self.velocity
        up = self.up_direction
        self.velocity = velocity + up * (speed - dot(velocity, up))
        self._jump_requested = True
        self._coyote_remaining = 0.0
        self._buffered_jump = None

    def move_and_slide(self):
        if self.game is None:raise RuntimeError('Add the character to a Game first')
        self._motor_active=True
        self._motor_velocity=self.velocity
        return bool(self.contacts)

    def _prepare_motion(self,dt):
        self._motion_start=self.position
        self._carry=Vector2(0,0)
        if self.is_on_floor() and self._floor_hit.collider.collision_layer&self.floor_layers:
            self._carry=self._platform(self._floor_hit)
        elif self.wall_layers:
            for hit in self.contacts:
                if not self._floor(hit) and not self._ceiling(hit) and hit.collider.collision_layer&self.wall_layers:
                    self._carry=self._platform(hit);break
        self._motion_contacts=self.contacts
        # A jump supplied directly through velocity also suppresses floor snapping.
        self._jump_requested=self._jump_requested or dot(self.velocity,self.up_direction)>max(1,dot(self._last_velocity,self.up_direction)+1)
        self._native_body.velocity=tuple(self.velocity+self._carry)
        self._project_motion(self._native_body)

    def _project_motion(self,body):
        velocity=Vector2(*body.velocity)
        up=self.up_direction
        hits=list(self._motion_contacts)
        if self.is_on_floor() and self._floor_hit not in hits:hits.append(self._floor_hit)
        for hit in hits:
            other=hit.collider
            if other.game is not self.game or other._is_area:continue
            if other._body_kind==pymunk.Body.DYNAMIC and not other.freeze:continue
            platform=self._platform(hit)
            carry_layers=self.floor_layers if self._floor(hit) else self.wall_layers
            if not other.collision_layer&carry_layers:
                platform=hit.normal*dot(platform,hit.normal)
            relative=velocity-platform
            inward=dot(relative,hit.normal)
            if self._floor(hit) and self._jump_requested:continue
            if inward<0:
                if self._ceiling(hit) and not self.slide_on_ceiling:
                    relative=Vector2(0,0)
                elif self.motion_mode=='grounded' and 0<dot(hit.normal,up)<cos(radians(self.max_angle))-1e-7 and self.block_on_wall and (self.is_on_floor() or dot(self._motor_velocity,up)<=1):
                    relative=up*min(0,dot(relative,up))
                else:relative-=hit.normal*inward
            if self._floor(hit) and self._motor_active:
                tangent=Vector2(-up.y,up.x)
                requested=dot(self._motor_velocity,tangent)
                if self.stop_on_slope and abs(requested)<.01 and not self._jump_requested:
                    relative=Vector2(0,0)
                elif self.constant_speed and abs(requested)>.01 and not self._jump_requested:
                    slope=Vector2(hit.normal.y,-hit.normal.x)
                    if dot(slope,tangent)<0:slope=-slope
                    relative=slope*requested
            velocity=relative+platform
        body.velocity=tuple(velocity)

    def apply_floor_snap(self):
        if self.game is None or self.motion_mode!='grounded':return False
        hit=self.game.physics.floor_probe(self,self.snap_length)
        if hit is None:return False
        if hit.distance>self.safe_margin:self.position-=self.up_direction*(hit.distance-self.safe_margin)
        self._floor_hit=hit
        return True

    def _finish_motion(self,dt):
        was_floor=self.is_on_floor()
        self._native_body.velocity=tuple(Vector2(*self._native_body.velocity)-self._carry)
        self._linear_velocity=Vector2(*self._native_body.velocity)
        floors=[hit for hit in self.contacts if self._floor(hit)]
        hit=max(floors,key=lambda hit:dot(hit.normal,self.up_direction),default=None)
        if self.motion_mode=='grounded' and not self._jump_requested:
            probe=self.game.physics.floor_probe(self,self.snap_length if was_floor else self.safe_margin+.5)
            if probe is not None:
                hit=probe
                if was_floor and probe.distance>self.safe_margin:self.position-=self.up_direction*(probe.distance-self.safe_margin)
        if self._jump_requested and dot(self.velocity,self.up_direction)>1:hit=None
        self._floor_hit=hit
        if was_floor and hit is None and self.on_leave!='none':
            carry=self._carry
            if self.on_leave=='add_upward_velocity' and dot(carry,self.up_direction)<0:carry-=self.up_direction*dot(carry,self.up_direction)
            self.linear_velocity=self.velocity+carry
        if hit is not None and not self._jump_requested:
            velocity=self.velocity
            inward=dot(velocity,hit.normal)
            if inward<0:self.linear_velocity=velocity-hit.normal*inward
        self._real_velocity=(self.position-self._motion_start)/dt
        self._last_velocity=self.velocity
        if self._jump_requested:
            self._coyote_remaining = 0.0
        elif hit is not None or was_floor:
            self._coyote_remaining = self.coyote_time
        elif self._coyote_remaining > 0:
            self._coyote_remaining = max(0.0, self._coyote_remaining - dt)
        jumped = self._jump_requested
        self._jump_requested=False
        self._motor_active=False
        if self._buffered_jump is not None:
            speed, remaining = self._buffered_jump
            remaining -= dt
            if remaining <= 0:
                self._buffered_jump = None
            elif hit is not None and not jumped:
                self._start_jump(speed)
            else:
                self._buffered_jump = (speed, remaining)


class RigidBody(PhysicsBody):
    _body_kind=pymunk.Body.DYNAMIC


class StaticBody(PhysicsBody):
    _body_kind=pymunk.Body.STATIC


class AnimatableBody(PhysicsBody):
    _body_kind=pymunk.Body.KINEMATIC

    def move_to(self,position):self.position=position


class Area(PhysicsBody):
    _body_kind=pymunk.Body.KINEMATIC
    _is_area=True
    area_entered=Signal()
    area_exited=Signal()
    def __init__(self,name=None,**options):
        super().__init__(name,**options)
        self._monitoring=True
        self._monitorable=True
    @property
    def monitoring(self):return self._monitoring
    @monitoring.setter
    def monitoring(self,value):self._monitoring=bool(value)
    @property
    def monitorable(self):return self._monitorable
    @monitorable.setter
    def monitorable(self,value):self._monitorable=bool(value)
    def get_overlapping_bodies(self):return tuple(other for other in self._overlaps if not other._is_area)
    def get_overlapping_areas(self):return tuple(other for other in self._overlaps if other._is_area)


__all__=['CharacterBody','RigidBody','StaticBody','AnimatableBody','Area']
