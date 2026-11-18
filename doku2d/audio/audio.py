"""Game-local audio playback and explicit 2D distance/pan mixing."""
from pathlib import Path
from math import isfinite, hypot, cos, sin, radians, log10
from sfml.audio import Sound, SoundBuffer, Music, Status
from sfml.system import Vector2, seconds
from ..core import Entity, Signal


class AudioPlayer(Entity):
    finished = Signal()
    _is_audio_player = True

    def __init__(self, audio=None, *, name=None, autoplay=False, loop=False, stream=False,
                 volume=100, pitch_scale=1, max_polyphony=1, bus='SFX'):
        super().__init__(name)
        self._audio = None
        self._buffer = None
        self._voices = []
        self._volume = 100.0
        self._pitch_scale = 1.0
        self._stream_paused = False
        self._max_polyphony = 1
        self._loop = bool(loop)
        self._autoplay = bool(autoplay)
        self._stream = bool(stream)
        self.bus = bus
        self.audio = audio
        self.volume = volume
        self.pitch_scale = pitch_scale
        self.max_polyphony = max_polyphony

    @property
    def audio(self): return self._audio
    @audio.setter
    def audio(self,value):
        if value is not None and not isinstance(value,(str,Path,SoundBuffer)):
            raise TypeError('audio must be a path, SoundBuffer or None')
        self.stop()
        self._audio = value
        self._buffer = value if isinstance(value,SoundBuffer) else None
    @property
    def volume(self): return self._volume
    @volume.setter
    def volume(self,value):
        if not isfinite(value) or not 0 <= value <= 100: raise ValueError('Volume must be in [0,100]')
        self._volume = float(value)
        self._configure_all()
    @property
    def volume_db(self): return 20*log10(self.volume/100) if self.volume else float('-inf')
    @volume_db.setter
    def volume_db(self,value):
        if value == float('-inf'): self.volume = 0
        elif not isfinite(value) or value > 0: raise ValueError('volume_db must be at most 0 dB')
        else: self.volume = 100*10**(value/20)
    @property
    def pitch_scale(self): return self._pitch_scale
    @pitch_scale.setter
    def pitch_scale(self,value):
        if not isfinite(value) or value <= 0: raise ValueError('Pitch must be positive and finite')
        self._pitch_scale = float(value)
        self._configure_all()
    @property
    def loop(self): return self._loop
    @loop.setter
    def loop(self,value):
        self._loop = bool(value)
        self._configure_all()
    @property
    def autoplay(self): return self._autoplay
    @autoplay.setter
    def autoplay(self,value): self._autoplay = bool(value)
    @property
    def stream(self): return self._stream
    @stream.setter
    def stream(self,value): self._stream = bool(value)
    @property
    def max_polyphony(self): return self._max_polyphony
    @max_polyphony.setter
    def max_polyphony(self,value):
        if not isinstance(value,int) or value < 1: raise ValueError('Polyphony must be a positive integer')
        self._max_polyphony = value
        while len(self._voices) > value: self._voices.pop(0).stop()
    @property
    def playing(self): return any(voice.status != Status.STOPPED for voice in self._voices)
    @playing.setter
    def playing(self,value):
        if value and not self.playing: self.play()
        elif not value: self.stop()
    @property
    def stream_paused(self): return self._stream_paused
    @stream_paused.setter
    def stream_paused(self,value):
        self._stream_paused = bool(value)
        self._audio_update(suspended=self.game is not None and not self.can_process())
    @property
    def bus(self):
        return self._bus

    @bus.setter
    def bus(self, value):
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError('Name must be a nonempty audio bus name')
        if self.game is not None:
            self.game.audio[value]
        self._bus = value
        self._configure_all()

    @property
    def effective_volume(self):
        gain = self.game.audio._gain(self.bus) if self.game else 1.0
        return self.volume * gain
    @property
    def pan(self): return 0.0

    def _configure(self,voice):
        voice.spatialization_enabled = False
        voice.relative_to_listener = True
        voice.volume = self.effective_volume
        voice.pan = self.pan
        voice.pitch = self.pitch_scale
        voice.loop = self.loop

    def _configure_all(self):
        for voice in self._voices: self._configure(voice)

    def play(self, from_position=0.0):
        if self.audio is None: raise ValueError('Set audio before calling play()')
        if not isfinite(from_position) or from_position < 0: raise ValueError('Playback position cannot be negative')
        if self.stream and isinstance(self.audio,(str,Path)):
            path = self.game.resources.resolve(self.audio) if self.game else Path(self.audio)
            voice = Music.from_file(str(path))
        else:
            if self._buffer is None:
                self._buffer = (self.game.resources.get_sound(self.audio) if self.game
                                else SoundBuffer.from_file(str(self.audio)))
            voice = Sound(self._buffer)
        self._configure(voice)
        while len(self._voices) >= self.max_polyphony: self._voices.pop(0).stop()
        self._voices.append(voice)
        voice.play()
        voice.playing_offset = seconds(from_position)
        if self.stream_paused or self.game is not None and not self.can_process(): voice.pause()

    def stop(self):
        for voice in self._voices: voice.stop()
        self._voices.clear()

    def pause(self): self.stream_paused = True
    def resume(self): self.stream_paused = False

    def seek(self,position):
        if not isfinite(position) or position < 0: raise ValueError('Playback position cannot be negative')
        for voice in self._voices: voice.playing_offset = seconds(position)

    def get_playback_position(self):
        return self._voices[-1].playing_offset.seconds if self._voices else 0.0

    def _audio_update(self,*,suspended=False):
        had_voices = bool(self._voices)
        self._voices = [voice for voice in self._voices if voice.status != Status.STOPPED]
        for voice in self._voices:
            self._configure(voice)
            if suspended or self.stream_paused:
                if voice.status == Status.PLAYING: voice.pause()
            elif voice.status == Status.PAUSED: voice.play()
        if had_voices and not self._voices: self.finished.emit()

    def on_added(self):
        self.game.audio[self.bus]
        self._configure_all()
        if self.autoplay and not self.playing: self.play()
    def on_removed(self): self.stop()


