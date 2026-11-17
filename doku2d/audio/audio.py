from typing import Any

from ..core import Node, Object, Signal

class AudioPlayer(Object):
    finished = Signal()

    _audio: Any  # stream
    _volume: float
    _pitch_scale: float = 1.0
    _playing: bool = False
    _autoplay: bool = False
    _stream_paused: bool = False
    _mix_target: Any # stereo surround center
    _max_polyphony: int = 1
    _bus: Any  # master,x ,x, x
    _playback_type: Any  # default stream sample

class PositionalAudio(Node):
    finished = Signal()

    _audio:Any #stream
    _volume:float
    _pitch_scale:float = 1.0
    _playing:bool = False
    _autoplay:bool = False
    _stream_paused:bool = False
    _max_distance:int = 2000 #px
    _attenuation:float = 1.0
    _max_polyphony:int = 1
    _panning_strength:float = 1.0
    _bus:Any # master,x ,x, x

    _area_mask:Any # 1-16
    _playback_type:Any # default stream sample

class AudioListener(Node):
    _current:bool = False

    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, value):
        self._current = value