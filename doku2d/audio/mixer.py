"""Independent volume and mute controls for each game's audio buses."""
from math import isfinite
from types import MappingProxyType


class AudioBus:
    def __init__(self, mixer, name, volume, muted):
        self._mixer = mixer
        self._name = name
        self._volume = self._checked_volume(volume)
        self._muted = bool(muted)

    @staticmethod
    def _checked_volume(value):
        if not isfinite(value) or not 0 <= value <= 100:
            raise ValueError('Audio bus volume must be in [0, 100]')
        return float(value)

    @property
    def name(self):
        return self._name

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        value = self._checked_volume(value)
        if value != self._volume:
            self._volume = value
            self._mixer._refresh(self.name)

    @property
    def muted(self):
        return self._muted

    @muted.setter
    def muted(self, value):
        value = bool(value)
        if value != self._muted:
            self._muted = value
            self._mixer._refresh(self.name)

    @property
    def _gain(self):
        return 0.0 if self.muted else self.volume / 100


class AudioMixer:
    """Master scales every bus. Music and SFX are available by default."""

    def __init__(self, game, *, preferences=None, save=None):
        self._game = game
        self._buses = {}
        self._preferences = dict(preferences) if isinstance(preferences, dict) else {}
        self._save_preferences = save
        for name in ('Master', 'Music', 'SFX'):
            self.add_bus(name)

    @property
    def buses(self):
        return MappingProxyType(self._buses)

    def __getitem__(self, name):
        return self._buses[name]

    def add_bus(self, name, *, volume=100, muted=False):
        if not isinstance(name, str) or not name or name != name.strip():
            raise ValueError('Name must be a nonempty audio bus name')
        if name in self._buses:
            raise ValueError(f'Audio bus already exists: {name}')
        saved = self._preferences.get(name)
        if isinstance(saved, dict):
            saved_volume, saved_mute = saved.get('volume'), saved.get('muted')
            if type(saved_volume) in (int, float) and 0 <= saved_volume <= 100:
                volume = saved_volume
            if isinstance(saved_mute, bool):
                muted = saved_mute
        bus = AudioBus(self, name, volume, muted)
        self._buses[name] = bus
        return bus

    def _gain(self, name):
        master = self['Master']._gain
        return master if name == 'Master' else master * self[name]._gain

    def _refresh(self, name):
        if self._save_preferences is not None:
            bus = self[name]
            self._preferences[name] = {'volume': bus.volume, 'muted': bus.muted}
            self._save_preferences(dict(self._preferences))
        for entity in self._game.objects:
            if getattr(entity, '_is_audio_player', False) and (name == 'Master' or entity.bus == name):
                entity._configure_all()
