"""Per-canvas offscreen lighting. Visibility fans and extruded polygons cast shadows."""
from math import sin,cos,atan2,pi,hypot,ceil
from sfml.graphics import (Color,Image,Texture,RenderTexture,RenderStates,Shader,Sprite,
                           Vertex,VertexArray,PrimitiveType,ConvexShape,BLEND_ADD,BLEND_NONE)
from sfml.system import Vector2
from .light import PointLight,DirectionalLight,color

COMPOSITE=b'''
uniform sampler2D scene;
uniform sampler2D lights;
uniform vec4 ambient;
uniform float has_lights;
void main() {
    vec2 uv=gl_TexCoord[0].xy;
    vec4 base=texture2D(scene,uv);
    vec3 illumination=ambient.rgb;
    if (has_lights > 0.5) illumination += texture2D(lights,uv).rgb;
    vec3 albedo=base.a>0.000001?base.rgb/base.a:vec3(0.0);
    gl_FragColor=vec4(albedo*illumination,base.a*ambient.a);
}
'''


ENERGY=b'''
uniform sampler2D source;
uniform float energy;
void main() {
    vec4 sampleColor=texture2D(source,gl_TexCoord[0].xy)*gl_Color;
    gl_FragColor=vec4(sampleColor.rgb*sampleColor.a*energy,1.0);
}
'''

def cross(a,b):return a.x*b.y-a.y*b.x


def inside(point,polygon):
    result=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a.y>point.y)!=(b.y>point.y):
            if point.x<(b.x-a.x)*(point.y-a.y)/(b.y-a.y)+a.x:result=not result
    return result


def edges(points,closed):return list(zip(points,points[1:]+points[:1])) if closed else list(zip(points,points[1:]))


