from typing import Any, List, Tuple

from ..core import Node, Signal


class Anchor: pass

#anchor zımbırtısı olmalı.
class Control(Node):
    mouse_entered = Signal()
    mouse_exited = Signal()
    resized = Signal()
    gui_input = Signal()
    focus_entered = Signal()
    focus_exited = Signal()

    _font:Any
    _position:Any
    _rotation:Any
    _scale:int
    _offset:Any
    _size:Any
    _min_size:Any
    _max_size:Any
    _transform:Any

    _material:Any


    @property
    def font(self):
        return self._font

    @font.setter
    def font(self, font):
        self._font = font


class Panel(Control): pass

class Label(Control):

    _text:str = ""
    _uppercase:bool = False
    _horizontal_alignment:str = "center"
    _vertical_alignment:str = "center"
    _clip_text:bool = False
    #_wrap


    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text:str):
        self._text = text

class RichLabel(Control):
    finished = Signal()
    meta_clicked = Signal()
    meta_hover_ended = Signal()
    meta_hover_started = Signal()

    _bbcode_enabled:bool = False
    _text:str


    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text: str):
        self._text = text

class BaseButton(Control):
    toggled = Signal()
    pressed = Signal()
    button_up = Signal()
    button_down = Signal()

    _text: str
    #icon micon da buraya gelcek.

class CheckBox(BaseButton):
    pass

class CheckButton(BaseButton):
    pass

class Button(BaseButton):



    _text_alignment:str = "center"
    _disabled:bool = False
    _toggle_mode:bool = False
    _button_pressed:bool = False
    _icon:Any
    _icon_alignment:str = "left"



    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text: str):
        self._text = text

class TextureButton(BaseButton): pass

class LineEdit(Control):
    text_changed = Signal()
    text_submitted = Signal()

    _text:str
    _placeholder:str
    _alignment:str = "center"
    _max_length:int
    _editable:bool
    _blink:bool = True
    _secret:bool
    _secret_character:str = "*"
    _right_icon:Any

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text:str):
        self._text = text

class ProgressBar(Control):
    changed = Signal()
    value_changed = Signal()

    _show_percentage:bool = True
    _fill_mode:str
    #begin2end, end2begin, top2bottom >

    _min_value:float = 0
    _max_value:float = 100
    _value:float = 1
    _step:float = 0.01
    _rounded:bool = False

class TextureProgressBar(ProgressBar):

    _fill_mode:str = "fill" #left-right, clock vs.
    _nine_patch_stretch:bool = False

class Slider(Control):

    changed = Signal()
    value_changed = Signal()

    # drag_started = Signal()
    # drag_ended = Signal()

    _disabled:bool = False
    _scrollable:bool = True

    _min_value: float = 0
    _max_value: float = 100
    _value: float = 1
    _step: float = 0.01
    _rounded: bool = False

class SpinBox(Control):
    changed = Signal()
    value_changed = Signal()

    _alignment:str = "center"
    _prefix:str
    _suffix:str

class ScrollBar(Control):
    scrolling = Signal()
    changed = Signal()
    value_changed = Signal()

    _min_value: float = 0
    _max_value: float = 100
    _value: float = 1
    _step: float = 0.01
    _rounded: bool = False

class TextEdit(Control):
    caret_changed = Signal()
    gutter_added = Signal()
    gutter_removed = Signal()
    gutter_clicked = Signal()
    lines_edited_from = Signal()
    text_changed = Signal()
    text_set = Signal()

    _text:str
    _placeholder:str
    _editable:bool = True
    _context_menu_enabled:bool = False
    _emoji_menu_enabled:bool = False
    #_scroll
    _blink:bool = True

#class RadioButton(Control): pass

class Item():
    _text:str
    _icon:Any
    _selectable:bool = True
    _disabled:bool = False

class ItemList(Control):
    empty_clicked = Signal()
    item_activated = Signal()
    item_clicked = Signal()
    item_selected = Signal()
    multi_selected = Signal()

    _select_mode:str = "single" #multi, toggle
    _items:List[Item] = []

    _icon_mode:str = "left" # top
    _icon_scale:float = 1.0
    _fixed_icon_size:Tuple[int,int] = (0,0)

class TabBar(Control):
    tab_button_pressed = Signal()
    tab_changed = Signal()
    tab_clicked = Signal()
    tab_close_pressed = Signal()
    tab_hovered = Signal()
    tab_selected = Signal()

    _current_tab:int = -1
    _tab_alignment:str = "center" #left, right
    _tab_close_display:bool = False
    _max_tab_width:int = 0

    _tabs:List[str] = [] #title, tooltip, icon, disabled

class OptionButton(BaseButton):
    item_focused = Signal()
    item_selected = Signal()

    button_down = Signal()
    button_up = Signal()
    pressed = Signal()
    toggled = Signal()

    _selected:int = -1
    _search_bar:bool = False
    _items:List[Item]
    _icon_alignment:str = "left"
    _vertical_icon_alignment:str = "center"

    _disabled:bool = False

class ColorPickerButton(BaseButton):
    color_changed = Signal()
    picker_created = Signal()
    popup_closed = Signal()

    button_down = Signal()
    button_up = Signal()
    pressed = Signal()
    toggled = Signal()

    _color:Any
    _edit_alpha:bool = True
    _edit_intensity:bool = True
    _text:str
    _icon:Any

class NinePatchRect(Control):
    texture_changed = Signal()

    _texture:Any
    _draw_center:bool = True
    _region_rect:List[float] = [0.0, 0.0, 0.0, 0.0]
    _patch_margin: List[float] = [0.0, 0.0, 0.0, 0.0]