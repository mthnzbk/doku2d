"""Composable per-character effects for RichLabel."""
from colorsys import hsv_to_rgb
from dataclasses import dataclass, field
from math import sin, cos, tau, floor, isfinite
from sfml.system import Vector2


@dataclass
class CharacterEffect:
    index: int
    elapsed: float
    color: tuple
    offset: Vector2 = field(default_factory=lambda: Vector2(0,0))
    scale: float = 1.0
    visible: bool = True


def number(options, name, default):
    try:
        value = float(options.get(name,default))
        return value if isfinite(value) else default
    except (TypeError,ValueError):
        return default


def wave(character, options):
    amplitude = number(options,"amp",4)
    frequency = max(0,number(options,"freq",2))
    if frequency:
        character.offset += Vector2(0,sin(character.elapsed*tau*frequency-character.index*0.45)*amplitude)


def tornado(character, options):
    radius = number(options,"radius",3)
    phase = character.elapsed*tau*number(options,"freq",1)+character.index*0.4
    character.offset += Vector2(cos(phase)*radius,sin(phase)*radius)


def shake(character, options):
    tick = floor(character.elapsed*max(0,number(options,"rate",20)))
    amplitude = number(options,"level",2)
    seed = character.index*123.45+tick*73.31
    character.offset += Vector2(sin(seed*19.17)*amplitude,sin(seed*31.79)*amplitude)


def rainbow(character, options):
    hue = (character.elapsed*number(options,"speed",0.2)+character.index*0.045*number(options,"freq",1))%1
    saturation = max(0,min(1,number(options,"sat",0.65)))
    brightness = max(0,min(1,number(options,"val",1)))
    rgb = tuple(round(channel*255) for channel in hsv_to_rgb(hue,saturation,brightness))
    alpha = character.color[3] if len(character.color)==4 else 255
    character.color = (*rgb,alpha)


def pulse(character, options):
    phase = (sin(character.elapsed*tau*number(options,"freq",1))+1)/2
    alpha = character.color[3] if len(character.color)==4 else 255
    character.color = (*character.color[:3],round(alpha*(0.35+phase*0.65)))


DEFAULT_EFFECTS = {"wave":wave,"tornado":tornado,"shake":shake,
                   "rainbow":rainbow,"pulse":pulse}
