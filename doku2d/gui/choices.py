from dataclasses import dataclass
from sfml.graphics import Color, RenderStates, Transform
from sfml.window import Event, Keyboard
from ..core import Signal, LocalizedText
from .base import Control
from .buttons import BaseButton
from .theme import box, color, label, texture, clipped


@dataclass
class Item:
    text: str | LocalizedText = ""
    icon: object = None
    selectable: bool = True
    disabled: bool = False


def as_item(value):
    return value if isinstance(value, Item) else Item(Control._caption(value))


def popup_bounds(owner, width, height):
    game = owner.game
    view = game.make_view(owner.canvas or game.world)
    world = owner.transform.transform_point((0, owner.size.y))
    ndc = view.transform.transform_point(world)
    x = max(0, min(game.size.x-width, (ndc.x+1)*game.size.x/2))
    y = (1-ndc.y)*game.size.y/2
    if y+height > game.size.y: y = max(0, y-height-owner.size.y)
    return (x, y, min(width,game.size.x), min(height,game.size.y))


def popup_states(owner, target):
    target.view = owner.game.make_view(owner.game._ui.canvas)
    transform = Transform()
    transform.translate(owner._popup_rect[:2])
    shader = owner.material._resolve(owner.game.resources) if owner.material is not None else None
    return RenderStates(transform=transform, shader=shader)


