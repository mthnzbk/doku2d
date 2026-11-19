"""User GLSL materials and the offscreen passes used by Canvas effects."""
from pathlib import Path
from types import MappingProxyType

from sfml.graphics import BLEND_NONE, Color, RenderStates, Shader, Sprite


class ShaderMaterial:
    """A GLSL shader with its own parameters, compiled when first drawn."""

    def __init__(self, fragment, *, vertex=None, texture_uniform='u_texture'):
        if fragment is None:
            raise ValueError('A fragment shader is required')
        if texture_uniform is not None and (not isinstance(texture_uniform, str) or not texture_uniform):
            raise ValueError('Texture uniform must be a nonempty string or None')
        self._fragment = fragment
        self._vertex = vertex
        self._texture_uniform = texture_uniform
        self._source = False
        self._parameters = {}
        self._compiled = {}

    @classmethod
    def from_file(cls, fragment, **options):
        return cls(fragment, **options)

    @classmethod
    def from_source(cls, fragment, **options):
        material = cls(fragment, **options)
        material._source = True
        return material

    @property
    def parameters(self):
        return MappingProxyType(self._parameters)

    def set_shader_parameter(self, name, value):
        if not isinstance(name, str) or not name:
            raise ValueError('Shader parameter name must be a nonempty string')
        if name == self._texture_uniform:
            raise ValueError('The current texture sampler is managed by the material')
        for shader in self._compiled.values():
            shader.set_uniform(name, value)
        self._parameters[name] = value
        return self

    def get_shader_parameter(self, name):
        return self._parameters[name]

    def _resolve(self, resources):
        key = None if self._source or resources is None else resources.root
        shader = self._compiled.get(key)
        if shader is not None:
            return shader

        def stage(value):
            if value is None:
                return None
            if self._source:
                return value.encode('utf-8') if isinstance(value, str) else value
            return str(resources.resolve(value) if resources is not None else Path(value).resolve())

        vertex, fragment = stage(self._vertex), stage(self._fragment)
        if not Shader.is_available():
            raise RuntimeError('ShaderMaterial requires OpenGL shader support')
        loader = Shader.from_memory if self._source else Shader.from_file
        shader = loader(fragment=fragment) if vertex is None else loader(vertex=vertex, fragment=fragment)
        if self._texture_uniform is not None:
            shader.set_currenttexturetype_parameter(self._texture_uniform)
        for name, value in self._parameters.items():
            shader.set_uniform(name, value)
        self._compiled[key] = shader
        return shader


def checked_material(value):
    if value is not None and not isinstance(value, ShaderMaterial):
        raise TypeError('material must be a ShaderMaterial or None')
    return value


_STRAIGHT = b'''
    uniform sampler2D source;
    void main() {
        vec4 p = texture2D(source, gl_TexCoord[0].xy);
        gl_FragColor = p.a > 0.0 ? vec4(p.rgb / p.a, p.a) : vec4(0.0);
    }
'''


def draw_effect(game, target, texture, shader, **states):
    previous = target.view
    target.reset_GL_states()
    target.view = game._pixel_view(target.size)
    try:
        target.draw(Sprite(texture), RenderStates(shader=shader, **states))
    finally:
        target.view = previous


class CanvasEffect:
    def __init__(self, game):
        self._game = game
        self._capture = self._straight = None
        self._normalize = None

    def render(self, target, material, draw):
        shader = material._resolve(self._game.resources)
        if self._normalize is None:
            self._normalize = Shader.from_memory(fragment=_STRAIGHT)
        if self._capture is None or tuple(self._capture.size) != tuple(target.size):
            self._capture = self._game.create_render_texture(target.size)
            self._straight = self._game.create_render_texture(target.size)
        capture, straight = self._capture, self._straight
        capture.reset_GL_states()
        capture.clear(Color.TRANSPARENT)
        draw(capture)
        capture.display()
        self._normalize.set_uniform('source', capture.texture)
        draw_effect(self._game, straight, capture.texture, self._normalize, blend_mode=BLEND_NONE)
        straight.display()
        draw_effect(self._game, target, straight.texture, shader)


__all__ = ['ShaderMaterial']
