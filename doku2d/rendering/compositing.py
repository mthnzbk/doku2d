"""Explicit visual composition and canvas-wide ambient color/time of day."""
from math import isfinite
from bisect import bisect_right
from sfml.graphics import Color,RenderTexture,Shader,Sprite,RenderStates
from ..core import Entity,Signal
from ..animation.values import interpolate
from .light import color

GROUP_SHADER=b'''
uniform sampler2D source;
uniform vec4 tint;
uniform float opacity;
void main(){
    vec4 pixel=texture2D(source,gl_TexCoord[0].xy);
    vec3 rgb=pixel.a>0.000001?pixel.rgb/pixel.a:vec3(0.0);
    gl_FragColor=vec4(rgb*tint.rgb,pixel.a*tint.a*opacity);
}
'''


class CanvasGroup(Entity):
    """A drawing group, not a scene tree. Members remain flat Game entities."""
    _is_canvas_group=True
    member_added=Signal()
    member_removed=Signal()
    def __init__(self,name=None,*,canvas=None,opacity=1,color=Color.WHITE):
        super().__init__(name)
        self._members=[];self._surface=None;self._shader=None
        self._opacity=1.;self._color=Color.WHITE
        self.canvas=canvas;self.opacity=opacity;self.color=color
    @property
    def members(self):return tuple(self._members)
    @property
    def opacity(self):return self._opacity
    @opacity.setter
    def opacity(self,value):
        if not isfinite(value) or not 0<=value<=1:raise ValueError('Group opacity must be in [0,1]')
        self._opacity=float(value)
    @property
    def color(self):return color(self._color)
    @color.setter
    def color(self,value):self._color=color(value)
    def add(self,source):
        from ..core.singleton import instantiate
        entity=instantiate(source)
        if not isinstance(entity,Entity):raise TypeError('Group expects an Entity, class or factory')
        if any(getattr(entity,flag,False) for flag in ('_is_canvas_group','_is_physics_body','_is_light','_is_occluder','_is_canvas_modulate','_is_audio_player')) or hasattr(entity,'_sync_collisions') or getattr(entity,'tile_map',None) is not None:
            raise TypeError('CanvasGroup accepts independent visual entities; keep physics, maps, lights and other groups outside it')
        if entity is self or entity._canvas_group is not None:raise ValueError('Object already belongs to a visual group')
        owner=entity.game or entity._pending_game
        if owner is not None and owner is not (self.game or self._pending_game):raise ValueError('Register the group in the same game before attaching a registered object')
        entity.canvas=None;entity._canvas_group=self;self._members.append(entity)
        try:
            if self.game and owner is None:self.game.add(entity,persistent=self.game._objects[self], scope=self.scope)
        except Exception:
            self._members.remove(entity);entity._canvas_group=None;raise
        self.member_added.emit(entity)
        return entity
    def _forget(self,entity):
        if entity in self._members:self._members.remove(entity)
        entity._canvas_group=None;self.member_removed.emit(entity)
    def remove(self,entity,*,free=False):
        if entity not in self._members:raise ValueError('Object is not a member')
        canvas=entity.canvas;self._forget(entity);entity.canvas=canvas
        if free:
            game=entity.game or entity._pending_game
            if game:game.remove(entity)
        return entity
    def on_added(self):
        for member in self.members:
            owner=member.game or member._pending_game
            if owner is not None and owner is not self.game:raise ValueError('Group member belongs to another game')
            if owner is None:self.game.add(member,persistent=self.game._objects[self], scope=self.scope)
    def on_removed(self):
        if not self.game.closed:
            for member in self.members:
                if member.game is self.game or member._pending_game is self.game:self.game.remove(member)
        self._surface=None;self._shader=None
    def render(self,target,states):
        if self.opacity<=0:return
        size=tuple(map(int,target.size))
        if self._surface is None or tuple(self._surface.size)!=size:self._surface=RenderTexture(*size)
        if self._shader is None:
            if not Shader.is_available():raise RuntimeError('CanvasGroup requires OpenGL shader support')
            self._shader=Shader.from_memory(fragment=GROUP_SHADER)
        surface=self._surface;surface.reset_GL_states();surface.clear(Color.TRANSPARENT)
        canvas=self.canvas or self.game.world
        members=sorted((obj for obj in self.members if obj.game is self.game and obj.visible and obj not in self.game._removing),key=lambda obj:obj.z_index)
        self.game._draw_canvas_objects(surface,members,canvas)
        surface.display()
        self._shader.set_uniform('source',surface.texture);self._shader.set_uniform('tint',self.color)
        self._shader.set_uniform('opacity',self.opacity)
        old_view=target.view;target.reset_GL_states();target.view=target.default_view
        try:target.draw(Sprite(surface.texture),RenderStates(shader=self._shader))
        finally:target.view=old_view


