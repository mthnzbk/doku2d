from dataclasses import dataclass
from pathlib import Path
from math import isfinite
from types import MappingProxyType
from sfml.graphics import Texture
from sfml.system import Vector2
from ..core.entity import Entity
from ..core.signal import Signal
from ..rendering.sprite import Sprite
from ..rendering.atlas import AtlasRegion


@dataclass(frozen=True)
class Animation:
    frames: tuple = (0,)
    fps: float = 8.0
    loop: bool = True


class AnimatedSprite(Entity):
    batchable = True
    cullable = True
    animation_changed = Signal()
    animation_finished = Signal()
    animation_looped = Signal()
    frame_changed = Signal()
    sprite_frames_changed = Signal()

    def __init__(self, texture=None, *, frame_size=None, name=None, resources=None):
        super().__init__(name)
        self._resources=resources;self._texture_path=None
        self._visual = Sprite(resources=resources)
        self._sheet_texture = None
        self._motion = None
        self._frame_size = None
        self._clips = {}
        self._animation = ""
        self._frame = 0
        self._speed_scale = 1.0
        self._playback_speed = 1.0
        self._playing = False
        self._finished = False
        self._time = 0.0
        if frame_size is not None:
            self.frame_size = frame_size
        if texture is not None:
            self.texture = texture

    @property
    def motion(self):return self._motion

    def follow_motion(self,body,**options):
        from .motion import MotionAnimation
        self._motion=MotionAnimation(self,body,**options) if body is not None else None
        return self._motion

    @staticmethod
    def _clip(frames, fps, loop):
        frames = tuple(frames)
        if not frames or any(not isinstance(frame, AtlasRegion) and (not isinstance(frame, int) or frame < 0)
                             for frame in frames):
            raise ValueError('Animation frames must be nonnegative indices or atlas regions')
        if not isfinite(fps) or fps <= 0:
            raise ValueError("Animation fps must be positive and finite")
        return Animation(frames,float(fps),bool(loop))

    def _grid(self, texture, frame_size):
        if texture is None or frame_size is None:
            return (1,1)
        width,height = frame_size
        if texture.size.x % width or texture.size.y % height:
            raise ValueError("The texture must contain whole sprite-sheet cells")
        return (int(texture.size.x/width),int(texture.size.y/height))

    def _validate_frames(self, clip, count):
        if self._sheet_texture is not None and any(isinstance(frame, int) and frame >= count for frame in clip.frames):
            raise ValueError("Animation frame is outside the sprite sheet")

    @property
    def texture(self):
        return self._visual.texture

    @texture.setter
    def texture(self, value):
        if isinstance(value,(str,Path)):
            self._texture_path=value
            resources=self._resources or (self.game.resources if self.game else None)
            value=resources.get_texture(value) if resources else None
        else:self._texture_path=None
        if value is not None and not isinstance(value,Texture):
            raise TypeError("texture must be an SFML Texture, path or None")
        columns,rows = self._grid(value,self._frame_size)
        if value is not None and any(isinstance(frame, int) and frame >= columns*rows
                                     for clip in self._clips.values() for frame in clip.frames):
            raise ValueError("The texture is too small for the existing animations")
        self._sheet_texture = value
        self._visual.texture = value
        self._visual.hframes,self._visual.vframes = columns,rows
        self._apply_frame()

    def _bind_resources(self,resources):
        self._resources=resources;self._visual._bind_resources(resources)
        if self._texture_path is not None:self._load_texture()

    def _load_texture(self):
        path=self._texture_path
        if path is not None:
            self.texture=self._resources.get_texture(path) if self._resources else Texture.from_file(str(path))
            self._texture_path=path

    @property
    def frame_size(self):
        return Vector2(*self._frame_size) if self._frame_size is not None else None

    @frame_size.setter
    def frame_size(self, value):
        width,height = value
        if not isfinite(width) or not isfinite(height) or width <= 0 or height <= 0 or int(width) != width or int(height) != height:
            raise ValueError("Frame size must contain positive integer dimensions")
        columns,rows = self._grid(self._sheet_texture,(width,height))
        for clip in self._clips.values():
            self._validate_frames(clip,columns*rows)
        self._frame_size = (int(width),int(height))
        self._visual.hframes,self._visual.vframes = columns,rows
        self._apply_frame()

    @property
    def sprite_frames(self):
        return MappingProxyType(self._clips)

    @sprite_frames.setter
    def sprite_frames(self, values):
        clips = {}
        for name,config in values.items():
            if isinstance(config,Animation):
                clip = self._clip(config.frames,config.fps,config.loop)
            else:
                clip = self._clip(config["frames"],config.get("fps",8),config.get("loop",True))
            self._validate_frames(clip,self._visual.hframes*self._visual.vframes)
            clips[name] = clip
        self._clips = clips
        self._animation = self._animation if self._animation in clips else next(iter(clips),"")
        self._frame = 0
        self._time = 0
        self._playing = False
        self._apply_frame()
        self.sprite_frames_changed.emit()

    def add_animation(self, name, frames, *, fps=8, loop=True):
        if not isinstance(name,str) or not name:
            raise ValueError("Animation names must be nonempty strings")
        clip = self._clip(frames,fps,loop)
        self._validate_frames(clip,self._visual.hframes*self._visual.vframes)
        self._clips[name] = clip
        if not self.animation:
            self._animation = name
        if self.animation == name:
            self._frame = min(self._frame,len(clip.frames)-1)
            self._apply_frame()
        self.sprite_frames_changed.emit()
        return self

    @property
    def animation(self):
        return self._animation

    @animation.setter
    def animation(self, name):
        if name not in self._clips:
            raise KeyError(f"Unknown animation: {name}")
        if name != self.animation:
            self._animation = name
            self._frame,self._time = 0,0
            self._apply_frame()
            self.animation_changed.emit()

    @property
    def frame(self):
        return self._frame

    @frame.setter
    def frame(self, value):
        clip = self._clips.get(self.animation)
        if not isinstance(value,int) or clip is None or not 0 <= value < len(clip.frames):
            raise ValueError("Frame is outside the current animation")
        if self._frame != value:
            self._frame = value
            self._apply_frame()
            self.frame_changed.emit()

    @property
    def speed_scale(self):
        return self._speed_scale

    @speed_scale.setter
    def speed_scale(self, value):
        if not isfinite(value):
            raise ValueError("speed_scale must be finite")
        self._speed_scale = float(value)

    @property
    def playing(self):
        return self._playing

    def is_playing(self):
        return self.playing

    def play(self, name=None, *, speed=1.0, from_end=False):
        name = name or self.animation
        if name not in self._clips:
            raise KeyError(f"Unknown animation: {name}")
        if not isfinite(speed):
            raise ValueError("Playback speed must be finite")
        self.animation = name
        if self._finished:
            self.frame = 0 if speed*self.speed_scale >= 0 else len(self._clips[name].frames)-1
            self._time = 0
        self._finished = False
        if from_end:
            self.frame = len(self._clips[name].frames)-1
            self._time = 0
        self._playback_speed = float(speed)
        self._playing = True

    def pause(self):
        self._playing = False

    def stop(self):
        self.pause()
        self._finished = False
        self._time = 0
        if self.animation:
            self.frame = 0

    def _apply_frame(self):
        clip = self._clips.get(self.animation)
        frame = clip.frames[self.frame] if clip is not None else None
        if isinstance(frame, AtlasRegion):
            if self._visual.atlas_region is not frame:
                self._visual.texture = frame
        else:
            if self._visual.atlas_region is not None:
                self._visual.texture = self._sheet_texture
            if frame is not None and self._sheet_texture is not None:
                self._visual.frame = frame

    def advance(self, dt):
        if self.motion is not None:self.motion.update()
        if not isfinite(dt) or dt < 0:
            raise ValueError("Delta time must be finite and nonnegative")
        speed = self.speed_scale*self._playback_speed
        if not self.playing or not speed:
            return
        name = self.animation
        clip = self._clips[name]
        self._time += dt*abs(speed)
        steps = int((self._time+1e-10)*clip.fps)
        self._time = max(0,self._time-steps/clip.fps)
        direction = 1 if speed > 0 else -1
        for _ in range(steps):
            if not self.playing or self.animation != name or self._clips.get(name) is not clip:
                break
            index = self.frame+direction
            if 0 <= index < len(clip.frames):
                self.frame = index
            elif clip.loop:
                self.frame = index%len(clip.frames)
                self.animation_looped.emit()
            else:
                self._playing = False
                self._finished = True
                self._time = 0
                self.animation_finished.emit()
                break

    def _advance(self, dt):
        self.advance(dt)

    def render(self, target, states):
        if self.texture is None and self._texture_path is not None:self._load_texture()
        self._visual.render(target,states)

    def _batch_sprite(self):
        return self._visual if type(self).render is AnimatedSprite.render else None

    @property
    def centered(self):
        return self._visual.centered

    @centered.setter
    def centered(self, value):
        self._visual.centered = value

    @property
    def offset(self):
        return self._visual.offset

    @offset.setter
    def offset(self, value):
        self._visual.offset = value

    @property
    def flip_h(self):
        return self._visual.flip_h

    @flip_h.setter
    def flip_h(self, value):
        self._visual.flip_h = value

    @property
    def flip_v(self):
        return self._visual.flip_v

    @flip_v.setter
    def flip_v(self, value):
        self._visual.flip_v = value


__all__ = ["AnimatedSprite","Animation"]
