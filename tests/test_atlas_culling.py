import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sfml.graphics import Color, Image, Texture

from doku2d import AnimatedSprite, Camera, Game, Particles, Sprite, SpriteAtlas, TextureButton


def snapshot(game):
    target = game.create_render_texture()
    target.clear(Color.BLACK)
    game.render(target)
    target.display()
    return target.texture.to_image(), game.debug.draw_calls


class AtlasCullingTests(TestCase):
    def test_shared_atlas_batches_sprites_and_keeps_ui_icon_crop(self):
        game = Game(size=(64, 40), debug=True)
        self.addCleanup(game.close)
        red, green = Image.create(6, 8, Color.RED), Image.create(12, 10, Color.GREEN)
        first = game.add(Sprite(Texture.from_image(red)))
        second = game.add(Sprite(Texture.from_image(green)))
        first.position, second.position = (12, 12), (27, 12)
        reference, separate_calls = snapshot(game)

        atlas = SpriteAtlas.pack({'red': red, 'green': green})
        first.texture, second.texture = atlas['red'], atlas['green']
        batched, atlas_calls = snapshot(game)
        self.assertIs(first.texture, second.texture)
        self.assertEqual(bytes(reference.pixels), bytes(batched.pixels))
        self.assertEqual((separate_calls, atlas_calls), (2, 1))

        game.remove(second)
        actor = game.add(AnimatedSprite())
        actor.position = (27, 12)
        actor.add_animation('colors', (atlas['red'], atlas['green']))
        actor.frame = 1
        button = game.add(TextureButton())
        button.size, button.position = (12, 10), (42, 8)
        button.texture_normal = atlas['green']
        result, calls = snapshot(game)
        self.assertEqual(result[27, 12], Color.GREEN)
        self.assertEqual(result[48, 13], Color.GREEN)
        self.assertIs(actor.texture, first.texture)
        self.assertEqual(calls, 2)
        actor.frame = 0
        result, _ = snapshot(game)
        self.assertEqual(result[27, 12], Color.RED)

        sheet = Texture.from_image(Image.create(6, 8, Color.BLUE))
        actor.texture = sheet
        actor.add_animation('sheet', (0,))
        actor.play('sheet')
        result, _ = snapshot(game)
        self.assertEqual(result[27, 12], Color.BLUE)
        actor.play('colors')
        self.assertIs(actor.texture, atlas.texture)

    def test_atlas_json_uses_cached_texture_and_checks_bounds(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            folder = root / 'art'
            folder.mkdir()
            Image.create(8, 8, Color.WHITE).to_file(str(folder/'atlas.png'))
            path = folder/'atlas.json'
            path.write_text(json.dumps({'meta': {'image': 'atlas.png'}, 'frames': [
                {'filename': 'icon', 'frame': {'x': 2, 'y': 1, 'w': 3, 'h': 4}},
            ]}), encoding='utf-8')
            game = Game(asset_root=root)
            try:
                atlas = game.resources.load_atlas('res://art/atlas.json')
                self.assertIs(atlas, game.resources.load_atlas(path))
                self.assertIs(atlas.texture, game.resources.get_texture('art/atlas.png'))
                self.assertEqual(atlas['icon'].rect, (2, 1, 3, 4))
                with self.assertRaises(ValueError):
                    SpriteAtlas(atlas.texture, {'outside': (7, 1, 3, 4)})
                game.resources.unload('art/atlas.png')
                self.assertIsNot(atlas.texture, game.resources.load_atlas(path).texture)
            finally:
                game.close()

    def test_rotated_camera_culls_offscreen_sprites_but_keeps_edge_pixels(self):
        game = Game(size=(64, 48), debug=True)
        self.addCleanup(game.close)
        game.batching = False
        camera = game.add(Camera())
        camera.position, camera.rotation, camera.zoom = (120, 90), 37, (1.5, 1.5)
        camera.reset_smoothing()
        texture = Texture.from_image(Image.create(8, 8, Color.WHITE))
        edge = game.add(Sprite(texture))
        edge.position = game.screen_to_world((-1, 20))
        edge.rotation = 26
        far = game.add(Sprite(texture))
        far.position = game.screen_to_world((140, 120))
        game.culling = False
        reference, full_calls = snapshot(game)
        game.culling = True
        culled, visible_calls = snapshot(game)
        self.assertEqual(bytes(reference.pixels), bytes(culled.pixels))
        self.assertNotEqual(culled[0, 20], Color.BLACK)
        self.assertEqual((full_calls, visible_calls), (2, 1))

    def test_particle_culling_uses_world_and_local_coordinates(self):
        game = Game(size=(70, 42), debug=True)
        self.addCleanup(game.close)
        game.batching = False
        world = game.add(Particles(position=(180, 70), amount=8, emitting=False, seed=3))
        world.burst(4)
        world.position = (30, 18)
        world.burst(4)
        local = game.add(Particles(position=(180, 70), amount=4, emitting=False, seed=3))
        local.local_coords = True
        local.rotation, local.scale = 42, (2, 3)
        local.burst(4)
        game.culling = False
        first, full_calls = snapshot(game)
        game.culling = True
        culled, visible_calls = snapshot(game)
        self.assertEqual(bytes(culled.pixels), bytes(first.pixels))
        self.assertEqual((full_calls, visible_calls), (12, 4))
        self.assertEqual((world.alive_count, local.alive_count), (8, 4))

        local.position = (40, 30)
        _, calls = snapshot(game)
        self.assertEqual(calls, 8)
