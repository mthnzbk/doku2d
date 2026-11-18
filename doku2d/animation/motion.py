"""Small opt-in animation policy, independent of a scene or state-machine tree."""
from math import hypot, isfinite
from sfml.system import Vector2
from ..core.signal import Signal


class MotionAnimation:
    changed=Signal()
    def __init__(self,sprite,body,*,idle='idle',run='run',jump='jump',fall='fall',run_speed=200,flip=True):
        if not hasattr(body,'velocity'):raise TypeError('Motion animation needs a body with velocity')
        if not isfinite(run_speed) or run_speed<=0:raise ValueError('run_speed must be positive')
        self.sprite,self.body=sprite,body
        self.animations={'idle':idle,'run':run,'jump':jump,'fall':fall}
        required=('idle','run','jump','fall') if getattr(body,'motion_mode',None)=='grounded' else ('idle','run')
        for state in required:
            if self.animations[state] not in sprite.sprite_frames:raise KeyError(f'Missing {state} animation: {self.animations[state]}')
        self.run_speed=float(run_speed)
        self.flip=bool(flip)
        self.enabled=True
        self._state=''
    @property
    def state(self):return self._state
    def update(self):
        if not self.enabled:return
        velocity=self.body.velocity
        up=getattr(self.body,'up_direction',Vector2(0,-1))
        horizontal=velocity.x*(-up.y)+velocity.y*up.x
        vertical=velocity.x*up.x+velocity.y*up.y
        if getattr(self.body,'motion_mode',None)=='grounded' and not self.body.is_on_floor():
            state='jump' if vertical>1 else 'fall'
        else:state='run' if hypot(*velocity)>.5 else 'idle'
        if self.flip and abs(horizontal)>.5:self.sprite.flip_h=horizontal<0
        name=self.animations[state]
        magnitude=abs(horizontal) if getattr(self.body,'motion_mode',None)=='grounded' else hypot(*velocity)
        speed=max(.25,min(2,magnitude/self.run_speed)) if state=='run' else 1
        self.sprite.play(name,speed=speed)
        if state!=self.state:
            self._state=state
            self.changed.emit(state)
