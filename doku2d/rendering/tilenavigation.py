"""Project authored TileMap obstacles onto a bounded movement grid."""
from functools import cache
from math import ceil, floor

from ..core.entity import Entity
from ..physics.navigation import grid_path
from .tilecollision import geometry, properties


def find_path(tilemap, start, goal, *, diagonal, blocked_layers, bounds, blocked,
              radius, physics, agent, ignored):
    tw, th = tilemap.tile_size
    if bounds is None:
        x, y, width, height = tilemap.bounds
        if width <= 0 or height <= 0:
            return []
        left, top = floor(x/tw), floor(y/th)
        right, bottom = ceil((x+width)/tw), ceil((y+height)/th)
    else:
        left, top, width, height = bounds
        right, bottom = left+width, top+height

    def in_bounds(point):
        return left <= point[0] < right and top <= point[1] < bottom

    if not in_bounds(start) or not in_bounds(goal):
        return []
    explicit = blocked_layers is not None
    layers = tilemap.layers
    if explicit:
        names = (blocked_layers,) if isinstance(blocked_layers, str) else tuple(blocked_layers)
        layers = {name: layers[name] for name in names}

    obstacles = set(blocked)
    aligned_layers = []
    tilesets = tilemap.tilesets

    @cache
    def solid_tile(cell):
        tile = tilesets[cell.tileset].tiles.get(cell.tile_id, {})
        flags = properties(tile)
        if flags.get('collision_enabled', True) is False:
            return False
        shapes = tile.get('objectgroup', {}).get('objects', ())
        return bool(flags.get('solid', False) or any(
            properties(shape).get('collision_enabled', True) and geometry(shape) for shape in shapes))

    def mark(points, transform):
        points = [transform.transform_point(point) for point in points]
        # Reserve every grid cell touched by the obstacle's bounds.
        x0 = floor(min(p.x for p in points)/tw + 1e-7)
        y0 = floor(min(p.y for p in points)/th + 1e-7)
        x1 = max(x0+1, ceil(max(p.x for p in points)/tw - 1e-7))
        y1 = max(y0+1, ceil(max(p.y for p in points)/th - 1e-7))
        obstacles.update((x, y) for y in range(max(top, y0), min(bottom, y1))
                         for x in range(max(left, x0), min(right, x1)))

    for layer in layers.values():
        flags = layer.properties
        if not explicit and flags.get('collision_enabled', flags.get('collision', True)) is False:
            continue
        all_tiles = explicit or flags.get('collision_mode') == 'solid'
        transform = Entity.transform.fget(layer)
        dx, dy = layer.position.x/tw, layer.position.y/th
        aligned = (layer.rotation % 360 == 0 and tuple(layer.scale) == (1, 1)
                   and dx.is_integer() and dy.is_integer())
        if layer.cells:
            if aligned:
                aligned_layers.append((layer.cells, int(dx), int(dy), all_tiles))
            else:
                for (x, y), cell in layer.cells.items():
                    if all_tiles or solid_tile(cell):
                        x0, y0 = x*tw, y*th
                        mark(((x0, y0), (x0+tw, y0), (x0+tw, y0+th), (x0, y0+th)), transform)

        if explicit or layer.collision_enabled or flags.get('collision_enabled', flags.get('collision', False)):
            for obj in layer.objects:
                if obj.properties.get('collision_enabled', True) is False:
                    continue
                for _, points in _object_geometry(layer, obj, tilesets):
                    mark(points, transform)

    @cache
    def occupied(point):
        if point in obstacles:
            return True
        x, y = point
        for cells, dx, dy, all_tiles in aligned_layers:
            cell = cells.get((x - dx, y - dy))
            if cell is not None and (all_tiles or solid_tile(cell)):
                return True
        return False

    # The transform's rotation preserves a circle, while its scale turns the
    # world radius into separate horizontal and vertical map clearances.
    sx, sy = map(abs, tilemap.scale)
    if radius and (sx == 0 or sy == 0):
        return []
    rx, ry = (radius/sx, radius/sy) if radius else (0, 0)

    @cache
    def world_center(point):
        return tilemap.map_to_world(point)

    def clear_between(first, second):
        if radius:
            a = ((first[0]+.5)*tw, (first[1]+.5)*th)
            b = ((second[0]+.5)*tw, (second[1]+.5)*th)
            # Exact contact fits; the epsilon avoids rejecting it after a transform.
            px, py = max(0, rx-1e-6), max(0, ry-1e-6)
            x0, x1 = floor((min(a[0], b[0])-px)/tw), floor((max(a[0], b[0])+px)/tw)
            y0, y1 = floor((min(a[1], b[1])-py)/th), floor((max(a[1], b[1])+py)/th)
            if x0 < left or x1 >= right or y0 < top or y1 >= bottom:
                return False
            for y in range(y0, y1+1):
                for x in range(x0, x1+1):
                    if occupied((x, y)) and _intersects_rect(a, b, (x*tw-px, y*th-py),
                                                           ((x+1)*tw+px, (y+1)*th+py)):
                        return False
        return physics is None or physics._navigation_clear(
            world_center(first), world_center(second), radius, agent=agent, ignored=ignored, tilemap=tilemap)

    @cache
    def walkable(point):
        return in_bounds(point) and not occupied(point) and (not extra_clearance or clear_between(point, point))

    extra_clearance = bool(radius or physics is not None)
    return grid_path(start, goal, walkable, diagonal=diagonal,
                     can_cross=clear_between if extra_clearance else None)


def _intersects_rect(start, end, low, high):
    """Clip a segment against the two axis intervals of a rectangle."""
    enter, leave = 0.0, 1.0
    for a, b, minimum, maximum in zip(start, end, low, high):
        delta = b-a
        if delta == 0:
            if not minimum <= a <= maximum:
                return False
            continue
        t1, t2 = (minimum-a)/delta, (maximum-a)/delta
        enter, leave = max(enter, min(t1, t2)), min(leave, max(t1, t2))
        if enter > leave:
            return False
    return True


def _object_geometry(layer, obj, tilesets):
    x = obj.position[0] - layer.position.x
    y = obj.position[1] - layer.position.y
    w, h = obj.size
    raw = {'x': x, 'y': y, 'width': w, 'height': h, 'rotation': obj.rotation}
    if obj.tile is not None:
        tw, th = tilesets[obj.tile.tileset].tile_size
        w, h = w or tw, h or th
        raw['polygon'] = [{'x': 0, 'y': -h}, {'x': w, 'y': -h}, {'x': w, 'y': 0}, {'x': 0, 'y': 0}]
    elif obj.shape in ('polygon', 'polyline'):
        raw[obj.shape] = [{'x': px, 'y': py} for px, py in obj.points]
    elif obj.shape in ('point', 'ellipse', 'text'):
        raw[obj.shape] = True
    return geometry(raw)