class AmbientLight(Entity):
    """Canvas-wide multiplicative ambient color; independent of point lights."""
    _is_canvas_modulate=True
    changed=Signal()
    def __init__(self,name=None,*,color=Color.WHITE,enabled=True):
        super().__init__(name);self._color=Color.WHITE;self._enabled=bool(enabled);self.color=color
    @property
    def color(self):return color(self._color)
    @color.setter
    def color(self,value):
        value=color(value)
        if value!=self._color:self._color=value;self.changed.emit()
    @property
    def enabled(self):return self._enabled
    @enabled.setter
    def enabled(self,value):
        if bool(value)!=self._enabled:self._enabled=bool(value);self.changed.emit()


CanvasModulate=AmbientLight


class DayNightCycle(AmbientLight):
    time_changed=Signal()
    day_changed=Signal()
    phase_changed=Signal()
    DEFAULT_COLORS=((0,(30,40,74)),(5,(35,47,82)),(7,(230,167,135)),
                    (10,(255,255,255)),(16,(255,255,255)),(18,(224,145,118)),
                    (21,(49,57,98)),(24,(30,40,74)))
    def __init__(self,name=None,*,day_length=180,time=8,colors=None,playing=True):
        super().__init__(name)
        self._day_length=180.;self._time=0.;self._day=0;self._speed_scale=1.
        self._colors=();self._playing=bool(playing)
        self.day_length=day_length;self.colors=self.DEFAULT_COLORS if colors is None else colors;self.time=time
    @property
    def day_length(self):return self._day_length
    @day_length.setter
    def day_length(self,value):
        if not isfinite(value) or value<=0:raise ValueError('Day length must be positive seconds')
        self._day_length=float(value)
    @property
    def time(self):return self._time
    @time.setter
    def time(self,value):
        if not isfinite(value):raise ValueError('Time must be finite hours')
        old=self.phase;previous=self._time;self._time=float(value)%24
        self._apply_time()
        if self._time!=previous:self.time_changed.emit(self.time)
        if self.phase!=old:self.phase_changed.emit(self.phase)
    @property
    def day(self):return self._day
    @day.setter
    def day(self,value):
        if not isinstance(value,int) or value<0:raise ValueError('Day must be a nonnegative integer')
        if self._day!=value:self._day=value;self.day_changed.emit(value)
    @property
    def phase(self):
        return 'dawn' if 5<=self.time<8 else 'day' if 8<=self.time<17 else 'dusk' if 17<=self.time<21 else 'night'
    @property
    def colors(self):return tuple((t,color(c)) for t,c in self._colors)
    @colors.setter
    def colors(self,values):
        keys=tuple(sorted(((float(t),color(c)) for t,c in values),key=lambda item:item[0]))
        if len(keys)<2 or keys[0][0]!=0 or keys[-1][0]!=24 or len({t for t,c in keys})!=len(keys) or any(not isfinite(t) or not 0<=t<=24 for t,c in keys):
            raise ValueError('Day colors need unique hours including 0 and 24')
        if keys[0][1]!=keys[-1][1]:raise ValueError('Midnight colors at 0 and 24 must match')
        self._colors=keys;self._apply_time()
    @property
    def speed_scale(self):return self._speed_scale
    @speed_scale.setter
    def speed_scale(self,value):
        if not isfinite(value) or value<0:raise ValueError('Day speed must be nonnegative')
        self._speed_scale=float(value)
    @property
    def playing(self):return self._playing
    def pause(self):self._playing=False
    def resume(self):self._playing=True
    def _apply_time(self):
        if not self._colors:return
        i=max(0,min(len(self._colors)-2,bisect_right([t for t,c in self._colors],self.time)-1))
        a,c1=self._colors[i];b,c2=self._colors[i+1]
        self.color=interpolate(c1,c2,(self.time-a)/(b-a))
    def _advance(self,dt):
        if not self.playing:return
        hours=self.time+dt*24/self.day_length*self.speed_scale
        if hours>=24:self.day+=int(hours//24)
        self.time=hours


__all__=['CanvasGroup','AmbientLight','CanvasModulate','DayNightCycle']