class LightingRenderer:
    def __init__(self,game):
        if not Shader.is_available():raise RuntimeError('Canvas lighting requires OpenGL shader support')
        self.game=game;self._size=None;self._scene=None;self._lights=None;self._scratch=None
        self._shader=Shader.from_memory(fragment=COMPOSITE)
        self._energy_shader=Shader.from_memory(fragment=ENERGY);self._gradients={}
    def _resize(self,size):
        size=tuple(map(int,size))
        if size!=self._size:
            self._size=size
            self._scene = RenderTexture(*size)
            self._lights = self._scratch = None
    def _gradient(self,falloff):
        key=round(falloff,4)
        if key not in self._gradients:
            size=128;image=Image.create(size,size,Color.BLACK)
            for y in range(size):
                for x in range(size):
                    distance=hypot((x+.5)/size*2-1,(y+.5)/size*2-1)
                    value=round(255*max(0,1-distance)**falloff)
                    image[x,y]=Color(value,value,value)
            texture=Texture.from_image(image);texture.smooth=True
            if len(self._gradients)>=8:self._gradients.pop(next(iter(self._gradients)))
            self._gradients[key]=texture
        return self._gradients[key]
    def _point(self,light,occluders):
        radius=light.radius*light.texture_scale
        center=light.offset;transform=light.transform;inverse=transform.inverse
        segments=[];angles=[i*2*pi/96 for i in range(96)]
        if light.shadow:
            for occluder in occluders:
                points=[inverse.transform_point(p) for p in occluder.world_points]
                if occluder.closed and inside(center,points):return
                left,right=min(p.x for p in points),max(p.x for p in points)
                top,bottom=min(p.y for p in points),max(p.y for p in points)
                dx=max(left-center.x,0,center.x-right);dy=max(top-center.y,0,center.y-bottom)
                if dx*dx+dy*dy>radius*radius:continue
                for point in points:
                    angle=atan2(point.y-center.y,point.x-center.x)
                    angles.extend(((angle-1e-5)%(2*pi),angle%(2*pi),(angle+1e-5)%(2*pi)))
                segments.extend(edges(points,occluder.closed))
        segments=[(a.x-center.x,a.y-center.y,b.x-a.x,b.y-a.y) for a,b in segments]
        points=[]
        for angle in sorted(set(angles)):
            dx,dy=cos(angle),sin(angle);distance=radius
            for ax,ay,ex,ey in segments:
                denominator=dx*ey-dy*ex
                if abs(denominator)<1e-10:continue
                ray=(ax*ey-ay*ex)/denominator;fraction=(ax*dy-ay*dx)/denominator
                if 0<=ray<distance and 0<=fraction<=1:distance=ray
            points.append(Vector2(center.x+dx*distance,center.y+dy*distance))
        if not points:return
        points.append(points[0]);texture=light.texture or self._gradient(light.falloff)
        width,height=texture.size
        mesh=VertexArray(PrimitiveType.TRIANGLES_FAN)
        mesh.append(Vertex(center,light.color,(width/2,height/2)))
        for point in points:
            uv=((point.x-center.x)/radius/2+.5,(point.y-center.y)/radius/2+.5)
            mesh.append(Vertex(point,light.color,(uv[0]*width,uv[1]*height)))
        self._energy_shader.set_uniform('source',texture)
        self._energy_shader.set_uniform('energy',light.energy)
        self._lights.draw(mesh,RenderStates(transform=transform,texture=texture,blend_mode=BLEND_ADD,shader=self._energy_shader))
    def _directional(self,light,occluders,view):
        scratch=self._scratch;scratch.view=view;scratch.clear(light.color)
        if light.shadow:
            extension=light.ray_direction*light.shadow_length
            for occluder in occluders:
                points=list(occluder.world_points)
                if occluder.closed:
                    from .tilecollision import convex_parts
                    polygons=convex_parts(points)
                else:polygons=[]
                polygons += [[a,b,b+extension,a+extension] for a,b in edges(points,occluder.closed)]
                for polygon in polygons:
                    # Triangles avoid requiring a concave polygon to be convex.
                    mesh=VertexArray(PrimitiveType.TRIANGLES_FAN)
                    for point in polygon:mesh.append(Vertex(point,Color.BLACK))
                    scratch.draw(mesh,RenderStates(blend_mode=BLEND_NONE))
        scratch.display()
        previous=self._lights.view;self._lights.view=self._lights.default_view
        sprite=Sprite(scratch.texture)
        self._energy_shader.set_uniform('source',scratch.texture)
        self._energy_shader.set_uniform('energy',light.energy)
        self._lights.draw(sprite,RenderStates(blend_mode=BLEND_ADD,shader=self._energy_shader))
        self._lights.view=previous
    def render(self,target,canvas,objects,draw_objects):
        self._resize(target.size)
        view=self.game.make_view(canvas)
        scene = self._scene
        scene.reset_GL_states();scene.view=view;scene.clear(Color.TRANSPARENT)
        draw_objects(scene,objects,canvas)
        scene.display()
        ambient=color(canvas.ambient)
        for obj in objects:
            if getattr(obj,'_is_canvas_modulate',False) and obj.enabled:
                tint=color(obj.color)
                ambient=Color(round(ambient.r*tint.r/255),round(ambient.g*tint.g/255),round(ambient.b*tint.b/255),round(ambient.a*tint.a/255))
        active = [obj for obj in objects if getattr(obj, '_is_light', False)
                  and obj.enabled and obj.energy > 0 and obj.light_mask & canvas.light_mask
                  and (obj.target is None or obj.target.game is self.game)]
        if active:
            if self._lights is None:
                self._lights = RenderTexture(*self._size)
            lights = self._lights
            lights.reset_GL_states();lights.view=view;lights.clear(Color.BLACK)
            occluders = [obj for obj in objects if getattr(obj, '_is_occluder', False) and obj.enabled
                         and (obj.target is None or obj.target.game is self.game)]
            for light in active:
                blockers = [obj for obj in occluders if obj.light_mask & light.light_mask] if light.shadow else ()
                if isinstance(light, PointLight):
                    self._point(light, blockers)
                elif isinstance(light, DirectionalLight):
                    if self._scratch is None:
                        self._scratch = RenderTexture(*self._size)
                    self._scratch.reset_GL_states()
                    self._directional(light, blockers, view)
            lights.display()
        self._shader.set_uniform('scene',scene.texture)
        # Bind a valid texture even when the shader skips the light sampler.
        self._shader.set_uniform('lights', self._lights.texture if active else scene.texture)
        self._shader.set_uniform('has_lights', 1.0 if active else 0.0)
        self._shader.set_uniform('ambient',ambient)
        old_view=target.view;target.reset_GL_states();target.view=self.game._pixel_view(target.size)
        try:target.draw(Sprite(scene.texture),RenderStates(shader=self._shader))
        finally:target.view=old_view
