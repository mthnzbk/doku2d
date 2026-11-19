from pathlib import Path
from sfml.graphics import Sprite as SFMLSprite, Texture, Rect, RenderStates
from sfml.system import Vector2
from ..core import Entity, Signal
from .atlas import AtlasRegion


class Sprite(Entity):
    batchable = True
    cullable = True
    frame_changed = Signal()
    texture_changed = Signal()

    def __init__(self, texture=None, *, name=None, resources=None):
        super().__init__(name)
        self._resources=resources
        self._texture_path=None
        self._texture = None
        self._atlas_region = None
        self._sprite = None
        self._batch_geometry = None
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
        region = value if isinstance(value, AtlasRegion) else None
        if region is not None:
            value = region.texture
        if isinstance(value,(str,Path)):
            self._texture_path=value
            resources=self._resources or (self.game.resources if self.game else None)
            value=resources.get_texture(value) if resources else None
        else:self._texture_path=None
        if value is not None and not isinstance(value, Texture):
            raise TypeError("texture must be a Texture, AtlasRegion, file path or None")
        if value is not self._texture:
            self._sprite = SFMLSprite(value) if value is not None else None
        self._texture = value
        self._atlas_region = region
        self._batch_geometry = None
        self.texture_changed.emit()

    @property
    def atlas_region(self):
        return self._atlas_region

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

    def _frame_rect(self):
        if self.atlas_region is not None:
            return self.atlas_region.rect
        if self.region:
            return self._region_rect
        texture_size = self.texture.size
        width, height = texture_size.x // self.hframes, texture_size.y // self.vframes
        return self.frame % self.hframes * width, self.frame // self.hframes * height, width, height

    def _batch_sprite(self):
        return self if type(self).render is Sprite.render else None

    def _batch_quad(self):
        key = (self.texture, self._frame, self._hframes, self._vframes,
               self._atlas_region, tuple(self._region_rect) if self._region else None, self._centered,
               self._flip_h, self._flip_v, self._offset.x, self._offset.y)
        if self._batch_geometry is not None and key == self._batch_geometry[0]:
            return self._batch_geometry[1]
        x, y, width, height = self._frame_rect()
        ox, oy = (width/2, height/2) if self.centered else (0, 0)
        x, y, width, height = map(int, (x, y, width, height))
        sx, sy = (-1 if self.flip_h else 1), (-1 if self.flip_v else 1)
        left, top = self._offset.x - sx*ox, self._offset.y - sy*oy
        right, bottom = left + sx*width, top + sy*height
        quad = (((left, top), (right, top), (left, bottom), (right, bottom)),
                ((x, y), (x+width, y), (x, y+height), (x+width, y+height)))
        self._batch_geometry = (key, quad)
        return quad

    def render(self, target, states):
        if self._sprite is None and self._texture_path is not None:self._load_texture()
        if self._sprite is None:
            return
        x, y, width, height = self._frame_rect()
        self._sprite.texture_rectangle = Rect((int(x), int(y)), (int(width), int(height)))
        self._sprite.origin = (width / 2, height / 2) if self.centered else (0, 0)
        self._sprite.scale = (-1 if self.flip_h else 1, -1 if self.flip_v else 1)
        self._sprite.position = self.offset
        target.draw(self._sprite, states)
