from typing import Any, Tuple

from sfml.system import Vector2

from ..core import Object, Signal, Node

class CollisionObject(Object):
    input_event = Signal()
    mouse_entered = Signal()
    mouse_exited = Signal()
    mouse_shape_entered = Signal()
    mouse_shape_exited = Signal()


    _disable_mode:Any #remove, make static, keep active
    _layer:int = 1 #1-32
    _mask:int = 1
    _priority:float = 1.0

    #input
    _pickable:bool = False

class CollisionShape2D(Node):
    _shape:str #Shape -> çember, kare, silindir,kapsül vs.
    _disabled:bool = False
    _one_way_collision:bool = False
    #one way
    _one_way_collision_margin:float = 1.0 #px
    _one_way_collision_direction:Vector2 = Vector2(0.0, 1.0)
    _debug_color:str = "blue"

class CollisionPolygon2D(Node):
    _build_mode:Any #Solids, segments
    _polygon:Tuple[Vector2]
    _disabled:bool = False
    _one_way_collision:bool = False
    _one_way_collision_margin: float = 1.0  # px
    _one_way_collision_direction: Vector2 = Vector2(0.0, 1.0)

class RayCast2D(Node):
    _enabled:bool = True
    _exlude_parent:bool = True
    _target_position:Vector2 = Vector2(0.0, 50.0)
    _collision_mask:int = 1 #1-32 bunlar büyük ihtimal >> gibi bir zıkkım 1-2-4-8
    _hit_from_inside:bool = False
    _collide_with_areas:bool = False
    _collide_with_bodies:bool = True