"""The supported public Doku2D API."""
from sfml.graphics import Color
from sfml.system import Vector2
from .config import ProjectConfig
__version__="1.0.0rc1"
from .gui import *
from .rendering import *
from .core import *
from .physics import *
from .audio import *
from .animation import *
from .gui import __all__ as _gui
from .rendering import __all__ as _rendering
from .core import __all__ as _core
from .physics import __all__ as _physics
from .audio import __all__ as _audio
from .animation import __all__ as _animation
__all__=list(dict.fromkeys(['Color','Vector2','ProjectConfig']+_core+_gui+_rendering+_physics+_audio+_animation))
