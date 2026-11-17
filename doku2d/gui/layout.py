from .control import Control


class Layout(Control):

    #böylece margincontainer gerekmez gibi.
    def set_margins(self, right, left, top, bottom): pass

class Grid(Layout):
    _columns:int = 1

class Box(Control):
    _alignment:str = "center" #begin, end

class HBox(Box): pass

class VBox(Box): pass

class Center(Layout): pass