class PositionalAudio(AudioPlayer):
    def __init__(self, audio=None, *, position=(0,0), max_distance=2000, attenuation=1,
                 panning_strength=1, panning_distance=400, **options):
        # These fields are needed before AudioPlayer's property setters run.
        self._max_distance = 2000.0
        self._attenuation = 1.0
        self._panning_strength = 1.0
        self._panning_distance = 400.0
        super().__init__(audio,**options)
        self.position = position
        self.max_distance = max_distance
        self.attenuation = attenuation
        self.panning_strength = panning_strength
        self.panning_distance = panning_distance

    @property
    def max_distance(self): return self._max_distance
    @max_distance.setter
    def max_distance(self,value):
        if not isfinite(value) or value <= 0: raise ValueError('max_distance must be positive')
        self._max_distance = float(value)
        self._configure_all()
    @property
    def attenuation(self): return self._attenuation
    @attenuation.setter
    def attenuation(self,value):
        if not isfinite(value) or value <= 0: raise ValueError('Attenuation must be positive')
        self._attenuation = float(value)
        self._configure_all()
    @property
    def panning_strength(self): return self._panning_strength
    @panning_strength.setter
    def panning_strength(self,value):
        if not isfinite(value) or value < 0: raise ValueError('Panning strength cannot be negative')
        self._panning_strength = float(value)
        self._configure_all()
    @property
    def panning_distance(self): return self._panning_distance
    @panning_distance.setter
    def panning_distance(self,value):
        if not isfinite(value) or value <= 0: raise ValueError('Panning distance must be positive')
        self._panning_distance = float(value)
        self._configure_all()

    def _relative(self):
        listener = self.game.audio_listener if self.game else None
        if listener:
            origin,angle = listener.position,radians(listener.rotation)
        elif self.game and self.game.camera and self.game.camera.enabled:
            origin,angle = self.game.camera.screen_center,radians(self.game.camera.view_rotation)
        else:
            origin,angle = (self.game.size/2 if self.game else Vector2(0,0)),0
        delta = self.position-origin
        return Vector2(delta.x*cos(angle)+delta.y*sin(angle),-delta.x*sin(angle)+delta.y*cos(angle))

    @property
    def effective_volume(self):
        delta = self._relative()
        gain = max(0,1-hypot(delta.x,delta.y)/self.max_distance)**self.attenuation
        return super().effective_volume * gain
    @property
    def pan(self):
        return max(-1,min(1,self._relative().x/self.panning_distance*self.panning_strength))


class AudioListener(Entity):
    def __init__(self,name=None,*,target=None):
        super().__init__(name)
        self._target = None
        self._offset = Vector2(0,0)
        self.target = target
    @property
    def target(self): return self._target
    @target.setter
    def target(self,value):
        if value is not None and not isinstance(value,Entity) and not callable(value):
            raise TypeError('Listener target must be an Entity, callable or None')
        self._target = value
    @property
    def offset(self): return Vector2(*self._offset)
    @offset.setter
    def offset(self,value): self._offset = self._vector(value)
    def _listener_update(self):
        if self.target is not None:
            point = self.target() if callable(self.target) else self.target.position
            self.position = self._vector(point)+self.offset
    @property
    def current(self): return self.game is not None and self.game.audio_listener is self
    @current.setter
    def current(self,value):
        if value: self.make_current()
        elif self.current: self.game.audio_listener = None
    def make_current(self):
        if self.game is None: raise RuntimeError('Add the listener to the Game first')
        self._listener_update()
        self.game.audio_listener = self
    def on_added(self):
        if self.game.audio_listener is None: self.make_current()
    def on_removed(self):
        if self.current: self.game.audio_listener = None


__all__ = ['AudioPlayer','PositionalAudio','AudioListener']
