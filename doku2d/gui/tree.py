"""A tree-shaped list with collapsible branches and keyboard navigation."""
from dataclasses import dataclass, field
from math import isfinite

from sfml.graphics import ConvexShape
from sfml.window import Event, Keyboard

from ..core import Signal
from .base import Control
from .theme import box, clipped, color, label


@dataclass(eq=False)
class TreeItem:
    text: object
    data: object = None
    expanded: bool = True
    _parent: object = field(default=None, init=False, repr=False)
    _children: list = field(default_factory=list, init=False, repr=False)

    @property
    def parent(self):
        return self._parent

    @property
    def children(self):
        return tuple(self._children)


class Tree(Control):
    item_selected = Signal()
    item_activated = Signal()
    item_expanded = Signal()

    def __init__(self, name=None, *, row_height=30):
        super().__init__(name)
        self.row_height = row_height
        self.size = (250, 200)
        self.focusable = True
        self._roots = []
        self._items = set()
        self._selected = None
        self._scroll = 0.0
        self._disclosure = ConvexShape(3)
        self._disclosure.set_point(0, (-4, -2.5))
        self._disclosure.set_point(1, (4, -2.5))
        self._disclosure.set_point(2, (0, 2.5))

    @property
    def row_height(self):
        return self._row_height

    @row_height.setter
    def row_height(self, value):
        if not isfinite(value) or value <= 0:
            raise ValueError('Tree row height must be positive and finite')
        self._row_height = float(value)

    @property
    def roots(self):
        return tuple(self._roots)

    @property
    def selected(self):
        return self._selected

    def add_item(self, text, *, parent=None, data=None, expanded=True):
        if parent is not None:
            self._require_item(parent)
        item = TreeItem(self._caption(text), data, expanded)
        item._parent = parent
        (self._roots if parent is None else parent._children).append(item)
        self._items.add(item)
        return item

    def _require_item(self, item):
        if not isinstance(item, TreeItem) or item not in self._items:
            raise ValueError('Item must belong to this Tree')

    def remove_item(self, item):
        self._require_item(item)
        parent = item.parent
        (self._roots if parent is None else parent._children).remove(item)
        pending = [item]
        while pending:
            node = pending.pop()
            pending.extend(node._children)
            self._items.remove(node)
        item._parent = None
        if self.selected not in self._items:
            self.select(parent)
        self._clamp_scroll(len(self._rows()))

    def clear(self):
        self._roots.clear()
        self._items.clear()
        self._scroll = 0
        self.select(None)

    def move_item(self, item, *, parent=None, index=None):
        """Move an item and its descendants. Index is measured after removal."""
        self._require_item(item)
        if parent is not None:
            self._require_item(parent)
        ancestor = parent
        while ancestor is not None:
            if ancestor is item:
                raise ValueError('Cannot move an item into its own branch')
            ancestor = ancestor.parent
        siblings = self._roots if item.parent is None else item.parent._children
        destination = self._roots if parent is None else parent._children
        length = len(destination)-(siblings is destination)
        if index is not None and (type(index) is not int or not 0 <= index <= length):
            raise IndexError('Tree destination index is outside the new branch')
        siblings.remove(item)
        destination.insert(length if index is None else index, item)
        item._parent = parent
        if self.selected is not None:
            self.select(self.selected)

    def _rows(self):
        pending = [(item, 0) for item in reversed(self._roots)]
        rows = []
        while pending:
            item, depth = pending.pop()
            rows.append((item, depth))
            if item.expanded:
                pending.extend((child, depth+1) for child in reversed(item._children))
        return rows

    def select(self, item):
        if item is not None:
            self._require_item(item)
            parent = item.parent
            while parent is not None:
                parent.expanded = True
                parent = parent.parent
            rows = self._rows()
            index = next(index for index, (node, _) in enumerate(rows) if node is item)
            self._scroll = min(self._scroll, index*self.row_height)
            self._scroll = max(self._scroll, (index+1)*self.row_height-self.size.y)
            self._clamp_scroll(len(rows))
        if item is not self._selected:
            self._selected = item
            self.item_selected.emit(item)

    def set_expanded(self, item, expanded):
        self._require_item(item)
        expanded = bool(expanded)
        if item.expanded != expanded and item.children:
            item.expanded = expanded
            rows = self._rows()
            if self.selected is not None and all(node is not self.selected for node, _ in rows):
                self.select(item)
            self._clamp_scroll(len(rows))
            self.item_expanded.emit(item, expanded)

    def _clamp_scroll(self, count):
        self._scroll = max(0, min(self._scroll, count*self.row_height-self.size.y))

    def _wheel(self, delta):
        self._scroll -= delta*self.row_height
        self._clamp_scroll(len(self._rows()))
        return True

    def _pointer_down(self, point, button=0, pointer=0):
        row = self._row_at(point)
        if button == 0 and row is not None:
            item, depth = row
            left = 8 + depth*18
            if item.children and left <= point.x < left+18:
                self.set_expanded(item, not item.expanded)
            else:
                self.select(item)
        return False

    def item_at(self, position):
        """Return the item at a local pointer position, or None."""
        row = self._row_at(self._vector(position))
        return row[0] if row is not None else None

    def _row_at(self, point):
        if not (0 <= point.x < self.size.x and 0 <= point.y < self.size.y):
            return None
        rows = self._rows()
        index = int((point.y + self._scroll)//self.row_height)
        return rows[index] if index < len(rows) else None

    def _key(self, event):
        key = event.code
        if key not in (Keyboard.UP, Keyboard.DOWN, Keyboard.LEFT, Keyboard.RIGHT,
                       Keyboard.HOME, Keyboard.END, Keyboard.RETURN):
            return False
        if event.type != Event.KEY_PRESSED:
            return True
        rows = self._rows()
        if not rows:
            return True
        index = next((i for i, (node, _) in enumerate(rows) if node is self.selected), -1)
        if index < 0 or key == Keyboard.HOME:
            self.select(rows[0][0])
        elif key == Keyboard.END:
            self.select(rows[-1][0])
        elif key in (Keyboard.UP, Keyboard.DOWN):
            offset = -1 if key == Keyboard.UP else 1
            self.select(rows[max(0, min(index+offset, len(rows)-1))][0])
        elif key == Keyboard.LEFT:
            item = self.selected
            if item.expanded and item.children:
                self.set_expanded(item, False)
            elif item.parent is not None:
                self.select(item.parent)
        elif key == Keyboard.RIGHT and self.selected.children:
            if self.selected.expanded:
                self.select(self.selected.children[0])
            else:
                self.set_expanded(self.selected, True)
        elif key == Keyboard.RETURN:
            self.item_activated.emit(self.selected)
        return True

    def render(self, target, states):
        theme = self.theme
        width, height = self.size
        box(target, states, (0, 0, width, height), theme.background, theme.border, radius=theme.radius)
        rows = self._rows()
        self._clamp_scroll(len(rows))
        with clipped(target, states, (2, 2, width-4, height-4)) as draw:
            if not draw:
                return
            for index in range(int(self._scroll//self.row_height), len(rows)):
                y = index*self.row_height-self._scroll
                if y >= height:
                    break
                item, depth = rows[index]
                if item is self.selected:
                    box(target, states, (4, y+2, width-8, self.row_height-4), theme.selection,
                        radius=theme.radius)
                x = 8+depth*18
                if item.children:
                    self._disclosure.position = (x+9, y+self.row_height/2)
                    self._disclosure.rotation = 0 if item.expanded else -90
                    self._disclosure.fill_color = color(theme.text)
                    target.draw(self._disclosure, states)
                label(target, states, self, item.text, (x+21, y, width-x-26, self.row_height))
