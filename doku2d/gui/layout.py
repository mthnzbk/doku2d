from math import ceil
from .base import Control


class Layout(Control):
    """A layout references controls; all members remain independent Game objects."""
    def __init__(self,name=None):
        super().__init__(name)
        self._items = []
        self._managed = set()
        self._margins = (0,0,0,0)
        self._spacing = 10.0
        self.mouse_filter = "ignore"
        self.clip_contents = False

    @property
    def controls(self):
        return tuple(control for control,_ in self._items)

    @property
    def spacing(self):
        return self._spacing

    @spacing.setter
    def spacing(self,value):
        if value < 0: raise ValueError("spacing cannot be negative")
        self._spacing = float(value)

    def set_margins(self,right=0,left=0,top=0,bottom=0):
        if min(right,left,top,bottom) < 0: raise ValueError("Margins cannot be negative")
        self._margins = (left,top,right,bottom)

    def add(self,control,*,expand=False):
        if not isinstance(control,Control): raise TypeError("Layout members must be Controls")
        if control is self: raise ValueError("A layout cannot contain itself")
        ancestor = self
        while ancestor is not None:
            if ancestor is control: raise ValueError("Layout cycles are not allowed")
            ancestor = ancestor._layout
        if control._layout is not None: raise ValueError("Control already belongs to a layout")
        if control.game is not None and control.game is not self.game:
            raise ValueError("Control belongs to another game")
        self._items.append((control,bool(expand)))
        control._layout = self
        if self.game and control.game is None:
            self._managed.add(control)
            self.game.add(control, canvas=self.canvas, persistent=self.game._objects[self], scope=self.scope)
        self.arrange()
        return control

    def remove(self,control):
        if control not in self.controls: raise ValueError("Control is not in this layout")
        self._items = [(item,expand) for item,expand in self._items if item is not control]
        control._layout = None
        if control in self._managed:
            self._managed.remove(control)
            if control.game is self.game and self.game: self.game.remove(control)
        self.arrange()
        return control

    def on_added(self):
        super().on_added()
        for control,_ in self._items:
            if control.game is None and control._pending_game is None:
                self._managed.add(control)
                self.game.add(control, canvas=self.canvas, persistent=self.game._objects[self], scope=self.scope)
            elif control.game not in (None,self.game):
                raise ValueError("Layout member belongs to another game")
        self.arrange()

    def on_removed(self):
        for control in tuple(self._managed):
            if control.game is self.game or control._pending_game is self.game:
                if self.game.closed:
                    continue
                self.game.remove(control)
        self._managed.clear()
        super().on_removed()

    def content_rect(self):
        left,top,right,bottom = self._margins
        return (self.position.x+left,self.position.y+top,
                max(0,self.size.x-left-right),max(0,self.size.y-top-bottom))

    def arrange(self):
        super().arrange()


class Box(Layout):
    def __init__(self,name=None):
        super().__init__(name)
        self._alignment = "begin"
        self.vertical = False

    def arrange(self):
        super().arrange()
        visible = [(control,expand) for control,expand in self._items if control.visible]
        if not visible: return
        x,y,width,height = self.content_rect()
        available = height if self.vertical else width
        base = sum((control.min_size.y if self.vertical else control.min_size.x) if expand
                   else (control.size.y if self.vertical else control.size.x) for control,expand in visible)
        gaps = self.spacing*(len(visible)-1)
        expand_count = sum(expand for _,expand in visible)
        extra = max(0,available-base-gaps)
        offset = 0 if expand_count else {"begin":0,"center":extra/2,"end":extra}.get(self.alignment,0)
        cursor = (y if self.vertical else x)+offset
        for control,expand in visible:
            if self.vertical:
                extent = control.min_size.y+extra/expand_count if expand else control.size.y
                control.position = (x,cursor)
                control.size = (width,extent)
            else:
                extent = control.min_size.x+extra/expand_count if expand else control.size.x
                control.position = (cursor,y)
                control.size = (extent,height)
            cursor += extent+self.spacing
            if isinstance(control,Layout): control.arrange()


    @property
    def alignment(self):
        return self._alignment

    @alignment.setter
    def alignment(self, value):
        self._alignment = value


class HBox(Box):
    pass


class VBox(Box):
    def __init__(self,name=None):
        super().__init__(name)
        self.vertical = True


class Grid(Layout):
    def __init__(self,name=None):
        super().__init__(name)
        self._columns = 1

    @property
    def columns(self):
        return self._columns

    @columns.setter
    def columns(self,value):
        if int(value) != value or value < 1: raise ValueError("columns must be a positive integer")
        self._columns = int(value)

    def arrange(self):
        super().arrange()
        controls = [control for control in self.controls if control.visible]
        if not controls: return
        x,y,width,height = self.content_rect()
        rows = ceil(len(controls)/self.columns)
        cell_w = max(0,(width-self.spacing*(self.columns-1))/self.columns)
        cell_h = max(0,(height-self.spacing*(rows-1))/rows)
        for index,control in enumerate(controls):
            control.position = (x+index%self.columns*(cell_w+self.spacing),y+index//self.columns*(cell_h+self.spacing))
            control.size = (cell_w,cell_h)
            if isinstance(control,Layout): control.arrange()


class Center(Layout):
    def arrange(self):
        super().arrange()
        x,y,width,height = self.content_rect()
        for control in self.controls:
            control.position = (x+(width-control.size.x)/2,y+(height-control.size.y)/2)
            if isinstance(control,Layout): control.arrange()


__all__ = ["Layout","Grid","Box","HBox","VBox","Center"]
