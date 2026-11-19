import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from doku2d import AnimatableBody, CharacterBody, Game, StaticBody, TileMap


class OneWayPlatformTests(TestCase):
    def setup_world(self, platform_type=StaticBody):
        game = Game()
        self.addCleanup(game.close)
        game.physics.gravity = (0, 700)
        platform = game.add(platform_type(position=(60, 70), size=(100, 8), one_way=True))
        game.add(StaticBody(position=(60, 160), size=(100, 12)))
        return game, platform

    @staticmethod
    def step(game, steps):
        for _ in range(steps):
            game.update(1/60)

    def test_jump_through_land_and_drop_onto_regular_ground(self):
        game, platform = self.setup_world()
        actor = game.add(CharacterBody(position=(60, 112), radius=6, motion_mode='grounded'))
        actor.velocity = (0, -335)
        self.step(game, 24)
        self.assertLess(actor.position.y, 45)
        self.assertFalse(actor.is_on_floor())
        self.step(game, 75)
        self.assertIs(actor._floor_hit.collider, platform)
        self.assertTrue(actor.drop_through())
        self.step(game, 52)
        self.assertAlmostEqual(actor.position.y, 148, delta=.4)
        self.assertTrue(actor.is_on_floor())
        self.assertFalse(actor.drop_through())

    def test_short_jump_from_below_does_not_catch_upper_face(self):
        game, _ = self.setup_world()
        actor = game.add(CharacterBody(position=(60, 112), radius=10, motion_mode='grounded'))
        actor.velocity = (0, -265)
        peak = actor.position.y
        for _ in range(100):
            game.update(1/60)
            peak = min(peak, actor.position.y)
        self.assertTrue(56 < peak < 66, peak)
        self.assertAlmostEqual(actor.position.y, 144, delta=.4)

    def test_moving_one_way_platform_carries_character(self):
        game, platform = self.setup_world(AnimatableBody)
        actor = game.add(CharacterBody(position=(60, 35), radius=6, motion_mode='grounded'))
        self.step(game, 55)
        self.assertIs(actor._floor_hit.collider, platform)
        for _ in range(30):
            platform.position += (1, 0)
            game.update(1/60)
        self.assertAlmostEqual(actor.position.x, 90, delta=2)
        self.assertIs(actor._floor_hit.collider, platform)

    def test_tiled_object_layer_can_define_one_way_and_regular_platforms(self):
        with TemporaryDirectory(dir=Path.cwd()) as folder:
            file = Path(folder) / 'platform.tmj'
            file.write_text(json.dumps({
                'orientation': 'orthogonal', 'width': 10, 'height': 10,
                'tilewidth': 16, 'tileheight': 16, 'tilesets': [],
                'layers': [{
                    'id': 1, 'name': 'Platforms', 'type': 'objectgroup',
                    'properties': [{'name': 'one_way', 'type': 'bool', 'value': True}],
                    'objects': [
                        {'id': 1, 'x': 10, 'y': 66, 'width': 100, 'height': 8},
                        {'id': 2, 'x': 10, 'y': 150, 'width': 100, 'height': 8,
                         'properties': [{'name': 'one_way', 'type': 'bool', 'value': False}]},
                    ],
                }],
            }), encoding='utf-8')
            game = Game()
            self.addCleanup(game.close)
            tilemap = game.add(TileMap.from_tiled(file, collisions=True))
            self.assertEqual([body.one_way for body in tilemap.colliders], [True, False])
