from typing import Any

from sfml.system import Vector2

from ..core import Node

class Light(Node):
    _enabled = True
    _color:str = "white"
    _energy:float = 1.0
    _blend_mode:str = "add" # subtract, mix
    _shadow:bool = False

class PointLight(Light):
    _texture:Any
    _offset:Vector2
    _texture_scale:float = 1.0
    _height:int = 0 #px

class DirectionalLight(Light):
    _height:float = 0.0
    _max_distance:int = 10000 #px

class LightOccluder(Node):
    _occluder:Any #texture
    _sdf_collision:bool = True #bu ne amk