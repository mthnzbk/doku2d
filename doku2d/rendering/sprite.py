from pathlib import Path
from sfml.graphics import Sprite as SFMLSprite, Texture, Rect, RenderStates
from sfml.system import Vector2
from ..core import Entity, Signal


class Sprite(Entity):
    frame_changed = Signal()
    texture_changed = Signal()

    def __init__(self, texture=None, *, name=None, resources=None):
        super().__init__(name)
        self._resources=resources
        self._texture_path=None
        self._texture = None
        self._sprite = None
        self._offset = Vector2(0, 0)
        self._centered = True
        self._flip_h = False
        self._flip_v = False
        self._hframes = 1
        self._vframes = 1
        self._frame = 0
        self._region = False
        self._region_rect = [0, 0, 0, 0]
        if texture is not None:
            self.texture = texture

    @property
    def texture(self):
        return self._texture

    @texture.setter
    def texture(self, value):
        if isinstance(value,(str,Path)):
            self._texture_path=value
            resources=self._resources or (self.game.resources if self.game else None)
            value=resources.get_texture(value) if resources else None
        else:self._texture_path=None
        if value is not None and not isinstance(value, Texture):
            raise TypeError("texture must be a Texture, file path or None")
        self._texture = value
        self._sprite = SFMLSprite(value) if value is not None else None
        self.texture_changed.emit()

    def _bind_resources(self,resources):
        self._resources=resources
        if self._texture_path is not None:self._load_texture()

    def _load_texture(self):
        path=self._texture_path
        if path is not None:
            self.texture=self._resources.get_texture(path) if self._resources else Texture.from_file(str(path))
            self._texture_path=path

    @property
    def offset(self):
        return Vector2(*self._offset)

    @offset.setter
    def offset(self, value):
        self._offset = self._vector(value)

    @property
    def centered(self):
        return self._centered

    @centered.setter
    def centered(self, value):
        self._centered = bool(value)

    @property
    def flip_h(self):
        return self._flip_h

    @flip_h.setter
    def flip_h(self, value):
        self._flip_h = bool(value)

    @property
    def flip_v(self):
        return self._flip_v

    @flip_v.setter
    def flip_v(self, value):
        self._flip_v = bool(value)

    @property
    def hframes(self):
        return self._hframes

    @hframes.setter
    def hframes(self, value):
        if int(value) != value or value < 1:
            raise ValueError("hframes must be a positive integer")
        self._hframes = int(value)
        self.frame = min(self.frame, self.hframes * self.vframes - 1)

    @property
    def vframes(self):
        return self._vframes

    @vframes.setter
    def vframes(self, value):
        if int(value) != value or value < 1:
            raise ValueError("vframes must be a positive integer")
        self._vframes = int(value)
        self.frame = min(self.frame, self.hframes * self.vframes - 1)

    @property
    def frame(self):
        return self._frame

    @frame.setter
    def frame(self, value):
        if int(value) != value or not 0 <= value < self.hframes * self.vframes:
            raise ValueError("Frame is outside the sprite sheet")
        if self._frame != int(value):
            self._frame = int(value)
            self.frame_changed.emit()

    @property
    def frame_coords(self):
        return Vector2(self.frame % self.hframes, self.frame // self.hframes)

    @frame_coords.setter
    def frame_coords(self, value):
        x, y = value
        if int(x) != x or int(y) != y or not (0 <= x < self.hframes and 0 <= y < self.vframes):
            raise ValueError("Frame coordinates are outside the sprite sheet")
        self.frame = y * self.hframes + x

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, value):
        self._region = bool(value)

    @property
    def region_rect(self):
        return list(self._region_rect)

    @region_rect.setter
    def region_rect(self, value):
        x, y, width, height = value
        if width < 0 or height < 0:
            raise ValueError("Region dimensions cannot be negative")
        self._region_rect = [x, y, width, height]

    def render(self, target, states):
        if self._sprite is None and self._texture_path is not None:self._load_texture()
        if self._sprite is None:
            return
        if self.region:
            x, y, width, height = self.region_rect
        else:
            width = self.texture.size.x // self.hframes
            height = self.texture.size.y // self.vframes
            x, y = self.frame_coords.x * width, self.frame_coords.y * height
        self._sprite.texture_rectangle = Rect((int(x), int(y)), (int(width), int(height)))
        self._sprite.origin = (width / 2, height / 2) if self.centered else (0, 0)
        self._sprite.scale = (-1 if self.flip_h else 1, -1 if self.flip_v else 1)
        self._sprite.position = self.offset
        target.draw(self._sprite, states)
