"""Small fluent tweens: sequential by default, parallel when requested."""
from copy import copy
from math import isfinite
from ..core.entity import Entity
from ..core.signal import Signal
from .values import Binding,interpolate,easing,duration


class PropertyTweener:
    def __init__(self,target,path,value,seconds,*,delay=0,ease='linear',from_value=None):
        self.binding=Binding(target,path);self.value=copy(value)
        self.duration=duration(seconds);self.delay=duration(delay)
        self.ease=ease;easing(ease,.5)
        self.start=copy(from_value);self.captured=from_value is not None;self.relative=False
    @property
    def length(self):return self.delay+self.duration
    def set_delay(self,value):self.delay=duration(value);return self
    def set_ease(self,value):easing(value,.5);self.ease=value;return self
    def from_(self,value):self.start=copy(value);self.captured=True;return self
    def from_current(self):return self.from_(self.binding.get())
    def as_relative(self):self.relative=True;return self
    def reset(self):pass
    def apply(self,time):
        if time<self.delay:return
        if not self.captured:self.start=self.binding.get();self.captured=True
        if self.relative and isinstance(self.start,(tuple,list)):
            if len(self.start)!=len(self.value):raise ValueError('Relative vectors need equal dimensions')
            target=type(self.start)(a+b for a,b in zip(self.start,self.value))
        else:target=self.start+self.value if self.relative else self.value
        t=1 if not self.duration else min(1,(time-self.delay)/self.duration)
        self.binding.set(copy(target) if t>=1 else interpolate(self.start,target,easing(self.ease,t)))


class _Callback:
    def __init__(self,callback,args,kwargs,delay):
        self.callback,self.args,self.kwargs=callback,args,kwargs
        self.length=duration(delay);self.called=False
    def reset(self):self.called=False
    def apply(self,time):
        if time>=self.length and not self.called:
            self.called=True;self.callback(*self.args,**self.kwargs)


class _Interval:
    def __init__(self,value):self.length=duration(value)
    def reset(self):pass
    def apply(self,time):pass


class Tween(Entity):
    finished=Signal()
    loop_finished=Signal()
    step_finished=Signal()
    def __init__(self,*,owner=None,auto_remove=True):
        super().__init__()
        self._tween_owner=owner
        self._stages=[];self._parallel=False;self._next_parallel=None
        self._stage=0;self._elapsed=0;self._cycles=0;self._loops=1
        self._running=True;self._completed=False;self._killed=False
        self._speed_scale=1.0;self._ease='linear';self.auto_remove=bool(auto_remove);self._generation=0
        if owner is not None:self.process_mode=owner.process_mode
    @property
    def running(self):return self._running and not self._killed and not self._completed
    @property
    def completed(self):return self._completed
    @property
    def speed_scale(self):return self._speed_scale
    @speed_scale.setter
    def speed_scale(self,value):
        if not isfinite(value) or value<0:raise ValueError('Tween speed must be finite and nonnegative')
        self._speed_scale=float(value)
    def set_ease(self,value):easing(value,.5);self._ease=value;return self
    def set_parallel(self,value=True):self._parallel=bool(value);return self
    def parallel(self):self._next_parallel=True;return self
    def chain(self):self._next_parallel=False;return self
    def set_loops(self,count=0):
        if not isinstance(count,int) or count<0:raise ValueError('Loop count must be a nonnegative integer; 0 means forever')
        self._loops=count;return self
    def _append(self,task):
        if self._killed:raise RuntimeError('Cannot add to a killed Tween')
        parallel=self._parallel if self._next_parallel is None else self._next_parallel
        self._next_parallel=None
        if parallel and self._stages:self._stages[-1].append(task)
        else:self._stages.append([task])
        return task
    def tween_property(self,target,path,value,seconds,*,delay=0,ease=None,from_value=None):
        return self._append(PropertyTweener(target,path,value,seconds,delay=delay,ease=ease or self._ease,from_value=from_value))
    def tween_callback(self,callback,*args,delay=0,**kwargs):
        if not callable(callback):raise TypeError('Expected a callable')
        self._append(_Callback(callback,args,kwargs,delay));return self
    def tween_interval(self,seconds):self._append(_Interval(seconds));return self
    def pause(self):self._running=False;return self
    def play(self):
        if self._killed:raise RuntimeError('Killed Tween cannot be resumed')
        if self.completed:return self.restart()
        self._running=True;return self
    def stop(self):
        self.restart();self.pause();return self
    def restart(self):
        if self._killed:raise RuntimeError('Killed Tween cannot be restarted')
        self._generation+=1
        self._stage=0;self._elapsed=0;self._cycles=0;self._completed=False;self._running=True
        for stage in self._stages:
            for task in stage:task.reset()
        return self
    def kill(self):
        self._generation+=1
        self._killed=True;self._running=False;self._stages.clear();self.destroy()
    def can_process(self):
        owner=self._tween_owner
        return super().can_process() and (owner is None or owner.game is not self.game or owner.can_process())
    def _advance(self,dt):
        if self._tween_owner is not None and self._tween_owner.game is not self.game:self.kill();return
        if not self.running or not self._stages or not self.speed_scale:return
        remaining=dt*self.speed_scale;generation=self._generation
        if self._loops==0 and sum(max(task.length for task in stage) for stage in self._stages)==0:
            raise ValueError('An infinite Tween must consume some time')
        while self.running:
            stage=tuple(self._stages[self._stage]);length=max(task.length for task in stage)
            consumed=min(remaining,max(0,length-self._elapsed));self._elapsed+=consumed;remaining-=consumed
            for task in stage:
                task.apply(self._elapsed)
                if not self.running or generation!=self._generation:return
            if self._elapsed+1e-10<length:return
            index=self._stage;self._stage+=1;self._elapsed=0
            self.step_finished.emit(index)
            if not self.running or generation!=self._generation:return
            if self._stage>=len(self._stages):
                self._cycles+=1
                if self._loops and self._cycles>=self._loops:
                    self._completed=True;self._running=False
                    self.finished.emit()
                    if self.completed and self.auto_remove:self.destroy()
                    return
                self.loop_finished.emit(self._cycles)
                if not self.running or generation!=self._generation:return
                self._stage=0
                for group in self._stages:
                    for task in group:task.reset()
            if remaining<=1e-10 and max(task.length for task in self._stages[self._stage])>0:return

    def on_removed(self):
        self._running=False;self._killed=True;self._stages.clear()
