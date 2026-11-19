"""Shared drawing primitives and an overridable, lazily loaded GUI theme."""
from dataclasses import dataclass, field, fields, replace
from contextlib import contextmanager
from math import cos, sin, pi
from pathlib import Path
import tomllib
from sfml.graphics import Color, Font, RectangleShape, CircleShape, ConvexShape, Text, Sprite, Rect


def color(value):
    return value if isinstance(value, Color) else Color(*value)


@dataclass
class Theme:
    font: object = None
    resources: object = field(default=None,repr=False,compare=False,kw_only=True)
    font_size: int = 16
    background: tuple = (19, 25, 37)
    surface: tuple = (29, 38, 53)
    hover: tuple = (40, 54, 72)
    active: tuple = (48, 103, 110)
    accent: tuple = (100, 224, 199)
    text: tuple = (231, 239, 247)
    muted: tuple = (145, 163, 184)
    border: tuple = (51, 65, 84)
    disabled: tuple = (62, 71, 84)
    selection: tuple = (43, 99, 119)
    padding: int = 12
    radius: int = 8

    @classmethod
    def load(cls, path, *, resources=None, base=None):
        """Read a TOML theme. Font paths are relative to its file or use res://."""
        path = resources.resolve(path) if resources is not None else Path(path).resolve()
        with path.open("rb") as stream:
            values = tomllib.load(stream)
        values = values.get("theme", values)
        known = {item.name for item in fields(cls)} - {"resources"}
        unknown = values.keys() - known
        if unknown:
            raise ValueError(f"Unknown theme fields: {', '.join(sorted(unknown))}")
        for name, value in values.items():
            if name == "font":
                if not isinstance(value, str) or not value:
                    raise ValueError("Theme font must be a path")
                values[name] = value if value.startswith("res://") else path.parent / value
            elif name in {"font_size", "padding", "radius"}:
                minimum = 1 if name == "font_size" else 0
                if type(value) is not int or value < minimum:
                    raise ValueError(f"Theme {name} must be an integer >= {minimum}")
            else:
                if not isinstance(value, list) or len(value) not in (3, 4) or any(
                    type(channel) is not int or not 0 <= channel <= 255 for channel in value
                ):
                    raise ValueError(f"Theme {name} must be an RGB or RGBA color")
                values[name] = tuple(value)
        theme = base if base is not None else cls()
        return replace(theme, resources=resources or theme.resources, **values)

    def variant(self, **overrides):
        """Copy this theme for a control or a layout, overriding selected fields."""
        return replace(self, **overrides)

    def get_font(self):
        if isinstance(self.font, (str, Path)):
            return self.resources.get_font(self.font) if self.resources else self._local_font(self.font)
        if self.font is None:
            candidates = (str(Path(__file__).parents[1]/'assets/fonts/NotoSans.ttf'),
                          "C:/Windows/Fonts/segoeui.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                          "/System/Library/Fonts/Supplemental/Arial.ttf")
            path = next((path for path in candidates if Path(path).is_file()), None)
            if path is None:
                raise RuntimeError("Set Theme.font to an SFML Font before drawing text")
            self.font = self.resources.get_font(path) if self.resources else Font.from_file(path)
        return self.font

    def _local_font(self, path):
        if getattr(self, "_font_path", None) != path:
            self._font_cache = Font.from_file(str(path))
            self._font_path = path
        return self._font_cache


def box(target, states, rect, fill, border=None, thickness=1, *, radius=0):
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return
    radius = max(0, min(radius, width/2, height/2))
    if radius:
        points = []
        for cx, cy, start in ((width-radius,radius,-pi/2), (width-radius,height-radius,0),
                              (radius,height-radius,pi/2), (radius,radius,pi)):
            for index in range(9):
                angle = start+index*pi/16
                points.append((cx+cos(angle)*radius,cy+sin(angle)*radius))
        shape = ConvexShape(len(points))
        for index, point in enumerate(points):
            shape.set_point(index,point)
    else:
        shape = RectangleShape((width, height))
    shape.position = (round(x), round(y))
    shape.fill_color = color(fill)
    if border is not None:
        shape.outline_color = color(border)
        shape.outline_thickness = -thickness
    target.draw(shape, states)


def disk(target, states, center, radius, fill):
    shape = CircleShape(max(0, radius), 40)
    x, y = center
    shape.position = (x-radius, y-radius)
    shape.fill_color = color(fill)
    target.draw(shape, states)


def text_object(control, value, size=None):
    return Text(control.font or control.theme.get_font(), control.localize(value),
                size or control.font_size)


def measure(control, value):
    text = text_object(control, value)
    return text.find_character_pos(len(str(value))).x


def label(target, states, control, value, rect=None, *, align="left", valign="center", tint=None):
    x, y, width, height = rect or (0, 0, control.size.x, control.size.y)
    text = text_object(control, value)
    bounds = text.local_bounds
    offset_x = {"left": 0, "center": (width-bounds.size.x)/2,
                "right": width-bounds.size.x}.get(align, 0)
    offset_y = {"top": 0, "center": (height-bounds.size.y)/2,
                "bottom": height-bounds.size.y}.get(valign, 0)
    text.position = (round(x+offset_x-bounds.position.x), round(y+offset_y-bounds.position.y))
    text.fill_color = color(tint or control.theme.text)
    target.draw(text, states)


def texture(target, states, image, rect, region=None):
    if image is None:
        return
    from ..rendering.atlas import AtlasRegion
    if isinstance(image, AtlasRegion):
        ax, ay, aw, ah = image.rect
        if region is None:
            region = image.rect
        else:
            x, y, width, height = region
            if x < 0 or y < 0 or x+width > aw+1e-6 or y+height > ah+1e-6:
                raise ValueError('UI crop must be inside its atlas region')
            region = (ax+x, ay+y, width, height)
        image = image.texture
    sprite = Sprite(image)
    if region is not None:
        x, y, width, height = region
        sprite.texture_rectangle = Rect((int(x), int(y)), (int(width), int(height)))
    bounds = sprite.local_bounds.size
    if bounds.x and bounds.y:
        sprite.position = rect[:2]
        sprite.scale = (rect[2]/bounds.x, rect[3]/bounds.y)
        target.draw(sprite, states)


def mix(first, second, amount):
    amount = max(0, min(1, amount))
    return tuple(round(a+(b-a)*amount) for a,b in zip(first,second))


@contextmanager
def clipped(target, states, rect):
    """Intersect a local rectangle with the active view's scissor."""
    original = target.view
    view = target.view
    x,y,width,height = rect
    corners = [view.transform.transform_point(states.transform.transform_point(point))
               for point in ((x,y),(x+width,y),(x,y+height),(x+width,y+height))]
    current = view.scissor
    left = max(current.position.x, 0, min((p.x+1)/2 for p in corners))
    top = max(current.position.y, 0, min((1-p.y)/2 for p in corners))
    right = min(current.position.x+current.size.x, 1, max((p.x+1)/2 for p in corners))
    bottom = min(current.position.y+current.size.y, 1, max((1-p.y)/2 for p in corners))
    visible = width > 0 and height > 0 and right > left and bottom > top
    try:
        if visible:
            view.scissor = Rect((left,top),(right-left,bottom-top))
            target.view = view
        yield visible
    finally:
        target.view = original
