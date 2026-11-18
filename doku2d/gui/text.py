import re
import shlex
from sfml.graphics import Color, TextStyle, RenderStates, Transform
from sfml.window import Event, Keyboard
from .clipboard import get_text, set_text
from ..core import Signal
from .base import Control
from .effects import CharacterEffect, DEFAULT_EFFECTS
from .theme import box, label, measure, text_object, clipped


class Label(Control):
    def __init__(self, name=None, *, text=""):
        super().__init__(name)
        self._text = str(text)
        self._uppercase = False
        self._horizontal_alignment = "left"
        self._vertical_alignment = "center"
        self._clip_text = True
        self.mouse_filter = "ignore"

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = str(value)

    def render(self, target, states):
        self.clip_contents = self.clip_text
        label(target, states, self, self.text.upper() if self.uppercase else self.text,
              align=self.horizontal_alignment, valign=self.vertical_alignment)


    @property
    def uppercase(self):
        return self._uppercase

    @uppercase.setter
    def uppercase(self, value):
        self._uppercase = value

    @property
    def horizontal_alignment(self):
        return self._horizontal_alignment

    @horizontal_alignment.setter
    def horizontal_alignment(self, value):
        self._horizontal_alignment = value

    @property
    def vertical_alignment(self):
        return self._vertical_alignment

    @vertical_alignment.setter
    def vertical_alignment(self, value):
        self._vertical_alignment = value

    @property
    def clip_text(self):
        return self._clip_text

    @clip_text.setter
    def clip_text(self, value):
        self._clip_text = value


