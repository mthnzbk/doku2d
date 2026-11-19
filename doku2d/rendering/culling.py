"""Conservative visibility tests in the active camera's coordinate system."""
from math import cos, hypot, radians, sin


def pose(entity):
    return (tuple(entity._position), entity._rotation, tuple(entity._scale))


def affine(pose):
    (x, y), rotation, (sx, sy) = pose
    if not rotation:
        return sx, 0, 0, sy, x, y
    angle = radians(rotation)
    c, s = cos(angle), sin(angle)
    return c*sx, -s*sy, s*sx, c*sy, x, y


def compose(outer, inner):
    a, b, c, d, x, y = outer
    e, f, g, h, u, v = inner
    return a*e+b*g, a*f+b*h, c*e+d*g, c*f+d*h, a*u+b*v+x, c*u+d*v+y


def transform_affine(transform):
    x, y = transform.transform_point((0, 0))
    u, v = transform.transform_point((64, 0))
    p, q = transform.transform_point((0, 64))
    return (u-x)/64, (p-x)/64, (v-y)/64, (q-y)/64, x, y


class ViewCuller:
    def __init__(self, view):
        x, y = view.center
        hw, hh = view.size / 2
        angle = view.rotation.radians
        c, s = cos(angle), sin(angle)
        self._camera = c, s, -s, c, -c*x-s*y, s*x-c*y
        self._plain = not angle
        # Keep boundary pixels despite floating-point and rasterization differences.
        pad = max(.01, max(abs(x), abs(y), hw, hh)*1e-6)
        self._half = hw + pad, hh + pad
        self._world = x-hw-pad, x+hw+pad, y-hh-pad, y+hh+pad

    def sprite(self, quad, position, group=None):
        (x0, y0), _, _, (x1, y1) = quad[0]
        if self._plain and group is None and not position[1]:
            (x, y), _, (sx, sy) = position
            left, right, top, bottom = self._world
            a, b, c, d = x+x0*sx, x+x1*sx, y+y0*sy, y+y1*sy
            return min(a, b) <= right and max(a, b) >= left and min(c, d) <= bottom and max(c, d) >= top
        matrix = affine(position)
        return self.rectangle(quad, compose(group, matrix) if group is not None else matrix)

    def rectangle(self, quad, matrix):
        (x0, y0), _, _, (x1, y1) = quad[0]
        return self.bounds((x0, y0, x1-x0, y1-y0), matrix)

    def bounds(self, rect, matrix):
        left, top, width, height = rect
        cx, cy = left+width/2, top+height/2
        rx, ry = abs(width)/2, abs(height)/2
        a, b, c, d, x, y = compose(self._camera, matrix)
        hw, hh = self._half
        return (abs(a*cx+b*cy+x) <= hw+abs(a)*rx+abs(b)*ry
                and abs(c*cx+d*cy+y) <= hh+abs(c)*rx+abs(d)*ry)

    def circles(self, transform=None):
        a, b, c, d, x, y = (compose(self._camera, transform_affine(transform))
                             if transform is not None else self._camera)
        sx, sy = hypot(a, b), hypot(c, d)
        hw, hh = self._half

        def visible(px, py, radius):
            return abs(a*px+b*py+x) <= hw+sx*radius and abs(c*px+d*py+y) <= hh+sy*radius

        return visible
