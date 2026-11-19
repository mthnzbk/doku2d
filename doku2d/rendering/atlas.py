"""Named rectangles that share a single SFML texture."""
from collections.abc import Mapping
from dataclasses import dataclass
from math import ceil, sqrt
from pathlib import Path

from sfml.graphics import Color, Image, Texture
from sfml.system import Vector2


@dataclass(frozen=True)
class AtlasRegion:
    texture: Texture
    rect: tuple

    def __post_init__(self):
        x, y, w, h = self.rect
        if not isinstance(self.texture, Texture):
            raise TypeError('An atlas region requires an SFML Texture')
        tw, th = self.texture.size
        if (any(type(v) is not int for v in (x, y, w, h)) or x < 0 or y < 0 or w <= 0 or h <= 0
                or x+w > tw or y+h > th):
            raise ValueError('Atlas rectangle must be inside the texture and have positive integer dimensions')
        object.__setattr__(self, 'rect', (x, y, w, h))

    @property
    def size(self):
        return Vector2(*self.rect[2:])


class SpriteAtlas(Mapping):
    def __init__(self, texture, frames):
        if not isinstance(texture, Texture):
            raise TypeError('An atlas requires an SFML Texture')
        self._texture = texture
        self._frames = {}
        for name, rect in frames.items():
            if not isinstance(name, str) or not name:
                raise ValueError('Atlas frame names must be nonempty strings')
            self._frames[name] = AtlasRegion(texture, rect)

    @property
    def texture(self):
        return self._texture

    def __getitem__(self, name):
        return self._frames[name]

    def __iter__(self):
        return iter(self._frames)

    def __len__(self):
        return len(self._frames)

    @classmethod
    def from_file(cls, path, *, resources=None):
        """Load engine JSON or an untrimmed, unrotated Aseprite/TexturePacker export."""
        from ..core.resource import Resources

        resources = resources or Resources()
        path = resources.resolve(path)
        data = resources.get_json(path)
        image = data.get('image') or data.get('meta', {}).get('image')
        if not isinstance(image, str) or not image:
            raise ValueError('Atlas JSON needs an image path')
        frames = data['frames']
        entries = frames.items() if isinstance(frames, dict) else ((item['filename'], item) for item in frames)
        rects = {}
        for name, entry in entries:
            if name in rects:
                raise ValueError(f'Duplicate atlas frame: {name}')
            if isinstance(entry, dict):
                if entry.get('rotated') or entry.get('trimmed'):
                    raise ValueError(f'Export atlas frame {name!r} without rotation or trimming')
                frame = entry.get('frame', entry)
                entry = tuple(frame[key] for key in ('x', 'y', 'w', 'h'))
            rects[name] = entry
        texture_path = image if image.startswith('res://') else path.parent / image
        return cls(resources.get_texture(texture_path), rects)

    @classmethod
    def pack(cls, images, *, resources=None, max_size=2048, padding=1):
        """Pack a mapping of names to Images or PNG paths into one texture."""
        if type(max_size) is not int or max_size <= 0 or type(padding) is not int or padding < 0:
            raise ValueError('Atlas max_size must be positive and padding nonnegative')
        if not images:
            raise ValueError('Provide at least one image to pack')
        items = []
        for name, source in images.items():
            if not isinstance(source, Image):
                path = resources.resolve(source) if resources else Path(source)
                source = Image.from_file(str(path))
            w, h = map(int, source.size)
            items.append((name, source, w+2*padding, h+2*padding))
        if any(max(w, h) > max_size for _, _, w, h in items):
            raise ValueError('An image is larger than the atlas limit')
        order = sorted(items, key=lambda item: item[3], reverse=True)

        def place(width):
            x = y = row_height = used_width = 0
            slots = []
            for name, source, w, h in order:
                if x+w > width:
                    x, y, row_height = 0, y+row_height, 0
                slots.append((name, source, (x+padding, y+padding, w-2*padding, h-2*padding)))
                row_height = max(row_height, h)
                x += w
                used_width = max(used_width, x)
            return used_width, y+row_height, slots

        width = min(max_size, max(max(item[2] for item in items), ceil(sqrt(sum(w*h for _, _, w, h in items)))))
        used_width, height, slots = place(width)
        if height > max_size:
            used_width, height, slots = place(max_size)
        if height > max_size:
            raise ValueError('Images do not fit in one atlas at this max_size')
        combined = Image.create(used_width, height, Color.TRANSPARENT)
        for _, source, (x, y, _, _) in slots:
            combined.blit(source, (x, y))
        return cls(Texture.from_image(combined), {name: rect for name, _, rect in slots})


__all__ = ['AtlasRegion', 'SpriteAtlas']
