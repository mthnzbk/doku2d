from sfml.system import Vector2
from sfml.graphics import Color
from .entity import Entity


class Canvas:
    """Shared drawing settings, independent of object ownership or lifecycle."""
    def __init__(self, name="World", *, order=0, screen_space=False, parallax=(1, 1)):
        self.name = name
        self.order = order
        self.screen_space = screen_space
        self.parallax = parallax
        self._ambient=Color.WHITE
        self._light_mask=1
        self._material = None
        self.lighting=True

    @property
    def material(self):
        return self._material

    @material.setter
    def material(self, value):
        from ..rendering.shader import checked_material
        self._material = checked_material(value)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = str(value)

    @property
    def order(self):
        return self._order

    @order.setter
    def order(self, value):
        self._order = int(value)

    @property
    def screen_space(self):
        return self._screen_space

    @screen_space.setter
    def screen_space(self, value):
        self._screen_space = bool(value)

    @property
    def parallax(self):
        return Vector2(*self._parallax)

    @parallax.setter
    def parallax(self, value):
        self._parallax = Entity._vector(value)

    @property
    def ambient(self):return Color(self._ambient.r,self._ambient.g,self._ambient.b,self._ambient.a)

    @ambient.setter
    def ambient(self,value):
        self._ambient=Color(value.r,value.g,value.b,value.a) if isinstance(value,Color) else Color(*value)

    @property
    def light_mask(self):return self._light_mask

    @light_mask.setter
    def light_mask(self,value):
        if not isinstance(value,int) or not 0<=value<=0xffffffff:raise ValueError('Light mask must be a 32-bit mask')
        self._light_mask=value