class RichLabel(Control):
    finished = Signal()
    meta_clicked = Signal()
    meta_hover_ended = Signal()
    meta_hover_started = Signal()

    def __init__(self, name=None, *, text=""):
        super().__init__(name)
        self._text = str(text)
        self._bbcode_enabled = False
        self._links = []
        self._hover_meta = None
        self._dirty = True
        self._elapsed = 0.0
        self._effects = dict(DEFAULT_EFFECTS)
        self._layout_cache = None
        self.effect_padding = 7.0

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = str(value)
        self._dirty = True
        self._layout_cache = None

    @property
    def bbcode_enabled(self):
        return self._bbcode_enabled

    @bbcode_enabled.setter
    def bbcode_enabled(self, value):
        self._bbcode_enabled = bool(value)
        self._layout_cache = None

    @property
    def elapsed(self):
        return self._elapsed

    def restart_effects(self):
        self._elapsed = 0.0

    def install_effect(self, name, callback):
        if not re.fullmatch(r"[a-zA-Z_]\w*",name) or not callable(callback):
            raise ValueError("An effect needs a valid tag name and callable")
        if name in ("b","i","color","url"):
            raise ValueError("Effect name is reserved for formatting")
        self._effects[name] = callback
        self._layout_cache = None

    def _styled_runs(self):
        if not self.bbcode_enabled:
            yield self.text,0,self.theme.text,None,()
            return
        stack = [(None,0,self.theme.text,None,())]
        pattern = r"(\[/?[a-zA-Z_]\w*(?:[^\]]*)\])"
        for token in re.split(pattern,self.text):
            if not token:
                continue
            match = re.fullmatch(r"\[(/?)([a-zA-Z_]\w*)([^\]]*)\]",token)
            if match is None:
                yield token,*stack[-1][1:]
                continue
            closing,tag,arguments = match.groups()
            if tag not in self._effects and tag not in ("b","i","color","url"):
                yield token,*stack[-1][1:]
                continue
            if closing:
                for index in range(len(stack)-1,0,-1):
                    if stack[index][0] == tag:
                        stack = stack[:index]
                        break
                continue
            _,style,tint,meta,effects = stack[-1]
            if tag == "b":
                style |= int(TextStyle.BOLD)
            elif tag == "i":
                style |= int(TextStyle.ITALIC)
            elif tag == "url":
                meta = arguments.lstrip("=").strip()
            elif tag == "color":
                try:
                    value = arguments.lstrip("=").strip().lstrip("#")
                    if len(value) not in (6,8):
                        raise ValueError()
                    tint = tuple(int(value[i:i+2],16) for i in range(0,len(value),2))
                except ValueError:
                    tint = self.theme.text
            else:
                try:
                    options = dict(item.split("=",1) for item in shlex.split(arguments) if "=" in item)
                except ValueError:
                    options = {}
                effects = (*effects,(tag,options))
            stack.append((tag,style,tint,meta,effects))

    def _runs(self):
        for value,style,tint,meta,_ in self._styled_runs():
            yield value,style,tint,meta

    def _layout_runs(self):
        font = self.font or self.theme.get_font()
        key = (self.text,self.bbcode_enabled,tuple(self.size),self.font_size,
               id(font),self.effect_padding,tuple(self.theme.text))
        if self._layout_cache is not None and self._layout_cache[0] == key:
            return self._layout_cache[1]
        padding = self.effect_padding
        x,y = padding,padding
        reference = text_object(self,"Hg").local_bounds
        row_height = self.font_size*1.6
        character_index = 0
        result = []
        for value,style,tint,meta,effects in self._styled_runs():
            for token in re.split(r"(\s+)",value):
                if not token:
                    continue
                for line_index,line in enumerate(token.split("\n")):
                    if line_index:
                        x,y = padding,y+row_height
                    text = text_object(self,line)
                    text.style = style | (int(TextStyle.UNDERLINED) if meta else 0)
                    width = text.find_character_pos(len(line)).x
                    if x+width > self.size.x-padding and x > padding and not line.isspace():
                        x,y = padding,y+row_height
                    # Break oversized words too, so effect text respects the control width.
                    for index,character in enumerate(line):
                        position = text.find_character_pos(index).x
                        next_position = text.find_character_pos(index+1).x
                        advance = next_position-position
                        if x+advance > self.size.x-padding and x > padding and not character.isspace():
                            x,y = padding,y+row_height
                        result.append((character,x,y-reference.position.y,style,tint,meta,effects,character_index))
                        x += advance
                        character_index += 1
        self._layout_cache = (key,result)
        return result

    def update(self, dt):
        self._elapsed += dt

    def render(self, target, states):
        self._links = []
        for value,x,y,style,tint,meta,effects,index in self._layout_runs():
            character = CharacterEffect(index,self.elapsed,self.theme.accent if meta and tint == self.theme.text else tint)
            for name,options in effects:
                self._effects[name](character,options)
            if not character.visible:
                continue
            text = text_object(self,value)
            text.style = style | (int(TextStyle.UNDERLINED) if meta else 0)
            bounds = text.local_bounds
            # Scaling around the glyph center keeps animated runs on their baseline.
            origin = (bounds.position.x+bounds.size.x/2,bounds.position.y+bounds.size.y/2)
            text.origin = origin
            text.scale = (character.scale,character.scale)
            text.position = (x+origin[0]+character.offset.x,y+origin[1]+character.offset.y)
            text.fill_color = Color(*character.color)
            target.draw(text,states)
            if meta:
                rect = text.global_bounds
                self._links.append(((rect.position.x,rect.position.y,rect.size.x,rect.size.y),meta))
        if self._dirty:
            self._dirty = False
            self.finished.emit()

    def _meta_at(self, point):
        return next((meta for (x,y,w,h),meta in self._links
                     if x <= point.x < x+w and y <= point.y < y+h),None)

    def _pointer_move(self, point, pointer=0):
        meta = self._meta_at(point)
        if meta != self._hover_meta:
            if self._hover_meta is not None:
                self.meta_hover_ended.emit(self._hover_meta)
            self._hover_meta = meta
            if meta is not None:
                self.meta_hover_started.emit(meta)

    def _pointer_down(self, point, button=0, pointer=0):
        meta = self._meta_at(point)
        if button == 0 and meta is not None:
            self.meta_clicked.emit(meta)
        return False


