"""Independent volume and mute controls for each game's audio buses."""
from math import isfinite
from dataclasses import dataclass
from types import MappingProxyType


@dataclass
class _Ducking:
    amount: float
    attack: float
    release: float
    level: float = 0.0


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
        self._ducking = {}
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
        master = self['Master']._gain * self.duck_gain('Master')
        return master if name == 'Master' else master * self[name]._gain * self.duck_gain(name)

    def duck(self, source, target, *, amount=55, attack=.18, release=.45):
        """Reduce target volume by a percentage while source is playing."""
        self[source], self[target]
        if source == target or not all(isfinite(value) and value >= 0 for value in (amount, attack, release)) or amount > 100:
            raise ValueError('Ducking needs two buses, a percentage from 0 to 100, and nonnegative times')
        previous = self._ducking.get((source, target))
        self._ducking[source, target] = _Ducking(amount/100, attack, release,
                                                previous.level if previous is not None else 0.0)

    def remove_ducking(self, source, target):
        self._ducking.pop((source, target), None)

    def duck_gain(self, name):
        """Current ducking multiplier for a bus, independently of its volume."""
        return 1-max((rule.level for (_, target), rule in self._ducking.items() if target == name), default=0)

    def _update_ducking(self, dt):
        if not self._ducking:
            return
        sources = {entity.bus for entity in self._game.objects if getattr(entity, '_is_audio_player', False)
                   and entity.playing and entity.can_process() and not entity.stream_paused
                   and entity.volume > 0 and self[entity.bus]._gain > 0}
        for (source, _), rule in self._ducking.items():
            goal, duration = (rule.amount, rule.attack) if source in sources else (0, rule.release)
            delta = rule.amount*dt/duration if duration and rule.amount else abs(goal-rule.level)
            rule.level = max(rule.level-delta, min(rule.level+delta, goal))

    def _refresh(self, name):
        if self._save_preferences is not None:
            bus = self[name]
            self._preferences[name] = {'volume': bus.volume, 'muted': bus.muted}
            self._save_preferences(dict(self._preferences))
        for entity in self._game.objects:
            if getattr(entity, '_is_audio_player', False) and (name == 'Master' or entity.bus == name):
                entity._configure_all()
