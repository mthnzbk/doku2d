"""Draw adjacent compatible sprites without reordering translucent objects."""
from sfml.graphics import Color, PrimitiveType, RenderStates, Vertex, VertexArray

from ..core.entity import Entity
from .culling import affine, pose


def supports_pose(entity):
    cls = type(entity)
    return (cls.transform is Entity.transform and cls.position is Entity.position
            and cls.rotation is Entity.rotation and cls.scale is Entity.scale)


def sprite_source(entity):
    source = getattr(entity, '_batch_sprite', None)
    if source is None or entity.material is not None or not supports_pose(entity):
        return None
    sprite = source()
    return sprite if sprite is not None and sprite.texture is not None else None


def _corners(positions, pose, group):
    a, b, c, d, x, y = affine(pose)
    corners = [(a*px+b*py+x, c*px+d*py+y) for px, py in positions]
    if group is not None:
        a, b, c, d, x, y = group
        corners = [(a*px+b*py+x, c*px+d*py+y) for px, py in corners]
    return corners


class SpriteBatch:
    def __init__(self):
        self._cache = {}
        self._sprites = []

    def begin(self, target, view, owner):
        self._target, self._view = target, view
        self._group_pose = pose(owner) if getattr(owner, '_is_canvas_group', False) else None
        self._texture = None
        self._index = 0

    def add(self, entity, sprite, position, quad):
        if sprite.texture is not self._texture:
            self.flush()
            self._texture = sprite.texture
        self._sprites.append((entity, position, quad))

    def flush(self):
        if not self._sprites:
            return
        target = self._target
        target.view = self._view
        if len(self._sprites) == 1:
            entity = self._sprites[0][0]
            entity.render(target, RenderStates(transform=entity.transform))
        else:
            sprites = [(position, quad) for _, position, quad in self._sprites]
            signature = (self._texture, self._group_pose, sprites)
            entry = self._cache.get(self._index)
            if entry is None or entry[0] != signature:
                previous = None
                if entry is not None and len(entry[0][2]) == len(sprites):
                    mesh = entry[1]
                    if entry[0][1] == self._group_pose:
                        previous = entry[0][2]
                else:
                    mesh = VertexArray(PrimitiveType.TRIANGLES, 6*len(sprites))
                tint = Color.WHITE
                group = affine(self._group_pose) if self._group_pose is not None else None
                for index, (pose, quad) in enumerate(sprites):
                    if previous is not None and previous[index] == sprites[index]:
                        continue
                    positions, uv = quad
                    corners = _corners(positions, pose, group)
                    vertices = [Vertex(point, tint, coords) for point, coords in zip(corners, uv)]
                    for offset, corner in enumerate((0, 1, 2, 2, 1, 3)):
                        mesh[6*index + offset] = vertices[corner]
                entry = self._cache[self._index] = (signature, mesh)
            target.draw(entry[1], RenderStates(texture=self._texture))
            self._index += 1
        self._sprites.clear()

    def end(self):
        self._sprites.clear()
        self._target = self._view = self._texture = None
        for index in range(self._index, len(self._cache)):
            del self._cache[index]
