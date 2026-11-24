"""Clickable map of a dialogue file's sections and links."""
from collections import defaultdict

from sfml.graphics import PrimitiveType, Vertex, VertexArray

from ..core import Signal
from ..gui import Control
from ..gui.theme import box, clipped, color, label
from .analysis import depths, routes


class DialogueGraph(Control):
    section_selected = Signal()

    def __init__(self):
        super().__init__()
        self.tree = None
        self._nodes = {}
        self._edges = ()
        self._offset = 0
        self._columns = 1
        self._rows = 1

    def set_tree(self, tree, entry=None):
        self.tree = tree
        by_depth = depths(tree, entry or tree.start)
        disconnected = max(by_depth.values())+1
        rows = defaultdict(int)
        self._nodes = {}
        for name in tree.sections:
            depth = by_depth.get(name, disconnected)
            self._nodes[name] = depth, rows[depth]
            rows[depth] += 1
        self._edges = tuple((name, target or 'END', caption) for name, section in tree.sections.items()
                            for target, caption in routes(section, include_end=True))
        if any(target == 'END' for _, target, _ in self._edges):
            self._nodes['END'] = max(rows)+1, 0
        self._columns = 1+max(depth for depth, _ in self._nodes.values())
        self._rows = max(rows.values())
        self._offset = 0

    def _rect(self, name):
        column, row = self._nodes[name]
        width = min(260, max(136, (self.size.x-28)/self._columns))
        count = max(1, int((self.size.x-28)/width))
        x = 14 + (column % count)*width
        band = 68+62*self._rows
        return x, 20+row*62+(column//count)*band-self._offset, width-34, 34

    def _wheel(self, delta):
        bottom = max((self._rect(name)[1]+self._offset+55 for name in self._nodes), default=0)
        self._offset = min(max(0, bottom-self.size.y), max(0, self._offset-40*delta))
        return True

    def _pointer_down(self, point, button=0, pointer=0):
        if button == 0:
            for name in self._nodes:
                x, y, w, h = self._rect(name)
                if name != 'END' and x <= point.x < x+w and y <= point.y < y+h:
                    self.section_selected.emit(name)
                    break
        return False

    def render(self, target, states):
        bounds = (0, 0, *self.size)
        box(target, states, bounds, self.theme.background, self.theme.border, radius=self.theme.radius)
        with clipped(target, states, bounds) as draw:
            if not draw:
                return
            rectangles = {name: self._rect(name) for name in self._nodes}
            for source, destination, caption in self._edges:
                x, y, w, h = rectangles[source]
                dx, dy, dw, dh = rectangles[destination]
                if x+w < dx:
                    start, end = (x+w, y+h/2), (dx, dy+dh/2)
                    elbow = (start[0]+end[0])/2
                    points = (start, (elbow, start[1]), (elbow, end[1]), end,
                              (end[0]-5,end[1]-4), end, (end[0]-5,end[1]+4))
                else:
                    start, end = (x+w, y+h/2), (dx+dw, dy+dh/2)
                    elbow = max(start[0],end[0])+12
                    yy = end[1] if start[1] != end[1] else end[1]+10
                    end = end[0], yy
                    points = (start, (elbow,start[1]), (elbow,yy), end, (end[0]+5,yy-4), end, (end[0]+5,yy+4))
                mesh = VertexArray(PrimitiveType.LINES_STRIP)
                for point in points:
                    mesh.append(Vertex(point, color(self.theme.accent)))
                target.draw(mesh, states)
                if caption:
                    label(target, states, self, caption, (min(start[0],end[0])+4, (start[1]+end[1])/2+6, 180, 19),
                          tint=self.theme.muted)
            for name, rect in rectangles.items():
                x, y, w, h = rect
                box(target, states, rect, self.theme.surface, self.theme.border, radius=self.theme.radius)
                if name != 'END' and self.tree.sections[name].call:
                    name = f'{name} ↗ {self.tree.sections[name].call.entry}'
                with clipped(target, states, rect) as visible:
                    if visible:
                        label(target, states, self, name, (x+6,y,w-12,h))
