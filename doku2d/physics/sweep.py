"""Continuous circle and box queries against the physics world's native shapes."""
from math import cos, isfinite, radians, sin

import pymunk
from pymunk import Vec2d

from .shapes import Box, Circle


def checked_shape(shape):
    if not isinstance(shape, (Circle, Box)):
        raise TypeError('ShapeCast requires a Circle or Box')
    return shape


def box_offsets(shape, rotation):
    angle = radians(rotation)
    right = Vec2d(cos(angle), sin(angle)) * (shape.size[0] / 2)
    down = Vec2d(-sin(angle), cos(angle)) * (shape.size[1] / 2)
    return (-right - down, right - down, right + down, -right + down)


def native_vertices(shape):
    if isinstance(shape, pymunk.Poly):
        points = shape.get_vertices()
    elif isinstance(shape, pymunk.Circle):
        points = (shape.offset,)
    else:
        points = (shape.a, shape.b)
    return tuple(shape.body.local_to_world(point) for point in points)


def support(points, normal, tangent):
    # Parallel faces need an interval so the reported hit lies on both shapes
    # even when the contact normal gives several equally far vertices.
    depths = [point.dot(normal) for point in points]
    depth = max(depths)
    edge = [point.dot(tangent) for point, projection in zip(points, depths)
            if depth - projection <= 1e-7]
    return depth, min(edge), max(edge)


def box_hit(obstacle, offsets, start, end, scratch):
    vertices = native_vertices(obstacle)
    # Expand the obstacle by the reflected box, then cast its center against
    # that convex hull. Pymunk also retains any rounded obstacle edges.
    hull = pymunk.Poly(scratch, [vertex - offset for vertex in vertices for offset in offsets],
                      radius=obstacle.radius)
    hull.cache_bb()
    hit = sweep_point(hull, start, end, 0)
    if hit is None:
        return None
    fraction, normal, _ = hit
    center = start + (end - start) * fraction
    tangent = Vec2d(-normal.y, normal.x)
    depth, low, high = support(vertices, normal, tangent)
    _, box_low, box_high = support(offsets, -normal, tangent)
    along = center.dot(tangent)
    position = (max(low, along + box_low) + min(high, along + box_high)) / 2
    position = min(high, max(low, position))
    point = normal * (depth + obstacle.radius) + tangent * position
    return fraction, normal, point


def sweep_point(obstacle, start, end, radius):
    initial = obstacle.point_query(start)
    if initial.distance <= radius:
        normal = initial.gradient
        # A circle queried at its exact center has no unique normal.
        if not normal.length:
            normal = (start - end).normalized() if start != end else Vec2d(1, 0)
        return 0.0, normal, start - normal * initial.distance
    if start != end:
        hit = obstacle.segment_query(start, end, radius)
        if hit is not None:
            return hit.alpha, hit.normal, hit.point
    return None


def swept_hits(space, shape, start, end, rotation, mask):
    shape = checked_shape(shape)
    start, end = Vec2d(*start), Vec2d(*end)
    if not all(map(isfinite, (*start, *end, rotation))):
        raise ValueError('Shape cast coordinates and rotation must be finite')
    if isinstance(shape, Circle):
        x_radius = y_radius = shape.radius
        offsets = scratch = None
    else:
        offsets = box_offsets(shape, rotation)
        x_radius = max(abs(point.x) for point in offsets)
        y_radius = max(abs(point.y) for point in offsets)
        scratch = pymunk.Body(body_type=pymunk.Body.STATIC)
    bounds = pymunk.BB(min(start.x, end.x) - x_radius, min(start.y, end.y) - y_radius,
                      max(start.x, end.x) + x_radius, max(start.y, end.y) + y_radius)
    length = (end - start).length
    for obstacle in space.bb_query(bounds, pymunk.ShapeFilter(mask=mask)):
        if offsets is None:
            hit = sweep_point(obstacle, start, end, shape.radius)
        else:
            hit = box_hit(obstacle, offsets, start, end, scratch)
        if hit is not None:
            fraction, normal, point = hit
            yield obstacle, fraction, normal, point, fraction * length
