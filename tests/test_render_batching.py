from unittest import TestCase

from sfml.graphics import Color, Image, RectangleShape, Texture

from doku2d import AmbientLight, AnimatedSprite, CanvasGroup, Entity, Game, Particles, ShaderMaterial, Sprite


def texture(color, size=(8, 8)):
    return Texture.from_image(Image.create(*size, color))


def snapshot(game, size=None):
    target = game.create_render_texture(size)
    target.clear(Color.BLACK)
    game.render(target)
    target.display()
    return target.texture.to_image(), game.debug.draw_calls


class RenderBatchingTests(TestCase):
    def test_sprite_runs_preserve_order_and_leave_custom_material_separate(self):
        game = Game(size=(32, 24), debug=True)
        self.addCleanup(game.close)
        red = texture(Color(255, 10, 10, 150))
        blue = texture(Color(5, 20, 255, 150))
        for index, image in enumerate((red, red, blue, red, red, red, red)):
            sprite = game.add(Sprite(image))
            sprite.position = (10 + index, 12)
            if index == 5:
                sprite.material = ShaderMaterial.from_source(
                    'void main() { gl_FragColor = vec4(0.9, 0.8, 0.1, 0.6); }',
                    texture_uniform=None)
        game.batching = False
        original, original_calls = snapshot(game)
        game.batching = True
        batched, batched_calls = snapshot(game)
        self.assertEqual(bytes(original.pixels), bytes(batched.pixels))
        self.assertEqual((original_calls, batched_calls), (7, 5))

    def test_animated_sprite_frames_and_group_transform_refresh_mesh(self):
        game = Game(size=(40, 32), debug=True)
        self.addCleanup(game.close)
        image = Image.create(8, 4, Color.RED)
        for y in range(4):
            for x in range(4, 8):
                image[x, y] = Color.GREEN
        atlas = Texture.from_image(image)
        group = game.add(CanvasGroup())
        group.position = (10, 8)
        group.rotation = 90
        actor = group.add(AnimatedSprite(atlas, frame_size=(4, 4)))
        actor.add_animation('blink', (0, 1))
        actor.play('blink')
        hint = group.add(Sprite(atlas))
        hint.region = True
        hint.region_rect = (0, 0, 4, 4)
        hint.position = (8, 0)
        hint.flip_h = True

        before, calls = snapshot(game)
        self.assertEqual(calls, 2)  # One batch plus the group composite.
        self.assertEqual(before[10, 8], Color.RED)
        actor.frame = 1
        after, calls = snapshot(game)
        self.assertEqual(after[10, 8], Color.GREEN)
        self.assertEqual(after[10, 16], Color.RED)
        self.assertEqual(calls, 2)
        group.position = (18, 12)
        game.batching = False
        reference, _ = snapshot(game)
        game.batching = True
        moved, _ = snapshot(game)
        self.assertEqual(bytes(reference.pixels), bytes(moved.pixels))

    def test_particles_batch_in_alpha_and_additive_modes(self):
        game = Game(size=(32, 32), debug=True)
        self.addCleanup(game.close)
        emitter = game.add(Particles(position=(16, 16), amount=12, emitting=False, seed=2))
        emitter.scale_range = (4, 4)
        emitter.color = (60, 100, 140, 110)
        emitter.burst(12)
        for mode, tex in (('alpha', None), ('add', texture(Color.WHITE, (6, 10)))):
            with self.subTest(mode=mode):
                emitter.blend_mode = mode
                emitter.texture = tex
                game.batching = False
                reference, native_calls = snapshot(game)
                game.batching = True
                batched, batched_calls = snapshot(game)
                self.assertEqual((native_calls, batched_calls), (12, 1))
                self.assertEqual(batched[16, 16], reference[16, 16])
                self.assertEqual(batched[0, 0], Color.BLACK)

    def test_draw_count_includes_offscreen_passes_and_custom_draws(self):
        game = Game(size=(40, 32), debug=True)
        self.addCleanup(game.close)
        game.debug.visible = True
        group = game.add(CanvasGroup())
        shared = texture(Color.WHITE)
        group.add(Sprite(shared))
        group.add(Sprite(shared))
        game.add(AmbientLight(color=(128, 128, 128)))
        game.world.material = ShaderMaterial.from_source('''
            uniform sampler2D u_texture;
            void main() { gl_FragColor = texture2D(u_texture, gl_TexCoord[0].xy); }
        ''')

        class CustomShape(Entity):
            def render(self, target, states):
                target.draw(RectangleShape((4, 4)), states)

        game.add(CustomShape(), canvas=game.ui.canvas)
        _, calls = snapshot(game, (80, 64))
        self.assertEqual(calls, 7)  # Batch, group, light, two canvas passes, HUD, presentation.
        game.debug.enabled = False
        _, calls = snapshot(game, (80, 64))
        self.assertEqual(calls, 0)
