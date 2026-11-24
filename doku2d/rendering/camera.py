"""A camera is an independent object; following never changes its target."""
from math import exp, sin, pi, cos, radians, isfinite
from random import Random
from sfml.system import Vector2
from ..core import Entity


class Camera(Entity):
    def __init__(self, name=None, *, target=None):
        super().__init__(name)
        self._offset = Vector2(0,0)
        self._enabled = True
        self._zoom = Vector2(1,1)
        self._limit_enable = True
        self._limit = [-10000000,-10000000,10000000,10000000]
        self._target = None
        self._dead_zone = Vector2(0,0)
        self._position_smoothing = False
        self._rotation_smoothing = False
        self._smoothing_speed = 8.0
        self._focus = None
        self._view_rotation = None
        self._shake = None
        self._shake_offset = Vector2(0,0)
        self._random = Random()
        self.target = target

    @property
    def target(self): return self._target
    @target.setter
    def target(self,value):
        if value is not None and not isinstance(value,Entity) and not callable(value):
            raise TypeError('Camera target must be an Entity, callable or None')
        self._target = value

    def follow(self, target, *, smoothing=8, dead_zone=(0,0)):
        self.target = target
        self.smoothing_speed = smoothing
        self.position_smoothing = smoothing > 0
        self.dead_zone = dead_zone
        self.reset_smoothing()
        return self

    @property
    def offset(self): return Vector2(*self._offset)
    @offset.setter
    def offset(self,value): self._offset = self._vector(value)
    @property
    def enabled(self): return self._enabled
    @enabled.setter
    def enabled(self,value): self._enabled = bool(value)
    @property
    def zoom(self): return Vector2(*self._zoom)
    @zoom.setter
    def zoom(self,value):
        value = self._vector(value)
        if value.x <= 0 or value.y <= 0: raise ValueError('Camera zoom must be positive')
        self._zoom = value
    @property
    def dead_zone(self): return Vector2(*self._dead_zone)
    @dead_zone.setter
    def dead_zone(self,value):
        value = self._vector(value)
        if value.x < 0 or value.y < 0: raise ValueError('Dead zone dimensions cannot be negative')
        self._dead_zone = value
    @property
    def smoothing_speed(self): return self._smoothing_speed
    @smoothing_speed.setter
    def smoothing_speed(self,value):
        if not isfinite(value) or value < 0: raise ValueError('Smoothing speed cannot be negative')
        self._smoothing_speed = float(value)
    @property
    def position_smoothing(self): return self._position_smoothing
    @position_smoothing.setter
    def position_smoothing(self,value): self._position_smoothing = bool(value)
    @property
    def smoothed(self): return self.position_smoothing
    @smoothed.setter
    def smoothed(self,value): self.position_smoothing = value
    @property
    def rotation_smoothing(self): return self._rotation_smoothing
    @rotation_smoothing.setter
    def rotation_smoothing(self,value): self._rotation_smoothing = bool(value)
    @property
    def limit_enable(self): return self._limit_enable
    @limit_enable.setter
    def limit_enable(self,value): self._limit_enable = bool(value)
    @property
    def limit(self): return list(self._limit)
    @limit.setter
    def limit(self,value):
        left,top,right,bottom = value
        if not all(isfinite(v) for v in value) or right <= left or bottom <= top:
            raise ValueError('Limits must be finite left, top, right, bottom coordinates')
        self._limit = [left,top,right,bottom]
    @property
    def bounds(self):
        left,top,right,bottom = self.limit
        return (left,top,right-left,bottom-top)
    @bounds.setter
    def bounds(self,value):
        x,y,w,h = value
        self.limit = (x,y,x+w,y+h)

    def _target_position(self):
        if self.target is None: return self.position
        return self._vector(self.target() if callable(self.target) else self.target.render_position)

    def reset_smoothing(self):
        self.position = self._target_position()
        self._focus = self.position
        self._view_rotation = self.rotation

    def shake(self, intensity=8, duration=.3, *, frequency=30):
        if not all(isfinite(v) for v in (intensity,duration,frequency)) or intensity < 0 or duration <= 0 or frequency <= 0:
            raise ValueError('Shake needs nonnegative intensity and positive duration/frequency')
        self._shake = [float(intensity),float(duration),float(frequency),0,
                       self._random.random()*2*pi,self._random.random()*2*pi]

    def stop_shake(self):
        self._shake = None
        self._shake_offset = Vector2(0,0)

    def _camera_update(self,dt):
        if self._focus is None: self.reset_smoothing()
        if self.target is not None:
            target,goal = self._target_position(),self.position
            half = self.dead_zone/2
            self.position = (target.x-max(-half.x,min(half.x,target.x-goal.x)),
                             target.y-max(-half.y,min(half.y,target.y-goal.y)))
        weight = 1-exp(-self.smoothing_speed*dt) if self.position_smoothing and self.smoothing_speed else 1
        self._focus += (self.position-self._focus)*weight
        angle_weight = 1-exp(-self.smoothing_speed*dt) if self.rotation_smoothing and self.smoothing_speed else 1
        self._view_rotation += ((self.rotation-self._view_rotation+180)%360-180)*angle_weight
        self._focus = self._clamp(self._focus+self.offset)-self.offset
        if self._shake:
            intensity,duration,frequency,elapsed,px,py = self._shake
            elapsed += dt
            self._shake[3] = elapsed
            if elapsed >= duration: self.stop_shake()
            else:
                amplitude = intensity*(1-elapsed/duration)**2
                self._shake_offset = Vector2(sin(elapsed*frequency*2*pi+px),sin(elapsed*frequency*2*pi*.83+py))*amplitude

    def _clamp(self,center):
        if not self.limit_enable or self.game is None: return Vector2(*center)
        left,top,right,bottom = self.limit
        half = Vector2(self.game.size.x/self.zoom.x/2,self.game.size.y/self.zoom.y/2)
        angle = radians(self.view_rotation)
        extent = Vector2(abs(cos(angle))*half.x+abs(sin(angle))*half.y,
                         abs(sin(angle))*half.x+abs(cos(angle))*half.y)
        def axis(value,low,high,size):
            return (low+high)/2 if high-low <= 2*size else max(low+size,min(high-size,value))
        return Vector2(axis(center.x,left,right,extent.x),axis(center.y,top,bottom,extent.y))

    @property
    def screen_center(self):
        focus = self.position if self._focus is None else self._focus
        if (self.game is not None and self.game.physics_interpolation and isinstance(self.target, Entity)
                and not self.position_smoothing and not any(self._dead_zone)):
            focus = self.target.render_position
        return self._clamp(focus + self.offset + self._shake_offset)
    @property
    def view_rotation(self): return self.rotation if self._view_rotation is None else self._view_rotation
    @property
    def current(self): return self.game is not None and self.game.camera is self
    def make_current(self):
        if self.game is None: raise RuntimeError('Add the camera to the Game first')
        self.game.camera = self
    def on_added(self):
        if self.enabled and self.game.camera is None: self.make_current()
    def on_removed(self):
        if self.current: self.game.camera = None
