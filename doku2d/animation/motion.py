"""Small opt-in animation policy, independent of a scene or state-machine tree."""
from math import atan2, floor, hypot, isfinite, tau
from sfml.system import Vector2
from ..core.signal import Signal


_DIRECTIONS = ('east', 'south_east', 'south', 'south_west', 'west', 'north_west', 'north', 'north_east')


class MotionAnimation:
    changed = Signal()

    def __init__(self, sprite, body, *, idle='idle', run='run', jump='jump', fall='fall',
                 run_speed=200, flip=True, directions=None):
        if not hasattr(body, 'velocity'):
            raise TypeError('Motion animation needs a body with velocity')
        if not isfinite(run_speed) or run_speed <= 0:
            raise ValueError('run_speed must be positive')
        if directions is not None and (type(directions) is not int or directions not in (4, 8)):
            raise ValueError('directions must be 4, 8, or None')
        self.sprite, self.body = sprite, body
        self.animations = {'idle': idle, 'run': run, 'jump': jump, 'fall': fall}
        self._directions = _DIRECTIONS[::8 // directions] if directions else ()
        self._facing = 'south' if self._directions else None
        required = ('idle', 'run', 'jump', 'fall') if getattr(body, 'motion_mode', None) == 'grounded' else ('idle', 'run')
        for state in required:
            base = self.animations[state]
            if base in sprite.sprite_frames:
                continue
            names = (f'{base}_{direction}' for direction in self._directions) if self._directions else (base,)
            for name in names:
                if name not in sprite.sprite_frames:
                    raise KeyError(f'Missing {state} animation: {name}')
        self.run_speed = float(run_speed)
        self.flip = bool(flip)
        self.enabled = True
        self._state = ''

    @property
    def state(self):
        return self._state

    @property
    def facing(self):
        """Last movement direction, or None when directional clips are disabled."""
        return self._facing

    def update(self):
        if not self.enabled:
            return
        vx, vy = self.body.velocity
        up = getattr(self.body, 'up_direction', Vector2(0, -1))
        horizontal = vx * -up.y + vy * up.x
        grounded = getattr(self.body, 'motion_mode', None) == 'grounded'
        magnitude = abs(horizontal) if grounded else hypot(vx, vy)
        if grounded and not self.body.is_on_floor():
            vertical = vx * up.x + vy * up.y
            state = 'jump' if vertical > 1 else 'fall'
        else:
            state = 'run' if hypot(vx, vy) > .5 else 'idle'

        name = self.animations[state]
        speed = max(.25, min(2, magnitude / self.run_speed)) if state == 'run' else 1
        if self._directions:
            if magnitude > .5:
                dx, dy = (-up.y * horizontal, up.x * horizontal) if grounded else (vx, vy)
                count = len(self._directions)
                self._facing = self._directions[floor(atan2(dy, dx) * count / tau + .5) % count]
            directional = f'{name}_{self.facing}'
            if directional in self.sprite.sprite_frames:
                name = directional
            self.sprite.play(name, speed=speed, preserve_phase=(state == self.state))
        else:
            if self.flip and abs(horizontal) > .5:
                self.sprite.flip_h = horizontal < 0
            self.sprite.play(name, speed=speed)
        if state != self.state:
            self._state = state
            self.changed.emit(state)
