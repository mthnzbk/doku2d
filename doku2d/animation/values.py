"""Shared interpolation and direct Python property bindings."""
from math import sin,cos,pi,isfinite
from numbers import Real
from copy import copy
from sfml.graphics import Color
from sfml.system import Vector2


def duration(value):
    if not isfinite(value) or value<0:raise ValueError('Duration must be finite and nonnegative')
    return float(value)


def easing(name,t):
    t=max(0,min(1,t))
    if callable(name):return name(t)
    if name=='linear':return t
    mode,_,kind=name.partition('_')
    if name.startswith('in_out_'):mode,kind='in_out',name[7:]
    if mode not in ('in','out','in_out'):raise ValueError(f'Unknown easing: {name}')
    def inward(x):
        if kind=='sine':return 1-cos(x*pi/2)
        if kind=='quad':return x*x
        if kind=='cubic':return x*x*x
        if kind=='quart':return x**4
        if kind=='quint':return x**5
        if kind=='expo':return 0 if x==0 else 2**(10*x-10)
        if kind=='back':return 2.70158*x**3-1.70158*x*x
        if kind=='bounce':
            y=1-x
            if y<1/2.75:r=7.5625*y*y
            elif y<2/2.75:y-=1.5/2.75;r=7.5625*y*y+.75
            elif y<2.5/2.75:y-=2.25/2.75;r=7.5625*y*y+.9375
            else:y-=2.625/2.75;r=7.5625*y*y+.984375
            return 1-r
        if kind=='elastic':return x if x in (0,1) else -(2**(10*x-10))*sin((10*x-10.75)*2*pi/3)
        raise ValueError(f'Unknown easing: {name}')
    if mode=='in':return inward(t)
    if mode=='out':return 1-inward(1-t)
    return inward(2*t)/2 if t<.5 else 1-inward(2-2*t)/2


def interpolate(a,b,t):
    if isinstance(a,bool) or isinstance(b,bool):return b if t>=1 else a
    if isinstance(a,Color) or isinstance(b,Color):
        def rgba(v):return (v.r,v.g,v.b,v.a) if isinstance(v,Color) else tuple(v)+(255,)*(4-len(v))
        return Color(*(max(0,min(255,round(x+(y-x)*t))) for x,y in zip(rgba(a),rgba(b))))
    if isinstance(a,Real) and isinstance(b,Real):return a+(b-a)*t
    if isinstance(a,Vector2) or isinstance(b,Vector2):return Vector2(*(x+(y-x)*t for x,y in zip(a,b)))
    if isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)):
        if len(a)!=len(b):raise ValueError('Interpolated sequences must have equal lengths')
        return type(a)(interpolate(x,y,t) for x,y in zip(a,b))
    return b if t>=1 else a


class Binding:
    def __init__(self,target,path):
        if not isinstance(path,str) or not path:raise ValueError('Property path must be nonempty')
        self.target=target;self.parts=path.replace(':','.').split('.')
        self.get()  # Catch typos before starting playback.
    @staticmethod
    def read(obj,key):
        if isinstance(obj,dict):return obj[key]
        if isinstance(obj,(tuple,list)):return obj[int(key)]
        return getattr(obj,key)
    def get(self):
        value=self.target
        for key in self.parts:value=self.read(value,key)
        return copy(value)
    def set(self,value):
        def replace(obj,keys,new):
            key=keys[0]
            child=replace(copy(self.read(obj,key)),keys[1:],new) if len(keys)>1 else new
            if isinstance(obj,dict):obj[key]=child
            elif isinstance(obj,list):obj[int(key)]=child
            elif isinstance(obj,tuple):
                values=list(obj);values[int(key)]=child;obj=tuple(values)
            elif isinstance(obj,Color) and key in ('r','g','b','a'):
                setattr(obj,key,max(0,min(255,round(child))))
            else:setattr(obj,key,child)
            return obj
        replace(self.target,self.parts,value)