class ItemList(Control):
    empty_clicked = Signal()
    item_activated = Signal()
    item_clicked = Signal()
    item_selected = Signal()
    multi_selected = Signal()

    def __init__(self, name=None):
        super().__init__(name)
        self._items = []
        self._select_mode = "single"
        self._icon_mode = "left"
        self._icon_scale = 1.0
        self._fixed_icon_size = (0,0)
        self._selected_indices = set()
        self._current = -1
        self._scroll = 0
        self._last_click = (-1, -10.0)
        self._elapsed = 0.0
        self.row_height = 32
        self.focusable = True
        self.size = (220,160)

    @property
    def selected_indices(self):
        return tuple(sorted(self._selected_indices))

    @property
    def items(self):
        return self._items

    @items.setter
    def items(self, values):
        self._items = list(values)
        self._selected_indices.clear()
        self._current = -1
        self._scroll = 0

    def add_item(self, text, icon=None):
        self.items.append(Item(self._caption(text),icon))
        return len(self.items)-1

    def select(self, index, *, additive=False):
        if not 0 <= index < len(self.items): raise IndexError(index)
        item = as_item(self.items[index])
        if item.disabled or not item.selectable: return
        self._current = index
        if self.select_mode in ("multi", "toggle") and additive:
            if index in self._selected_indices: self._selected_indices.remove(index)
            else: self._selected_indices.add(index)
            self.multi_selected.emit(index,index in self._selected_indices)
        else:
            self._selected_indices = {index}
            self.item_selected.emit(index)
        self._scroll = max(0, min(self._scroll, index*self.row_height))
        if (index+1)*self.row_height-self._scroll > self.size.y:
            self._scroll = (index+1)*self.row_height-self.size.y

    def _pointer_down(self, point, button=0, pointer=0):
        from sfml.window import Keyboard
        index = int((point.y+self._scroll)//self.row_height)
        if index >= len(self.items):
            self.empty_clicked.emit(point,button)
            return False
        self.item_clicked.emit(index,point,button)
        if button == 0:
            additive = self.select_mode == "toggle" or Keyboard.is_key_pressed(Keyboard.L_CONTROL) or Keyboard.is_key_pressed(Keyboard.R_CONTROL)
            self.select(index,additive=additive)
            if self._last_click[0] == index and self._elapsed-self._last_click[1] < 0.4:
                item = as_item(self.items[index])
                if not item.disabled: self.item_activated.emit(index)
            self._last_click = (index,self._elapsed)
        return False

    def _wheel(self, delta):
        self._scroll = max(0,min(max(0,len(self.items)*self.row_height-self.size.y),self._scroll-delta*self.row_height))
        return True

    def _key(self, event):
        if event.type != Event.KEY_PRESSED: return False
        if event.code in (Keyboard.UP, Keyboard.DOWN):
            direction = -1 if event.code == Keyboard.UP else 1
            index = self._current+direction
            while 0 <= index < len(self.items):
                item = as_item(self.items[index])
                if item.selectable and not item.disabled:
                    self.select(index,additive=event.control)
                    break
                index += direction
        elif event.code == Keyboard.RETURN and self._current >= 0:
            self.item_activated.emit(self._current)
        else: return False
        return True

    def update(self, dt):
        self._elapsed += dt

    def render(self, target, states):
        box(target,states,(0,0,*self.size),self.theme.background,self.theme.border,radius=self.theme.radius)
        with clipped(target,states,(4,4,max(0,self.size.x-8),max(0,self.size.y-8))) as visible:
            if not visible:
                return
            for index in range(max(0,int(self._scroll//self.row_height)),len(self.items)):
                y = index*self.row_height-self._scroll
                if y >= self.size.y: break
                item = as_item(self.items[index])
                if index in self._selected_indices:
                    box(target,states,(6,y+3,self.size.x-12,self.row_height-6),self.theme.selection,radius=5)
                x = 12
                if item.icon is not None:
                    edge = (self.fixed_icon_size[0] or self.row_height-8)*self.icon_scale
                    texture(target,states,item.icon,(x,y+4,edge,self.row_height-8))
                    x += edge+8
                label(target,states,self,item.text,(x,y,self.size.x-x-8,self.row_height),
                      tint=self.theme.muted if item.disabled else self.theme.text)


    @property
    def select_mode(self):
        return self._select_mode

    @select_mode.setter
    def select_mode(self, value):
        self._select_mode = value

    @property
    def icon_mode(self):
        return self._icon_mode

    @icon_mode.setter
    def icon_mode(self, value):
        self._icon_mode = value

    @property
    def icon_scale(self):
        return self._icon_scale

    @icon_scale.setter
    def icon_scale(self, value):
        self._icon_scale = value

    @property
    def fixed_icon_size(self):
        return self._fixed_icon_size

    @fixed_icon_size.setter
    def fixed_icon_size(self, value):
        self._fixed_icon_size = value


class TabBar(Control):
    tab_button_pressed = Signal()
    tab_changed = Signal()
    tab_clicked = Signal()
    tab_close_pressed = Signal()
    tab_hovered = Signal()
    tab_selected = Signal()

    def __init__(self,name=None):
        super().__init__(name)
        self._tabs = []
        self._current_tab = -1
        self._tab_alignment = "left"
        self._tab_close_display = False
        self._max_tab_width = 0
        self._hover_tab = -1
        self.focusable = True
        self.size = (320,38)

    @property
    def current_tab(self):
        return self._current_tab

    @current_tab.setter
    def current_tab(self,value):
        value = int(value)
        if value < -1 or value >= len(self.tabs): raise IndexError(value)
        if self._current_tab != value:
            self._current_tab = value
            self.tab_changed.emit(value)
        self.tab_selected.emit(value)

    def add_tab(self,title):
        self.tabs.append(self._caption(title))
        if self.current_tab < 0: self.current_tab = 0
        return len(self.tabs)-1

    def _tab_geometry(self):
        if not self.tabs: return 0,0
        width = self.size.x/len(self.tabs)
        if self.max_tab_width: width = min(width,self.max_tab_width)
        left = {"left":0,"center":(self.size.x-width*len(self.tabs))/2,
                "right":self.size.x-width*len(self.tabs)}.get(self.tab_alignment,0)
        return left,width

    def _tab_at(self,point):
        left,width = self._tab_geometry()
        index = int((point.x-left)//width) if width else -1
        return index if 0 <= index < len(self.tabs) and 0 <= point.y < self.size.y else -1

    def _pointer_down(self,point,button=0,pointer=0):
        index = self._tab_at(point)
        if index >= 0 and button == 0:
            left,width = self._tab_geometry()
            if self.tab_close_display and point.x > left+(index+1)*width-24:
                self.tab_close_pressed.emit(index)
            else:
                self.tab_clicked.emit(index)
                self.current_tab = index
        return False

    def _pointer_move(self,point,pointer=0):
        index = self._tab_at(point)
        if index != self._hover_tab:
            self._hover_tab = index
            self.tab_hovered.emit(index)

    def _key(self,event):
        if event.type != Event.KEY_PRESSED or not self.tabs: return False
        if event.code not in (Keyboard.LEFT,Keyboard.RIGHT): return False
        self.current_tab = (self.current_tab+(-1 if event.code == Keyboard.LEFT else 1))%len(self.tabs)
        return True

    def render(self,target,states):
        left,width = self._tab_geometry()
        box(target,states,(0,0,*self.size),self.theme.background)
        for index,title in enumerate(self.tabs):
            x = left+index*width
            if index == self.current_tab:
                box(target,states,(x,0,width,self.size.y),self.theme.surface)
                box(target,states,(x,self.size.y-3,width,3),self.theme.accent)
            label(target,states,self,title,(x+8,0,width-16-(24 if self.tab_close_display else 0),self.size.y),align="center")
            if self.tab_close_display:
                label(target,states,self,"x",(x+width-24,0,20,self.size.y),align="center")


    @property
    def tab_alignment(self):
        return self._tab_alignment

    @tab_alignment.setter
    def tab_alignment(self, value):
        self._tab_alignment = value

    @property
    def tab_close_display(self):
        return self._tab_close_display

    @tab_close_display.setter
    def tab_close_display(self, value):
        self._tab_close_display = value

    @property
    def max_tab_width(self):
        return self._max_tab_width

    @max_tab_width.setter
    def max_tab_width(self, value):
        self._max_tab_width = value

    @property
    def tabs(self):
        return self._tabs

    @tabs.setter
    def tabs(self, value):
        self._tabs = value


class OptionButton(BaseButton):
    item_focused = Signal()
    item_selected = Signal()

    def __init__(self,name=None):
        super().__init__(name)
        self._items = []
        self._selected = -1
        self._search_bar = False
        self._vertical_icon_alignment = "center"
        self._popup_rect = (0,0,0,0)
        self._popup_hover = -1
        self._popup_scroll = 0
        self._search = ""
        self.row_height = 32

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self,value):
        if not -1 <= int(value) < len(self.items): raise IndexError(value)
        self._selected = int(value)
        self._text = as_item(self.items[value]).text if value >= 0 else ""

    def add_item(self,text,icon=None):
        self.items.append(Item(self._caption(text),icon))
        if self.selected < 0: self.selected = 0
        return len(self.items)-1

    def _activate(self):
        self.pressed.emit()
        if self.game._ui.popup is self:
            self.game._ui.popup = None
        else:
            self._search = ""
            self._popup_rect = popup_bounds(self,max(180,self.size.x),min(8,len(self.items))*self.row_height+4)
            self._popup_hover = self.selected
            self.game._ui.popup = self

    def _choose(self,index):
        item = as_item(self.items[index])
        if not item.disabled and item.selectable:
            self.selected = index
            self.item_selected.emit(index)
            self.game._ui.popup = None

    def _visible_items(self):
        return [i for i,item in enumerate(self.items) if self._search.casefold() in self.localize(as_item(item).text).casefold()]

    def _popup_event(self,event):
        if event.type == Event.TEXT_ENTERED and self.search_bar:
            value = chr(event.unicode) if isinstance(event.unicode,int) else event.unicode
            if value.isprintable(): self._search += value
            self._popup_scroll = 0
            return True
        visible = self._visible_items()
        if event.type == Event.KEY_PRESSED:
            if event.code == Keyboard.ESCAPE:
                self.game._ui.popup = None
            elif event.code == Keyboard.BACK_SPACE and self.search_bar:
                self._search = self._search[:-1]
            elif event.code in (Keyboard.UP,Keyboard.DOWN) and visible:
                current = visible.index(self._popup_hover) if self._popup_hover in visible else -1
                self._popup_hover = visible[(current+(-1 if event.code == Keyboard.UP else 1))%len(visible)]
                self.item_focused.emit(self._popup_hover)
                row = visible.index(self._popup_hover)
                self._popup_scroll = max(0,row-6)
            elif event.code == Keyboard.RETURN and self._popup_hover in visible:
                self._choose(self._popup_hover)
            return True
        if event.type in (Event.MOUSE_MOVED,Event.MOUSE_BUTTON_PRESSED,Event.MOUSE_WHEEL_SCROLLED):
            x,y,width,height = self._popup_rect
            inside = x <= event.position.x < x+width and y <= event.position.y < y+height
            row = int((event.position.y-y-2)//self.row_height)+self._popup_scroll
            if event.type == Event.MOUSE_WHEEL_SCROLLED:
                self._popup_scroll = max(0,min(max(0,len(visible)-7),self._popup_scroll-int(event.delta)))
            elif event.type == Event.MOUSE_MOVED and inside and 0 <= row < len(visible):
                if self._popup_hover != visible[row]:
                    self._popup_hover = visible[row]
                    self.item_focused.emit(self._popup_hover)
            elif event.type == Event.MOUSE_BUTTON_PRESSED:
                if inside and 0 <= row < len(visible): self._choose(visible[row])
                else: self.game._ui.popup = None
            return True
        return event.type in (Event.MOUSE_BUTTON_RELEASED,Event.TEXT_ENTERED)

    def _render_popup(self,target):
        original = target.view
        try:
            states = popup_states(self,target)
            _,_,width,height = self._popup_rect
            box(target,states,(0,0,width,height),self.theme.background,self.theme.border)
            visible_items = self._visible_items()
            self._popup_scroll = min(self._popup_scroll, max(0, len(visible_items)-7))
            for row,index in enumerate(visible_items[self._popup_scroll:self._popup_scroll+7]):
                item = as_item(self.items[index])
                if index == self._popup_hover:
                    box(target,states,(2,2+row*self.row_height,width-4,self.row_height),self.theme.selection)
                label(target,states,self,item.text,(10,2+row*self.row_height,width-20,self.row_height),
                      tint=self.theme.muted if item.disabled else self.theme.text)
        finally:
            target.view = original


    @property
    def search_bar(self):
        return self._search_bar

    @search_bar.setter
    def search_bar(self, value):
        self._search_bar = value

    @property
    def items(self):
        return self._items

    @items.setter
    def items(self, value):
        self._items = value

    @property
    def vertical_icon_alignment(self):
        return self._vertical_icon_alignment

    @vertical_icon_alignment.setter
    def vertical_icon_alignment(self, value):
        self._vertical_icon_alignment = value


class ColorPickerButton(BaseButton):
    color_changed = Signal()
    picker_created = Signal()
    popup_closed = Signal()

    def __init__(self,name=None):
        super().__init__(name)
        self._color = Color.WHITE
        self._edit_alpha = True
        self._edit_intensity = False
        self._popup_rect = (0,0,280,190)
        self._channel = None
        self._created = False

    @property
    def color(self):
        return Color(self._color.r,self._color.g,self._color.b,self._color.a)

    @color.setter
    def color(self,value):
        value = color(value)
        old = self._color
        self._color = Color(value.r,value.g,value.b,value.a)
        if (old.r,old.g,old.b,old.a) != (value.r,value.g,value.b,value.a):
            self.color_changed.emit(self.color)

    def _activate(self):
        self.pressed.emit()
        self._popup_rect = popup_bounds(self,280,190 if self.edit_alpha else 154)
        self.game._ui.popup = self
        if not self._created:
            self._created = True
            self.picker_created.emit()

    def _close(self):
        self.game._ui.popup = None
        self._channel = None
        self.popup_closed.emit()

    def _set_channel(self,x):
        values = [self.color.r,self.color.g,self.color.b,self.color.a]
        values[self._channel] = int(max(0,min(255,(x-42)/210*255)))
        self.color = Color(*values)

    def _popup_event(self,event):
        if event.type == Event.KEY_PRESSED and event.code in (Keyboard.ESCAPE,Keyboard.RETURN):
            self._close()
            return True
        if event.type in (Event.MOUSE_BUTTON_PRESSED,Event.MOUSE_MOVED,Event.MOUSE_BUTTON_RELEASED):
            x = event.position.x-self._popup_rect[0]
            y = event.position.y-self._popup_rect[1]
            if event.type == Event.MOUSE_BUTTON_PRESSED:
                if not (0 <= x < self._popup_rect[2] and 0 <= y < self._popup_rect[3]):
                    self._close()
                else:
                    channel = int((y-12)//36)
                    if 0 <= channel < (4 if self.edit_alpha else 3):
                        self._channel = channel
                        self._set_channel(x)
            elif event.type == Event.MOUSE_MOVED and self._channel is not None:
                self._set_channel(x)
            elif event.type == Event.MOUSE_BUTTON_RELEASED:
                self._channel = None
            return True
        return True

    def _render_popup(self,target):
        original = target.view
        try:
            states = popup_states(self,target)
            box(target,states,(0,0,self._popup_rect[2],self._popup_rect[3]),self.theme.background,self.theme.border)
            channels = [self.color.r,self.color.g,self.color.b,self.color.a]
            for index in range(4 if self.edit_alpha else 3):
                y = 12+index*36
                label(target,states,self,"RGBA"[index],(12,y,22,26))
                tint = [(220,90,90),(90,210,140),(90,150,240),self.theme.muted][index]
                box(target,states,(42,y+10,210,6),self.theme.surface)
                box(target,states,(42,y+10,210*channels[index]/255,6),tint)
                box(target,states,(40+210*channels[index]/255,y+4,4,18),self.theme.text)
        finally:
            target.view = original

    def render(self,target,states):
        super().render(target,states)
        box(target,states,(8,7,max(0,self.size.x-16),max(0,self.size.y-14)),self.color,self.theme.border)


    @property
    def edit_alpha(self):
        return self._edit_alpha

    @edit_alpha.setter
    def edit_alpha(self, value):
        self._edit_alpha = value

    @property
    def edit_intensity(self):
        return self._edit_intensity

    @edit_intensity.setter
    def edit_intensity(self, value):
        self._edit_intensity = value
