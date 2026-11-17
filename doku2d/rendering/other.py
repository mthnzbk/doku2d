from typing import List, Any
from sfml.graphics import Color
from sfml.system import Vector2
from ..core import Node


class CanvasGroup(Node):
    #tweaks
    _fit_margin:int = 10 #px
    _clear_margin:int = 10
    _use_mipmaps:bool = False


class CanvasModulate(Node):
    _color:Color

    @property
    def color(self) -> Color: return self._color

    @color.setter
    def color(self, new_color:Color) -> None: self._color = new_color


class Marker(Node):
    _gizmo_extents:float = 10.0 #px # ne işe yarıyor amk?

    @property
    def gizmo_extents(self) -> float: return self._gizmo_extents

    @gizmo_extents.setter
    def gizmo_extents(self, value:float) -> None: self._gizmo_extents = value


class Line(Node):
    _points:List[Vector2]
    _closed: bool = False
    _width: float = 10.0 #px
    #_width_curve: Curve
    _color:str = 'black'

    #fill
    _gradient:str
    _texture:Any
    _texture_mode:Any #Tile, Strecth

    #capping
    _joint_mode:str #sharp, bevel, round
    _begin_cap_mode:str
    _end_cap_mode:str #box round

    #border
    _sharp_limit:float = 2.0
    _round_precision:int = 8
    _antialiased:bool = False