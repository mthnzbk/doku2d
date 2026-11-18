"""Canvas-local 2D lights and polygon/segment shadow occluders."""
from math import isfinite,hypot,cos,sin,pi,radians
from pathlib import Path
from sfml.graphics import Color,Texture,Transform
from sfml.system import Vector2
from ..core import Entity


def color(value):
    if isinstance(value,str):
        value=getattr(Color,value.upper(),None)
        if value is None:raise ValueError('Unknown color name')
    return Color(value.r,value.g,value.b,value.a) if isinstance(value,Color) else Color(*value)


def positive(value,name,zero=False):
    if not isfinite(value) or (value<0 if zero else value<=0):raise ValueError(f'{name} must be finite and positive')
    return float(value)


def mask(value):
    if not isinstance(value,int) or not 0<=value<=0xffffffff:raise ValueError('Light mask must be a 32-bit mask')
    return value


class Light(Entity):
    _is_light=True
    def __init__(self,name=None,*,position=(0,0),color='white',energy=1,shadow=False,target=None):
        super().__init__(name)
        self._enabled=True;self._color=Color.WHITE;self._energy=1;self._shadow=False
        self._light_mask=1;self._target=None
        self.position=position;self.color=color;self.energy=energy;self.shadow=shadow;self.target=target
    @property
    def enabled(self):return self._enabled
    @enabled.setter
    def enabled(self,value):self._enabled=bool(value)
    @property
    def color(self):return color(self._color)
    @color.setter
    def color(self,value):self._color=color(value)
    @property
    def energy(self):return self._energy
    @energy.setter
    def energy(self,value):self._energy=positive(value,'Light energy',True)
    @property
    def shadow(self):return self._shadow
    @shadow.setter
    def shadow(self,value):self._shadow=bool(value)
    @property
    def light_mask(self):return self._light_mask
    @light_mask.setter
    def light_mask(self,value):self._light_mask=mask(value)
    @property
    def target(self):return self._target
    @target.setter
    def target(self,value):
        if value is not None and not isinstance(value,Entity):raise TypeError('Light target must be an Entity or None')
        self._target=value
    @property
    def transform(self):
        transform=Transform()
        if self.target is not None:transform.combine(self.target.transform)
        transform.combine(Entity.transform.fget(self))
        return transform


class PointLight(Light):
    def __init__(self,name=None,*,radius=220,**options):
        super().__init__(name,**options)
        self._radius=220.;self._texture=None;self._offset=Vector2(0,0);self._texture_path=None;self._resources=None
        self._texture_scale=1.;self._falloff=1.6
        self.radius=radius
    @property
    def radius(self):return self._radius
    @radius.setter
    def radius(self,value):self._radius=positive(value,'Light radius')
    @property
    def falloff(self):return self._falloff
    @falloff.setter
    def falloff(self,value):self._falloff=positive(value,'Light falloff')
    @property
    def texture(self):return self._texture
    @texture.setter
    def texture(self,value):
        if isinstance(value,(str,Path)):
            self._texture_path=value
            resources=self._resources or (self.game.resources if self.game else None)
            value=resources.get_texture(value) if resources else None
        else:self._texture_path=None
        if value is not None and not isinstance(value,Texture):raise TypeError('Light texture must be a Texture, path or None')
        self._texture=value
    def _bind_resources(self,resources):
        self._resources=resources
        if self._texture_path is not None:
            path=self._texture_path;self.texture=resources.get_texture(path);self._texture_path=path

    @property
    def offset(self):return Vector2(*self._offset)
    @offset.setter
    def offset(self,value):self._offset=self._vector(value)
    @property
    def texture_scale(self):return self._texture_scale
    @texture_scale.setter
    def texture_scale(self,value):self._texture_scale=positive(value,'Texture scale')


class DirectionalLight(Light):
    def __init__(self,name=None,*,direction=(.6,1),shadow_length=1200,**options):
        super().__init__(name,**options)
        self._direction=Vector2(0,1);self._shadow_length=1200.
        self.direction=direction;self.shadow_length=shadow_length
    @property
    def direction(self):return Vector2(*self._direction)
    @direction.setter
    def direction(self,value):
        value=self._vector(value);length=hypot(*value)
        if not length:raise ValueError('Light direction cannot be zero')
        self._direction=value/length
    @property
    def shadow_length(self):return self._shadow_length
    @shadow_length.setter
    def shadow_length(self,value):self._shadow_length=positive(value,'Shadow length')
    @property
    def max_distance(self):return self.shadow_length
    @max_distance.setter
    def max_distance(self,value):self.shadow_length=value
    @property
    def ray_direction(self):
        transform=self.transform
        direction=transform.transform_point(self.direction)-transform.transform_point((0,0))
        length=hypot(*direction)
        return direction/length if length else self.direction


class LightOccluder(Entity):
    _is_occluder=True
    def __init__(self,points=None,*,name=None,position=(0,0),closed=True,target=None):
        super().__init__(name)
        self._points=();self._closed=bool(closed);self._enabled=True;self._light_mask=1;self._target=None
        self.points=points if points is not None else ((-20,-20),(20,-20),(20,20),(-20,20))
        self.position=position;self.target=target
    @property
    def points(self):return tuple(Vector2(*p) for p in self._points)
    @points.setter
    def points(self,value):
        points=tuple(tuple(self._vector(p)) for p in value)
        if len(points)<2:raise ValueError('Occluder needs at least two points')
        self._points=points
    @property
    def occluder(self):return self.points
    @occluder.setter
    def occluder(self,value):self.points=value
    @property
    def closed(self):return self._closed
    @closed.setter
    def closed(self,value):self._closed=bool(value)
    @property
    def enabled(self):return self._enabled
    @enabled.setter
    def enabled(self,value):self._enabled=bool(value)
    @property
    def light_mask(self):return self._light_mask
    @light_mask.setter
    def light_mask(self,value):self._light_mask=mask(value)
    @property
    def target(self):return self._target
    @target.setter
    def target(self,value):
        if value is not None and not isinstance(value,Entity):raise TypeError('Occluder target must be an Entity or None')
        self._target=value
    @property
    def transform(self):
        transform=Transform()
        if self.target is not None:transform.combine(self.target.transform)
        transform.combine(Entity.transform.fget(self))
        return transform
    @property
    def world_points(self):return tuple(self.transform.transform_point(p) for p in self._points)
    @classmethod
    def from_body(cls,body):
        from ..physics.shapes import Box,Circle,Polygon,Segment
        shape=body.shape
        if isinstance(shape,Box):
            w,h=shape.size;points=((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2))
        elif isinstance(shape,Circle):points=tuple((cos(i*2*pi/32)*shape.radius,sin(i*2*pi/32)*shape.radius) for i in range(32))
        elif isinstance(shape,Polygon):points=shape.vertices
        elif isinstance(shape,Segment):return cls((shape.start,shape.end),closed=False,target=body)
        else:raise TypeError('Unsupported occluder body shape')
        return cls(points,target=body)


__all__=['Light','PointLight','DirectionalLight','LightOccluder']
