from typing import Any

from ..core import Node, Signal


class Particles(Node):
    finished = Signal()

    _emitting:bool = True
    _amount:int = 10
    _amount_ratio:float = 1.0

    #sub emitter?

    _texture:Any
    #çok fazla


