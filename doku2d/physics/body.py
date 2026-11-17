from typing import Any

from sfml.system import Vector2

from .collision import CollisionObject
from ..core import Node, Signal



class CharacterBody(Node):
    collision_object: CollisionObject = CollisionObject()

    _motion_mode:Any #Grounded, floating
    _up_direction:Vector2 = Vector2(0,-1)
    _slide_on_ceiling:bool = True

    #floor
    _stop_on_slope:bool = True
    _constant_speed:bool = False
    _block_on_wall:bool = True
    _max_angle:float = 45.0 #derece
    _snap_length:float = 1.0 #px

    #moving platform
    _on_leave:Any #add velocity, add upward velocity, do nothing
    _floor_layers:int = 1 #1-32
    _wall_layers:int = 1 #1-32

    #collision
    _safe_margin:float = 0.08 #px

class RigidBody(Node):
    body_entered = Signal()
    body_exited = Signal()
    body_shape_entered = Signal()
    body_shape_exited = Signal()
    sleeping_state_changed = Signal()

    collision_object: CollisionObject = CollisionObject()

    _mass:float = 1.0 #kg
    #_physics_material:Any
    _gravity_scale:float = 1.0

    #mass distribution
    _center_of_mass_mode:Any #auto, custom
    _inertia:float = 0.0 #kg *px2

    #deactivation
    _sleeping:bool = False
    _can_sleep:bool = True
    _lock_rotation:bool = False
    _freeze:bool = False
    _freeze_mode:Any # static, Kinematic

    #solver
    _custom_integrator:bool = False
    _continuous_cd:Any # disabled, cast ray, cast shape
    _contact_monitor:bool = False

    #linear
    _linear_velocity:Vector2 = Vector2(0.0,0.0) #px/sn
    _linear_damp_mode:Any # combine, replace
    _linear_damp:float = 0.0

    #angular
    _angular_velocity:float = 0.0  #derece/sn
    _angular_damp_mode:Any # combine, replace
    _angular_damp:float = 0.0

    #constant forces
    _force:Vector2 #kg*px/sn
    _torque:float = 0.0 #kg*px2/sn


class StaticBody(Node):
    #???

    collision_object: CollisionObject = CollisionObject()

class AnimatableBody(Node):
    _sync2_physics:bool = True

    collision_object:CollisionObject = CollisionObject()

class Area(Node):
    area_entered = Signal()
    area_exited = Signal()
    area_shape_entered = Signal()
    area_shape_exited = Signal()
    body_entered = Signal()
    body_exited = Signal()
    body_shape_entered = Signal()
    body_shape_exited = Signal()

    collision_object: CollisionObject = CollisionObject()

    _monitoring:bool = True
    _monitorable:bool = True
    _priority:int = 0

    #gravity
    _gravity_space_override: Any  # ""

    #linear damp
    _linear_damp_space_override:Any # ""

    #angular damp
    _angular_damp_space_override:Any # disabled, combine, combine-replace, replace, com-rep

    #audio bus
    _audio_bus_override:bool = False
    _audio_bus_name:Any #master,x ,y