class _Editor(Control):
    text_changed = Signal()
    text_submitted = Signal()
    caret_changed = Signal()

    def __init__(self, name=None, *, text="", multiline=False):
        super().__init__(name)
        self._text = str(text)
        self._placeholder = ""
        self._editable = True
        self._alignment = "left"
        self._max_length = 0
        self._blink = True
        self._secret = False
        self._secret_character = "*"
        self._right_icon = None
        self._multiline = multiline
        self._cursor = len(self._text)
        self._selection_anchor = self._cursor
        self._caret_time = 0.0
        self._scroll_x = 0.0
        self._scroll_y = 0.0
        self._dragging = False
        self._ensure_caret = True
        self._gutters = []
        self._undo = []
        self._redo = []
        self._context_rows = []
        self._popup_rect = (0, 0, 0, 0)
        self.focusable = True
        if multiline: self.size = (240, 120)

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        value = str(value)
        if not self._multiline: value = value.replace("\r", "").replace("\n", "")
        if self.max_length: value = value[:self.max_length]
        if value != self._text:
            self._text = value
            self._cursor = min(self._cursor, len(value))
            self._selection_anchor = self._cursor
            self.text_changed.emit(value)

    @property
    def cursor(self):
        return self._cursor

    @cursor.setter
    def cursor(self, value):
        self._move_cursor(value, False)

    def _move_cursor(self, value, selecting=False):
        self._cursor = max(0, min(len(self.text), int(value)))
        if not selecting:
            self._selection_anchor = self._cursor
        self._caret_time = 0.0
        self._ensure_caret = True
        self.caret_changed.emit()

    @property
    def selected_text(self):
        a, b = sorted((self._selection_anchor, self._cursor))
        return self.text[a:b]

    def select_all(self):
        self._selection_anchor = 0
        self._cursor = len(self.text)


    def _replace_selection(self, value):
        if not self.editable: return
        a, b = sorted((self._selection_anchor, self._cursor))
        if self.max_length:
            value = value[:max(0, self.max_length-(len(self.text)-(b-a)))]
        previous = self.text
        replacement = self.text[:a]+value+self.text[b:]
        if replacement != previous:
            self._undo.append((previous, self._cursor, self._selection_anchor))
            self._redo.clear()
        self.text = replacement
        self._move_cursor(a+len(value))
        if self._multiline and previous != self.text:
            self.lines_edited_from.emit(previous[:a].count("\n"), self.text[:self._cursor].count("\n"))


    def _copy(self, *, cut=False):
        if self.secret or not self.selected_text:
            return
        if set_text(self.selected_text) and cut and self.editable:
            self._replace_selection("")

    def _paste(self):
        value = get_text()
        if not value:
            return
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        if not self._multiline:
            value = value.replace("\n", " ")
        self._replace_selection(value)

    def _text_input(self, value):
        if self.editable:
            value = "".join(ch for ch in value if ch >= " " and ch != "\x7f")
            if value: self._replace_selection(value)
        return True

    def _key(self, event):
        if event.type != Event.KEY_PRESSED: return False
        key, shift, ctrl = event.code, event.shift, event.control
        if ctrl and key in (Keyboard.Z, Keyboard.Y) and self.editable:
            source, destination = (self._redo, self._undo) if key == Keyboard.Y or shift else (self._undo, self._redo)
            if source:
                destination.append((self.text, self._cursor, self._selection_anchor))
                value, cursor, anchor = source.pop()
                self.text = value
                self._move_cursor(cursor)
                self._selection_anchor = anchor
        elif ctrl and key == Keyboard.A:
            self.select_all()
        elif ctrl and key in (Keyboard.C, Keyboard.X):
            self._copy(cut=key == Keyboard.X)
        elif ctrl and key == Keyboard.V:
            self._paste()
        elif key in (Keyboard.LEFT, Keyboard.RIGHT):
            direction = -1 if key == Keyboard.LEFT else 1
            if not shift and self.selected_text:
                target = min(self._cursor, self._selection_anchor) if direction < 0 else max(self._cursor, self._selection_anchor)
            else:
                target = self._cursor+direction
                if ctrl:
                    while 0 < target < len(self.text) and not self.text[target].isspace(): target += direction
            self._move_cursor(target, shift)
        elif key in (Keyboard.HOME, Keyboard.END):
            if key == Keyboard.HOME:
                target = 0 if ctrl else self.text.rfind("\n", 0, self._cursor)+1
            else:
                end = self.text.find("\n", self._cursor)
                target = len(self.text) if ctrl or end == -1 else end
            self._move_cursor(target, shift)
        elif key in (Keyboard.UP, Keyboard.DOWN) and self._multiline:
            lines = self.text.split("\n")
            line = self.text[:self._cursor].count("\n")
            column = self._cursor-(self.text.rfind("\n", 0, self._cursor)+1)
            next_line = max(0, min(len(lines)-1, line+(-1 if key == Keyboard.UP else 1)))
            self._move_cursor(sum(len(v)+1 for v in lines[:next_line])+min(column,len(lines[next_line])), shift)
        elif key in (Keyboard.BACK_SPACE, Keyboard.DELETE):
            if not self.selected_text:
                self._selection_anchor = max(0, self._cursor-1) if key == Keyboard.BACK_SPACE else min(len(self.text),self._cursor+1)
            self._replace_selection("")
        elif key == Keyboard.RETURN:
            if self._multiline: self._replace_selection("\n")
            else: self.text_submitted.emit(self.text)
        elif key == Keyboard.ESCAPE:
            self.game._ui.set_focus(None)
        else:
            return True
        return True

    def _display(self, value):
        return self.secret_character*len(value) if self.secret else value

    def _content_left(self):
        return 10 + sum(gutter["width"] for gutter in self._gutters)

    def _viewport(self):
        left = self._content_left()
        return (left,8,max(0,self.size.x-left-10),max(0,self.size.y-16))

    def _render_scrollbars(self, target, states):
        pass

    def _line_geometry(self, value, row=0, *, masked=True):
        text = text_object(self, self._display(value) if masked else value)
        reference = text_object(self, "Hg").local_bounds
        left, _, width, _ = self._viewport()
        advance = text.find_character_pos(len(text.string)).x
        extra = max(0, width-advance)
        alignment = {"left":0,"center":extra/2,"right":extra}.get(self.alignment,0)
        top = round((self.size.y-reference.size.y)/2)
        if self._multiline:
            top = round(8+row*self.font_size*1.5-self._scroll_y)
            origin_y = top-reference.position.y
        else:
            bounds = text.local_bounds
            # Center the actual visible glyphs, including bullets and asterisks.
            origin_y = (self.size.y-bounds.size.y)/2-bounds.position.y
        text.position = (round(left+alignment-self._scroll_x),round(origin_y))
        return text, top, reference.size.y

    def _index_at(self, point):
        lines = self.text.split("\n")
        row = 0
        if self._multiline:
            row = max(0, min(len(lines)-1, int((point.y-8+self._scroll_y)/(self.font_size*1.5))))
        text, _, _ = self._line_geometry(lines[row], row)
        column = min(range(len(lines[row])+1),
                     key=lambda index: abs(text.find_character_pos(index).x-point.x))
        return sum(len(value)+1 for value in lines[:row])+column

    def _pointer_down(self, point, button=0, pointer=0):
        if button == 1 and self._multiline and self.context_menu_enabled:
            from .choices import popup_bounds
            self._context_rows = ["Cut", "Copy", "Paste", "Select all"]
            if self.emoji_menu_enabled:
                self._context_rows.append("Emoji")
            self._popup_rect = popup_bounds(self, 180, len(self._context_rows)*32+4)
            self.game._ui.popup = self
            return False
        if button != 0:
            return False
        if self._gutters and point.x < self._content_left():
            x = 0
            for index, gutter in enumerate(self._gutters):
                x += gutter["width"]
                if point.x < x:
                    line = max(0, int((point.y-8+self._scroll_y)/(self.font_size*1.5)))
                    self.gutter_clicked.emit(line,index)
                    return False
        self._move_cursor(self._index_at(point))
        self._dragging = True
        return True

    def _pointer_move(self, point, pointer=0):
        if self._dragging: self._move_cursor(self._index_at(point), True)

    def _pointer_up(self, point, button=0, pointer=0):
        self._dragging = False

    def _cancel_pointer(self):
        self._dragging = False

    def _wheel(self, delta):
        if not self._multiline: return False
        lines = len(self.text.split("\n"))
        self._scroll_y = max(0, min(max(0, lines*self.font_size*1.5-self.size.y+16),
                                  self._scroll_y-delta*self.font_size*3))
        self._ensure_caret = False
        return True

    def update(self, dt):
        self._caret_time += dt

    def render(self, target, states):
        border = self.theme.accent if self.focused else self.theme.border
        box(target,states,(0,0,*self.size),self.theme.background,border,radius=self.theme.radius)
        lines = self.text.split("\n")
        viewport = self._viewport()
        row_height = self.font_size*1.5
        row = self.text[:self._cursor].count("\n")
        column = self._cursor-(self.text.rfind("\n",0,self._cursor)+1)
        caret_advance = text_object(self,self._display(lines[row])).find_character_pos(column).x
        if self.focused and self._ensure_caret:
            width = max(0,viewport[2]-2)
            self._scroll_x = max(0,min(self._scroll_x,caret_advance))
            if caret_advance-self._scroll_x > width:
                self._scroll_x = caret_advance-width
            if self._multiline:
                if row*row_height < self._scroll_y:
                    self._scroll_y = row*row_height
                if (row+1)*row_height-self._scroll_y > viewport[3]:
                    self._scroll_y = (row+1)*row_height-viewport[3]
            self._ensure_caret = False
        selection_start,selection_end = sorted((self._selection_anchor,self._cursor))
        start = 0
        # Single-line fields clip horizontally while using the full field height.
        text_clip = viewport if self._multiline else (viewport[0],1,viewport[2],max(0,self.size.y-2))
        with clipped(target,states,text_clip) as visible:
            if visible:
                for index,value in enumerate(lines):
                    if self._multiline and ((index+1)*row_height < self._scroll_y or index*row_height > self._scroll_y+viewport[3]):
                        start += len(value)+1
                        continue
                    text,top,height = self._line_geometry(value,index)
                    left = max(0,selection_start-start)
                    right = min(len(value),selection_end-start)
                    if right > left:
                        x = text.find_character_pos(left).x
                        width = text.find_character_pos(right).x-x
                        box(target,states,(x,top-2,width,height+4),self.theme.selection,radius=2)
                    text.fill_color = Color(*self.theme.text)
                    target.draw(text,states)
                    start += len(value)+1
                if not self.text:
                    placeholder,_,_ = self._line_geometry(self.placeholder,masked=False)
                    placeholder.fill_color = Color(*self.theme.muted)
                    target.draw(placeholder,states)
                if self.focused and (not self.blink or self._caret_time%1.0 < 0.55):
                    text,top,height = self._line_geometry(lines[row],row)
                    x = round(text.find_character_pos(column).x)
                    box(target,states,(x,top-2,1,height+4),self.theme.accent)
        self._draw_gutters(target,states)
        self._render_scrollbars(target,states)


    def _draw_gutters(self, target, states):
        x = 0
        row_height = self.font_size*1.5
        for gutter in self._gutters:
            box(target,states,(x,0,gutter["width"],self.size.y),self.theme.surface)
            for row in range(len(self.text.split("\n"))):
                y = 8+row*row_height-self._scroll_y
                if y+row_height < 0 or y > self.size.y:
                    continue
                value = str(row+1) if gutter["line_numbers"] else gutter["label"]
                label(target,states,self,value,(x,y,gutter["width"]-4,row_height),align="right",valign="top",tint=self.theme.muted)
            x += gutter["width"]

    @property
    def placeholder(self):
        return self._placeholder

    @placeholder.setter
    def placeholder(self, value):
        self._placeholder = value

    @property
    def alignment(self):
        return self._alignment

    @alignment.setter
    def alignment(self, value):
        self._alignment = value

    @property
    def max_length(self):
        return self._max_length

    @max_length.setter
    def max_length(self, value):
        self._max_length = value

    @property
    def editable(self):
        return self._editable

    @editable.setter
    def editable(self, value):
        self._editable = value

    @property
    def blink(self):
        return self._blink

    @blink.setter
    def blink(self, value):
        self._blink = value

    @property
    def secret(self):
        return self._secret

    @secret.setter
    def secret(self, value):
        self._secret = value

    @property
    def secret_character(self):
        return self._secret_character

    @secret_character.setter
    def secret_character(self, value):
        self._secret_character = value

    @property
    def right_icon(self):
        return self._right_icon

    @right_icon.setter
    def right_icon(self, value):
        self._right_icon = value


    def _popup_event(self, event):
        if event.type == Event.KEY_PRESSED and event.code == Keyboard.ESCAPE:
            self.game._ui.popup = None
            return True
        if event.type == Event.MOUSE_BUTTON_PRESSED:
            x = event.position.x-self._popup_rect[0]
            y = event.position.y-self._popup_rect[1]
            index = int((y-2)//32)
            if 0 <= x < self._popup_rect[2] and 0 <= index < len(self._context_rows):
                action = self._context_rows[index]
                if action == "Emoji":
                    self._context_rows = ["🙂", "❤️", "⭐", "🎮", "✅"]
                    return True
                if action == "Select all":
                    self.select_all()
                elif action in ("Copy", "Cut"):
                    self._copy(cut=action == "Cut")
                elif action == "Paste":
                    self._paste()
                else:
                    self._replace_selection(action)
            self.game._ui.popup = None
            return True
        return True

    def _render_popup(self, target):
        from .choices import popup_states
        original = target.view
        try:
            states = popup_states(self, target)
            box(target, states, (0,0,self._popup_rect[2],self._popup_rect[3]),
                self.theme.background,self.theme.border)
            for index, title in enumerate(self._context_rows):
                label(target, states, self, title, (10,2+index*32,self._popup_rect[2]-20,32))
        finally:
            target.view = original


class LineEdit(_Editor):
    pass


class TextEdit(_Editor):
    gutter_added = Signal()
    gutter_removed = Signal()
    gutter_clicked = Signal()
    lines_edited_from = Signal()
    text_set = Signal()

    def __init__(self, name=None, *, text=""):
        super().__init__(name,text=text,multiline=True)
        self._context_menu_enabled = True
        self._emoji_menu_enabled = False
        from .ranges import ScrollBar
        self._v_scrollbar = ScrollBar(value=0, max_value=0, step=1)
        self._v_scrollbar.vertical = True
        self._h_scrollbar = ScrollBar(value=0, max_value=0, step=1)
        self._scrollbar_drag = None
        self._syncing_scrollbars = False
        self._scroll_cache = None
        self._v_scrollbar.value_changed.connect(self._vertical_scrolled)
        self._h_scrollbar.value_changed.connect(self._horizontal_scrolled)


    @property
    def placeholder(self):
        return self._placeholder

    @placeholder.setter
    def placeholder(self, value):
        self._placeholder = value

    @property
    def editable(self):
        return self._editable

    @editable.setter
    def editable(self, value):
        self._editable = value

    @property
    def context_menu_enabled(self):
        return self._context_menu_enabled

    @context_menu_enabled.setter
    def context_menu_enabled(self, value):
        self._context_menu_enabled = value

    @property
    def emoji_menu_enabled(self):
        return self._emoji_menu_enabled

    @emoji_menu_enabled.setter
    def emoji_menu_enabled(self, value):
        self._emoji_menu_enabled = value

    @property
    def blink(self):
        return self._blink

    @blink.setter
    def blink(self, value):
        self._blink = value


    def add_gutter(self, label="", *, width=30, line_numbers=True):
        if width <= 0:
            raise ValueError("Gutter width must be positive")
        self._gutters.append({"label": str(label), "width": float(width), "line_numbers": bool(line_numbers)})
        self.gutter_added.emit()
        return len(self._gutters)-1

    def remove_gutter(self, index):
        del self._gutters[index]
        self.gutter_removed.emit()


    @property
    def v_scrollbar(self):
        return self._v_scrollbar

    @property
    def h_scrollbar(self):
        return self._h_scrollbar

    def _vertical_scrolled(self, value):
        if not self._syncing_scrollbars:
            self._scroll_y = value
            self._ensure_caret = False

    def _horizontal_scrolled(self, value):
        if not self._syncing_scrollbars:
            self._scroll_x = value
            self._ensure_caret = False

    def _viewport(self):
        font = self.font or self.theme.get_font()
        key = (self.text,tuple(self.size),self.font_size,id(font),self._content_left())
        if self._scroll_cache is None or self._scroll_cache[0] != key:
            lines = self.text.split("\n")
            self._scroll_cache = (key,max((measure(self,value) for value in lines),default=0)+2,
                                  len(lines)*self.font_size*1.5)
        _,content_width,content_height = self._scroll_cache
        left = self._content_left()
        full_width,full_height = max(0,self.size.x-left-10),max(0,self.size.y-16)
        vertical = horizontal = False
        thickness = 12
        for _ in range(3):
            width = max(0,full_width-(thickness if vertical else 0))
            height = max(0,full_height-(thickness if horizontal else 0))
            horizontal = content_width > width
            vertical = content_height > height
        width = max(0,full_width-(thickness if vertical else 0))
        height = max(0,full_height-(thickness if horizontal else 0))
        self._syncing_scrollbars = True
        try:
            self.v_scrollbar.visible = vertical
            self.h_scrollbar.visible = horizontal
            self.v_scrollbar.position = (self.size.x-thickness-2,6)
            self.v_scrollbar.size = (thickness,max(0,self.size.y-12-(thickness if horizontal else 0)))
            self.h_scrollbar.position = (left,self.size.y-thickness-2)
            self.h_scrollbar.size = (width,thickness)
            self.v_scrollbar.page = height
            self.h_scrollbar.page = width
            self.v_scrollbar.max_value = max(0,content_height-height)
            self.h_scrollbar.max_value = max(0,content_width-width)
            self._scroll_y = max(0,min(self.v_scrollbar.max_value,self._scroll_y))
            self._scroll_x = max(0,min(self.h_scrollbar.max_value,self._scroll_x))
            self.v_scrollbar.value = self._scroll_y
            self.h_scrollbar.value = self._scroll_x
        finally:
            self._syncing_scrollbars = False
        return (left,8,width,height)

    def _pointer_down(self, point, button=0, pointer=0):
        self._viewport()
        for scrollbar in (self.v_scrollbar,self.h_scrollbar):
            if scrollbar.visible:
                local = point-scrollbar.position
                if 0 <= local.x < scrollbar.size.x and 0 <= local.y < scrollbar.size.y:
                    self._scrollbar_drag = scrollbar
                    return scrollbar._pointer_down(local,button,pointer)
        return super()._pointer_down(point,button,pointer)

    def _pointer_move(self, point, pointer=0):
        if self._scrollbar_drag is not None:
            scrollbar = self._scrollbar_drag
            scrollbar._pointer_move(point-scrollbar.position,pointer)
        else:
            super()._pointer_move(point,pointer)

    def _pointer_up(self, point, button=0, pointer=0):
        if self._scrollbar_drag is not None:
            scrollbar = self._scrollbar_drag
            scrollbar._pointer_up(point-scrollbar.position,button,pointer)
            self._scrollbar_drag = None
        else:
            super()._pointer_up(point,button,pointer)

    def _cancel_pointer(self):
        if self._scrollbar_drag is not None:
            self._scrollbar_drag._cancel_pointer()
            self._scrollbar_drag = None
        super()._cancel_pointer()

    def _wheel(self, delta):
        self._viewport()
        from sfml.window import Keyboard
        horizontal = Keyboard.is_key_pressed(Keyboard.L_SHIFT) or Keyboard.is_key_pressed(Keyboard.R_SHIFT)
        scrollbar = self.h_scrollbar if horizontal else self.v_scrollbar
        if scrollbar.visible:
            scrollbar.value -= delta*self.font_size*3
            return True
        return False

    def _render_scrollbars(self, target, states):
        self._viewport()
        for scrollbar in (self.v_scrollbar,self.h_scrollbar):
            if scrollbar.visible:
                transform = Transform()
                transform.combine(states.transform)
                transform.translate(scrollbar.position)
                scrollbar.render(target,RenderStates(transform=transform))
