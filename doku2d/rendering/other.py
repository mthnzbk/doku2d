"""Named position markers and compatibility imports for visual composition."""
from ..core import Entity
from .compositing import CanvasGroup, AmbientLight, CanvasModulate, DayNightCycle


class Marker(Entity):
    """A named position/transform anchor; it does not draw anything."""


__all__=['CanvasGroup','AmbientLight','CanvasModulate','DayNightCycle','Marker']
