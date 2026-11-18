from dataclasses import dataclass
from math import isfinite
import pymunk


@dataclass(frozen=True)
class Box:
    size: tuple = (32,32)

    def __post_init__(self):
        size = tuple(self.size)
        if len(size) != 2 or any(not isfinite(value) or value <= 0 for value in size):
            raise ValueError("Box dimensions must be positive and finite")
        object.__setattr__(self,"size",size)

    def create(self, body, scale):
        return pymunk.Poly.create_box(body,(self.size[0]*scale.x,self.size[1]*scale.y))

    def moment(self, mass, scale):
        return pymunk.moment_for_box(mass,(self.size[0]*scale.x,self.size[1]*scale.y))


@dataclass(frozen=True)
class Circle:
    radius: float = 16

    def __post_init__(self):
        if not isfinite(self.radius) or self.radius <= 0:
            raise ValueError("Circle radius must be positive and finite")

    def create(self, body, scale):
        if scale.x != scale.y:
            raise ValueError("Circle physics shapes require uniform scale")
        return pymunk.Circle(body,self.radius*scale.x)

    def moment(self, mass, scale):
        return pymunk.moment_for_circle(mass,0,self.radius*scale.x)


@dataclass(frozen=True)
class Polygon:
    vertices: tuple = ((-16,-16),(16,-16),(0,16))

    def __post_init__(self):
        points = tuple(tuple(point) for point in self.vertices)
        if len(points) < 3 or any(len(p) != 2 or not all(isfinite(v) for v in p) for p in points):
            raise ValueError('Polygon needs at least three finite 2D vertices')
        cross = []
        for i,a in enumerate(points):
            b,c = points[(i+1)%len(points)],points[(i+2)%len(points)]
            value=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
            if abs(value)>1e-8:cross.append(value)
        if not cross or min(cross)<0<max(cross):raise ValueError('Polygon must be convex and have nonzero area')
        object.__setattr__(self,'vertices',points)

    def create(self,body,scale):return pymunk.Poly(body,[(x*scale.x,y*scale.y) for x,y in self.vertices])
    def moment(self,mass,scale):return pymunk.moment_for_poly(mass,[(x*scale.x,y*scale.y) for x,y in self.vertices])


@dataclass(frozen=True)
class Segment:
    start: tuple = (-16,0)
    end: tuple = (16,0)
    radius: float = .5

    def __post_init__(self):
        for field in ('start','end'):
            value=tuple(getattr(self,field))
            if len(value)!=2 or not all(isfinite(v) for v in value):raise ValueError('Segment points must be finite')
            object.__setattr__(self,field,value)
        if self.start==self.end or not isfinite(self.radius) or self.radius<=0:raise ValueError('Segment needs length and a positive radius')
    def create(self,body,scale):
        return pymunk.Segment(body,(self.start[0]*scale.x,self.start[1]*scale.y),
                              (self.end[0]*scale.x,self.end[1]*scale.y),self.radius*min(scale.x,scale.y))
    def moment(self,mass,scale):
        return pymunk.moment_for_segment(mass,(self.start[0]*scale.x,self.start[1]*scale.y),
                                        (self.end[0]*scale.x,self.end[1]*scale.y),self.radius*min(scale.x,scale.y))


__all__ = ['Box','Circle','Polygon','Segment']
