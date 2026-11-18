"""Property, callback and signal tracks using direct object references."""
from types import MappingProxyType
from math import isfinite
from bisect import bisect_right
from ..core.entity import Entity
from ..core.signal import Signal
from .values import Binding,interpolate,easing,duration


class Timeline:
    def __init__(self,length=None,*,loop=False):
        self._length=None if length is None else duration(length)
        self.loop=bool(loop);self._tracks=[];self._events=[]
    @property
    def length(self):
        return self._length if self._length is not None else max([keys[-1][0] for binding,keys,ease,mode in self._tracks]+[event[0] for event in self._events]+[0])
    def _check_time(self,time):
        time=duration(time)
        if self._length is not None and time>self._length:raise ValueError('Key exceeds the timeline length')
        return time
    def property(self,target,path,keys,*,ease='linear',interpolation='linear'):
        keys=tuple(sorted(((self._check_time(t),v) for t,v in keys),key=lambda item:item[0]))
        if not keys or len({t for t,v in keys})!=len(keys):raise ValueError('Use nonempty keys with unique times')
        if interpolation not in ('linear','step'):raise ValueError('Interpolation must be linear or step')
        easing(ease,.5)
        self._tracks.append((Binding(target,path),keys,ease,interpolation));return self
    def call(self,time,callback,*args,**kwargs):
        if not callable(callback):raise TypeError('Expected a callback')
        self._events.append((self._check_time(time),callback,args,kwargs));self._events.sort(key=lambda event:event[0]);return self
    def signal(self,time,signal,*args):return self.call(time,signal.emit,*args)
    def sample(self,time):
        for binding,keys,ease,mode in self._tracks:
            index=bisect_right([key[0] for key in keys],time)-1
            if index<0:value=keys[0][1]
            elif index>=len(keys)-1 or mode=='step':value=keys[index][1]
            else:
                a,v1=keys[index];b,v2=keys[index+1]
                value=interpolate(v1,v2,easing(ease,(time-a)/(b-a)))
            binding.set(value)


class AnimationPlayer(Entity):
    animation_started=Signal()
    animation_finished=Signal()
    animation_looped=Signal()
    def __init__(self,name=None,*,autoplay=None):
        super().__init__(name)
        self._animations={};self._animation='';self._playhead=0.0
        self._playing=False;self._speed_scale=1.0;self._playback_speed=1.0
        self._generation=0;self._pending_start=False;self.autoplay=autoplay
    @property
    def animations(self):return MappingProxyType(self._animations)
    @property
    def animation(self):return self._animation
    @property
    def playback_position(self):return self._playhead
    @property
    def playing(self):return self._playing
    @property
    def speed_scale(self):return self._speed_scale
    @speed_scale.setter
    def speed_scale(self,value):
        if not isfinite(value):raise ValueError('Animation speed must be finite')
        self._speed_scale=float(value)
    def add_animation(self,name,timeline):
        if not isinstance(name,str) or not name or not isinstance(timeline,Timeline):raise ValueError('Give a name and Timeline')
        if timeline.loop and timeline.length==0:raise ValueError('Looping timeline must have a positive length')
        self._animations[name]=timeline;return timeline
    def play(self,name=None,*,speed=1,from_end=False):
        name=name or self.animation
        if name not in self._animations:raise KeyError(f'Unknown animation: {name}')
        if not isfinite(speed):raise ValueError('Playback speed must be finite')
        self._generation+=1;self._animation=name;self._playback_speed=float(speed)
        self._playhead=self.animations[name].length if from_end else 0
        self._playing=True;self._pending_start=True
        self.animations[name].sample(self.playback_position);self.animation_started.emit(name)
    def play_backwards(self,name=None):self.play(name,speed=-1,from_end=True)
    def pause(self):self._playing=False
    def resume(self):
        if self.animation:self._playing=True
    def stop(self,*,reset=True):
        self._generation+=1;self._playing=False;self._pending_start=False
        if reset and self.animation:self._playhead=0;self.animations[self.animation].sample(0)
    def seek(self,time,*,update=True,events=False):
        if not self.animation:raise RuntimeError('Choose an animation before seeking')
        timeline=self.animations[self.animation];time=duration(time)
        if time>timeline.length:raise ValueError('Seek exceeds timeline length')
        old=self.playback_position;self._playhead=time;self._pending_start=False;self._generation+=1
        if update:timeline.sample(time)
        if events:self._events(timeline,old,time,self._generation,playback=False)
    def _events(self,timeline,old,new,generation,include_start=False,playback=True):
        reverse=new<old or new==old and self.speed_scale*self._playback_speed<0
        events=reversed(timeline._events) if reverse else timeline._events
        for time,callback,args,kwargs in tuple(events):
            crossed=(new<=time<old if reverse else old<time<=new) or include_start and time==old
            if crossed:
                callback(*args,**kwargs)
                if generation!=self._generation or playback and not self.playing:return False
        return True
    def _advance(self,dt):
        if not self.playing:return
        speed=self.speed_scale*self._playback_speed
        if not speed:return
        timeline=self.animations[self.animation];generation=self._generation
        if self._pending_start:
            self._pending_start=False
            if not self._events(timeline,self.playback_position,self.playback_position,generation,True):return
        remaining=dt*abs(speed);direction=1 if speed>0 else -1
        while self.playing:
            boundary=timeline.length if direction>0 else 0
            span=abs(boundary-self.playback_position);consumed=min(span,remaining)
            old=self.playback_position;self._playhead+=direction*consumed;remaining-=consumed
            if span-consumed<=1e-10:self._playhead=boundary
            timeline.sample(self.playback_position)
            if generation!=self._generation or not self.playing:return
            if not self._events(timeline,old,self.playback_position,generation):return
            if abs(self.playback_position-boundary)>1e-9:return
            if not timeline.loop:
                self._playing=False;self.animation_finished.emit(self.animation);return
            if timeline.length<=0:raise ValueError('Looping timeline must have a positive length')
            self._playhead=0 if direction>0 else timeline.length
            timeline.sample(self.playback_position);self.animation_looped.emit(self.animation)
            if generation!=self._generation or not self.playing:return
            if not self._events(timeline,self.playback_position,self.playback_position,generation,True):return
            if remaining<=1e-10:return
    def on_added(self):
        if self.autoplay:self.play(self.autoplay)
    def on_removed(self):self.stop(reset=False)


__all__=['Timeline','AnimationPlayer']
