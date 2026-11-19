"""CPU particles with bounded pools, world/local coordinates and simple presets."""
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain
from math import sin,cos,pi,sqrt,exp,hypot,isfinite,radians
from pathlib import Path
from random import Random
from sfml.graphics import (Color, Image, Texture, Sprite, CircleShape, RenderStates, RenderTexture,
                           BLEND_ADD, BLEND_ALPHA, PrimitiveType, Vertex, VertexArray)
from sfml.system import Vector2
from ..core import Entity,Signal
from ..animation.values import interpolate
from .culling import ViewCuller


@lru_cache(maxsize=1)
def _particle_mask():
    # Bake the same 12-sided outline once instead of tessellating it per particle.
    surface = RenderTexture(64, 64)
    surface.clear(Color(255, 255, 255, 0))
    surface.draw(CircleShape(32, 12))
    surface.display()
    texture = Texture.from_image(surface.texture.to_image())
    texture.smooth = True
    return texture


def positive(value,name,zero=False):
    if not isfinite(value) or (value<0 if zero else value<=0):raise ValueError(f'{name} must be finite and positive')
    return float(value)


def rgba(value):
    if isinstance(value,Color):return Color(value.r,value.g,value.b,value.a)
    return Color(*value)


def interval(value,name,minimum=0):
    if isinstance(value,(int,float)):value=(value,value)
    a,b=value
    if not all(isfinite(v) for v in (a,b)) or a>b or a<minimum:raise ValueError(f'{name} must be an ordered finite range')
    return float(a),float(b)


@dataclass
class _Particle:
    position:Vector2
    velocity:Vector2
    lifetime:float
    radius:float
    rotation:float
    spin:float
    age:float=0.0


class Particles(Entity):
    finished=Signal()
    cullable = True
    def __init__(self,name=None,*,position=(0,0),amount=64,lifetime=1,one_shot=False,emitting=True,seed=None):
        super().__init__(name)
        self._particles=[];self._texture=None;self._drawable=None;self._texture_path=None;self._resources=None
        self._batch_mesh = None
        self._clock=0.0;self._emitted=0;self._notified=False;self._has_emitted=False
        self._emitting=bool(emitting);self._local_coords=False
        self._random=Random(seed);self._seed=seed
        self._amount=64;self._amount_ratio=1.0;self._lifetime=1.0
        self._randomness=.2;self._explosiveness=0.0;self._speed_scale=1.0
        self._direction=Vector2(0,-1);self._spread=45.0;self._initial_velocity=(40,100)
        self._gravity=Vector2(0,120);self._damping=0.0;self._scale_range=(2,5);self._end_scale=0.0
        self._color=Color.WHITE;self._end_color=Color(255,255,255,0);self._color_ramp=()
        self._angular_velocity=(-90,90);self._rotation_range=(-180,180)
        self._emission_shape='point';self._emission_size=Vector2(20,20);self._emission_radius=10.0
        self._blend_mode='alpha';self.one_shot=bool(one_shot)
        self.position=position;self.amount=amount;self.lifetime=lifetime
    @property
    def alive_count(self):return len(self._particles)
    @property
    def emitting(self):return self._emitting
    @emitting.setter
    def emitting(self,value):
        value=bool(value)
        if value and not self._emitting:self._clock=0;self._emitted=0;self._notified=False
        self._emitting=value
    @property
    def amount(self):return self._amount
    @amount.setter
    def amount(self,value):
        if not isinstance(value,int) or not 1<=value<=10000:raise ValueError('Amount must be an integer in [1,10000]')
        self._amount=value
        if len(self._particles)>value:del self._particles[value:]
    @property
    def amount_ratio(self):return self._amount_ratio
    @amount_ratio.setter
    def amount_ratio(self,value):
        if not isfinite(value) or not 0<=value<=1:raise ValueError('amount_ratio must be in [0,1]')
        self._amount_ratio=float(value)
    @property
    def lifetime(self):return self._lifetime
    @lifetime.setter
    def lifetime(self,value):self._lifetime=positive(value,'Lifetime')
    @property
    def randomness(self):return self._randomness
    @randomness.setter
    def randomness(self,value):
        if not isfinite(value) or not 0<=value<1:raise ValueError('Randomness must be in [0,1)')
        self._randomness=float(value)
    @property
    def explosiveness(self):return self._explosiveness
    @explosiveness.setter
    def explosiveness(self,value):
        if not isfinite(value) or not 0<=value<=1:raise ValueError('Explosiveness must be in [0,1]')
        self._explosiveness=float(value)
    @property
    def speed_scale(self):return self._speed_scale
    @speed_scale.setter
    def speed_scale(self,value):self._speed_scale=positive(value,'Speed',True)
    @property
    def direction(self):return Vector2(*self._direction)
    @direction.setter
    def direction(self,value):
        value=self._vector(value);length=hypot(*value)
        if not length:raise ValueError('Direction cannot be zero')
        self._direction=value/length
    @property
    def spread(self):return self._spread
    @spread.setter
    def spread(self,value):
        if not isfinite(value) or not 0<=value<=360:raise ValueError('Spread must be in [0,360] degrees')
        self._spread=float(value)
    @property
    def initial_velocity(self):return self._initial_velocity
    @initial_velocity.setter
    def initial_velocity(self,value):self._initial_velocity=interval(value,'Velocity')
    @property
    def gravity(self):return Vector2(*self._gravity)
    @gravity.setter
    def gravity(self,value):self._gravity=self._vector(value)
    @property
    def damping(self):return self._damping
    @damping.setter
    def damping(self,value):self._damping=positive(value,'Damping',True)
    @property
    def scale_range(self):return self._scale_range
    @scale_range.setter
    def scale_range(self,value):self._scale_range=interval(value,'Size')
    @property
    def end_scale(self):return self._end_scale
    @end_scale.setter
    def end_scale(self,value):self._end_scale=positive(value,'End scale',True)
    @property
    def color(self):return rgba(self._color)
    @color.setter
    def color(self,value):self._color=rgba(value)
    @property
    def end_color(self):return rgba(self._end_color)
    @end_color.setter
    def end_color(self,value):self._end_color=rgba(value)
    @property
    def color_ramp(self):return tuple((t,rgba(c)) for t,c in self._color_ramp)
    @color_ramp.setter
    def color_ramp(self,value):
        values=tuple(sorted(((float(t),rgba(c)) for t,c in value),key=lambda item:item[0]))
        if values and (len(values)<2 or values[0][0]!=0 or values[-1][0]!=1 or len({t for t,c in values})!=len(values) or any(not isfinite(t) or not 0<=t<=1 for t,c in values)):
            raise ValueError('Color ramp needs unique keys from 0 to 1, including both endpoints')
        self._color_ramp=values
    @property
    def angular_velocity(self):return self._angular_velocity
    @angular_velocity.setter
    def angular_velocity(self,value):self._angular_velocity=interval(value,'Angular velocity',float('-inf'))
    @property
    def rotation_range(self):return self._rotation_range
    @rotation_range.setter
    def rotation_range(self,value):self._rotation_range=interval(value,'Rotation',float('-inf'))
    @property
    def emission_shape(self):return self._emission_shape
    @emission_shape.setter
    def emission_shape(self,value):
        if value not in ('point','box','circle'):raise ValueError('Emission shape must be point, box or circle')
        self._emission_shape=value
    @property
    def emission_size(self):return Vector2(*self._emission_size)
    @emission_size.setter
    def emission_size(self,value):
        value=self._vector(value)
        if min(value)<0:raise ValueError('Emission dimensions cannot be negative')
        self._emission_size=value
    @property
    def emission_radius(self):return self._emission_radius
    @emission_radius.setter
    def emission_radius(self,value):self._emission_radius=positive(value,'Emission radius',True)
    @property
    def local_coords(self):return self._local_coords
    @local_coords.setter
    def local_coords(self,value):
        if self.alive_count and bool(value)!=self._local_coords:raise RuntimeError('Clear particles before changing coordinate mode')
        self._local_coords=bool(value)
    @property
    def texture(self):return self._texture
    @texture.setter
    def texture(self,value):
        if isinstance(value,(str,Path)):
            self._texture_path=value
            resources=self._resources or (self.game.resources if self.game else None)
            value=resources.get_texture(value) if resources else None
        else:self._texture_path=None
        if value is not None and not isinstance(value,Texture):raise TypeError('Texture must be a Texture, path or None')
        self._texture=value;self._drawable=None
    def _bind_resources(self,resources):
        self._resources=resources
        if self._texture_path is not None:
            path=self._texture_path;self.texture=resources.get_texture(path);self._texture_path=path

    @property
    def blend_mode(self):return self._blend_mode
    @blend_mode.setter
    def blend_mode(self,value):
        if value not in ('alpha','add'):raise ValueError('Particle blending must be alpha or add')
        self._blend_mode=value
    @property
    def seed(self):return self._seed
    @seed.setter
    def seed(self,value):self._seed=value;self._random.seed(value)

    def restart(self,*,clear=True):
        if clear:self._particles.clear()
        self._clock=0;self._emitted=0;self._notified=False;self._has_emitted=False;self._emitting=True
    def clear(self):self._particles.clear();self._has_emitted=False;self._notified=False
    def burst(self,count=None):
        count=round(self.amount*self.amount_ratio) if count is None else count
        if not isinstance(count,int) or count<0:raise ValueError('Burst count must be a nonnegative integer')
        self._notified=False;self._has_emitted=True
        for _ in range(min(count,self.amount-self.alive_count)):
            self._particles.append(self._spawn());self._has_emitted=True

    def _spawn(self):
        rng=self._random;point=Vector2(0,0)
        if self.emission_shape=='box':point=Vector2(rng.uniform(-.5,.5)*self.emission_size.x,rng.uniform(-.5,.5)*self.emission_size.y)
        elif self.emission_shape=='circle':
            angle=rng.random()*2*pi;r=sqrt(rng.random())*self.emission_radius;point=Vector2(cos(angle)*r,sin(angle)*r)
        angle=radians(rng.uniform(-self.spread/2,self.spread/2));d=self.direction
        velocity=Vector2(d.x*cos(angle)-d.y*sin(angle),d.x*sin(angle)+d.y*cos(angle))*rng.uniform(*self.initial_velocity)
        radius=rng.uniform(*self.scale_range)
        rotation=rng.uniform(*self.rotation_range)
        if not self.local_coords:
            transform=self.transform;zero=transform.transform_point((0,0))
            point=transform.transform_point(point);velocity=transform.transform_point(velocity)-zero
            radius*=max(abs(self.scale.x),abs(self.scale.y));rotation+=self.rotation
        return _Particle(point,velocity,self.lifetime*rng.uniform(1-self.randomness,1+self.randomness),radius,rotation,rng.uniform(*self.angular_velocity))
    def _simulate(self,p,dt):
        p.age+=dt
        gravity=self.gravity
        if self.damping:
            decay=exp(-self.damping*dt);terminal=gravity/self.damping
            p.position+=(p.velocity-terminal)*((1-decay)/self.damping)+terminal*dt
            p.velocity=p.velocity*decay+terminal*(1-decay)
        else:p.position+=p.velocity*dt+gravity*(dt*dt/2);p.velocity+=gravity*dt
        p.rotation+=p.spin*dt
    def _advance(self,dt):
        dt*=self.speed_scale
        if not dt:return
        for p in self._particles:self._simulate(p,dt)
        self._particles=[p for p in self._particles if p.age<p.lifetime]
        remaining=dt;offset=0
        while self.emitting:
            span=min(remaining,max(0,self.lifetime-self._clock))
            count=round(self.amount*self.amount_ratio)
            window=self.lifetime*(1-self.explosiveness)
            while self._emitted<count:
                when=self._emitted*window/max(1,count)
                if when>self._clock+span+1e-10:break
                age=dt-(offset+max(0,when-self._clock))
                self._emitted+=1
                if self.alive_count<self.amount:
                    p=self._spawn();self._simulate(p,age)
                    if p.age<p.lifetime:self._particles.append(p)
                    self._has_emitted=True
            self._clock+=span;offset+=span;remaining-=span
            if self._clock>=self.lifetime-1e-10:
                if self.one_shot:self._emitting=False;self._has_emitted=True
                else:self._clock=0;self._emitted=0
            if remaining<=1e-10:break
        if not self.emitting and not self._particles and self._has_emitted and not self._notified:
            self._notified=True;self.finished.emit()
    def _particle_color(self,t):
        keys=self._color_ramp or ((0,self.color),(1,self.end_color))
        for (a,c1),(b,c2) in zip(keys,keys[1:]):
            if t<=b:return interpolate(c1,c2,(t-a)/(b-a))
        return keys[-1][1]

    def _visible_particles(self, target, states):
        visible = None
        if self.game is not None and self.game.culling and self.cullable and states.shader is None:
            visible = ViewCuller(target.view).circles(states.transform if self.local_coords else None)
        extent = sqrt(2) if self.texture is not None else 1
        end_scale = self.end_scale - 1
        for particle in self._particles:
            t = particle.age / particle.lifetime
            radius = particle.radius * (1 + end_scale*t)
            if visible is None or visible(particle.position.x, particle.position.y, radius*extent):
                yield particle, radius, t

    def render(self, target, states):
        if not self._particles:
            return
        visible = self._visible_particles(target, states)
        first = next(visible, None)
        if first is None:
            return
        visible = chain((first,), visible)
        if (len(self._particles) == 1 or states.shader is not None
                or (self.game is not None and not self.game.batching)):
            self._render_individually(target, states, visible)
            return
        if self._batch_mesh is None:
            self._batch_mesh = VertexArray(PrimitiveType.TRIANGLES_STRIP)
        mesh = self._batch_mesh
        mesh.clear()
        texture = self.texture or _particle_mask()
        width, height = texture.size
        extent = max(width, height)
        x, y = width/extent, height/extent
        strip = ((-x, -y, 0, 0), (x, -y, width, 0), (-x, y, 0, height), (x, y, width, height))
        previous = None
        for particle, radius, t in visible:
            angle = radians(particle.rotation)
            c, s = radius*cos(angle), radius*sin(angle)
            px, py = particle.position
            tint = self._particle_color(t)
            if tint.a == 0:
                continue
            for index, (x, y, u, v) in enumerate(strip):
                vertex = Vertex((px+x*c-y*s, py+x*s+y*c), tint, (u, v))
                if index == 0 and previous is not None:
                    mesh.append(previous)
                    mesh.append(vertex)
                mesh.append(vertex)
            previous = vertex
        if len(mesh):
            target.draw(mesh, RenderStates(texture=texture, blend_mode=BLEND_ADD if self.blend_mode == 'add' else BLEND_ALPHA,
                                           transform=states.transform if self.local_coords else None))

    def _render_individually(self,target,states,visible):
        if self._drawable is None:
            if self.texture:
                self._drawable=Sprite(self.texture);self._drawable.origin=self.texture.size/2
            else:self._drawable=CircleShape(1,12);self._drawable.origin=(1,1)
        drawable=self._drawable
        draw_states=RenderStates(blend_mode=BLEND_ADD if self.blend_mode=='add' else BLEND_ALPHA,
                                 transform=states.transform if self.local_coords else None, shader=states.shader)
        for p, size, t in visible:
            tint=self._particle_color(t)
            drawable.position=p.position;drawable.rotation=p.rotation
            if self.texture:
                factor=2*size/max(self.texture.size)
                drawable.scale=(factor,factor);drawable.color=tint
            else:drawable.scale=(size,size);drawable.fill_color=tint
            target.draw(drawable,draw_states)
    def on_removed(self):self.clear()
    @classmethod
    def sparks(cls,position=(0,0),**options):
        p=cls(position=position,**dict(dict(amount=70,lifetime=.7,one_shot=True,emitting=False),**options))
        p.explosiveness=1;p.spread=100;p.initial_velocity=(100,250);p.gravity=(0,380)
        p.scale_range=(1,3);p.color=(255,215,125);p.end_color=(240,70,25,0);p.blend_mode='add'
        return p
    @classmethod
    def smoke(cls,position=(0,0),**options):
        p=cls(position=position,**dict(dict(amount=45,lifetime=2.5),**options))
        p.spread=30;p.initial_velocity=(12,30);p.gravity=(0,-8);p.scale_range=(5,12);p.end_scale=2.5
        p.color=(150,164,180,95);p.end_color=(80,100,130,0)
        image=Image.create(32,32,Color.TRANSPARENT)
        for y in range(32):
            for x in range(32):
                alpha=round(255*max(0,1-hypot((x+.5)/16-1,(y+.5)/16-1))**2)
                image[x,y]=Color(255,255,255,alpha)
        p.texture=Texture.from_image(image);p.texture.smooth=True
        return p
    @classmethod
    def rain(cls,position=(0,0),**options):
        p=cls(position=position,**dict(dict(amount=220,lifetime=1.6),**options))
        p.direction=(0,1);p.spread=3;p.initial_velocity=(380,520);p.gravity=(0,0)
        p.emission_shape='box';p.emission_size=(1100,1);p.scale_range=(5,8);p.end_scale=.8
        p.rotation_range=(0,0);p.angular_velocity=(0,0)
        p.color=(140,188,230,180);p.end_color=(100,150,220,40)
        image=Image.create(2,12,Color.WHITE)
        for y in range(12):
            for x in range(2):image[x,y]=Color(255,255,255,round(30+200*y/11))
        p.texture=Texture.from_image(image);p.texture.smooth=True
        return p


__all__=['Particles']
