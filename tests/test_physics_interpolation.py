from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sfml.graphics import Color

from doku2d import AnimatableBody, Camera, CharacterBody, Game, LightOccluder, PointLight, RigidBody


class PhysicsInterpolationTests(TestCase):
    def make_game(self, **options):
        game = Game(size=(120, 80), physics_fps=10, **options)
        self.addCleanup(game.close)
        return game

    def test_partial_frames_blend_drawn_pose_but_physics_keeps_exact_position(self):
        game = self.make_game(physics_interpolation=True)
        body = game.add(RigidBody(position=(20, 40), size=(6, 6), color=Color.WHITE))
        body.velocity = (100, 0)
        game.update(.14)
        self.assertAlmostEqual(body.position.x, 30)
        self.assertAlmostEqual(body.transform.transform_point((0, 0)).x, 30)
        self.assertAlmostEqual(body.render_position.x, 24)
        self.assertAlmostEqual(body.render_transform.transform_point((0, 0)).x, 24)
        hit = game.physics.raycast((0, 40), (60, 40))
        self.assertIs(hit.collider, body)
        self.assertAlmostEqual(hit.point.x, 27)

        game.update(.03)
        self.assertAlmostEqual(body.position.x, 30)
        self.assertAlmostEqual(body.render_position.x, 27)
        target = game.create_render_texture()
        target.clear(Color.BLACK)
        game.render(target)
        target.display()
        image = target.texture.to_image()
        self.assertEqual(image[25, 40], Color.WHITE)
        self.assertEqual(image[32, 40], Color.BLACK)

    def test_only_last_two_poses_survive_a_frame_with_multiple_ticks(self):
        game = self.make_game(physics_interpolation=True)
        body = game.add(RigidBody(position=(20, 40)))
        body.velocity = (100, 0)
        game.update(.25)
        self.assertAlmostEqual(body.position.x, 40)
        self.assertAlmostEqual(body.render_position.x, 35)

    def test_animatable_body_samples_edits_in_fixed_update_and_wraps_angles(self):
        class Platform(AnimatableBody):
            def physics_update(self, dt):
                self.move_to(self.position + (20, 0))
                self.rotation = 10

        game = self.make_game(physics_interpolation=True)
        body = game.add(Platform(position=(20, 30)))
        body.rotation = 350
        game.update(.15)
        self.assertAlmostEqual(body.position.x, 40)
        self.assertAlmostEqual(body.render_position.x, 30)
        self.assertAlmostEqual(body.render_rotation % 360, 0, places=4)

    def test_camera_and_visual_followers_use_render_pose_and_teleport_snaps(self):
        game = self.make_game(physics_interpolation=True)
        body = game.add(CharacterBody(position=(60, 40), size=(8, 8)))
        camera = game.add(Camera()).follow(body, smoothing=0)
        light = game.add(PointLight(target=body, position=(5, 0)))
        occluder = game.add(LightOccluder.from_body(body))
        body.velocity = (100, 0)
        game.update(.15)
        self.assertAlmostEqual(camera.screen_center.x, 65)
        self.assertAlmostEqual(game.make_view(game.world).center.x, 65)
        self.assertAlmostEqual(light.render_transform.transform_point((0, 0)).x, 70)
        self.assertAlmostEqual(light.transform.transform_point((0, 0)).x, 75)
        self.assertAlmostEqual(occluder.render_transform.transform_point((0, 0)).x, 65)
        self.assertAlmostEqual(occluder.world_points[0].x, 66)

        body.teleport((90, 50))
        self.assertEqual(tuple(body.render_position), (90, 50))
        self.assertEqual(tuple(camera.screen_center), (90, 50))
        game.update(.01)
        self.assertEqual(tuple(body.render_position), (90, 50))

    def test_pause_and_explicit_changes_discard_previous_pose(self):
        game = self.make_game(physics_interpolation=True)
        body = game.add(RigidBody(position=(20, 40)))
        body.velocity = (100, 0)
        game.update(.15)
        self.assertAlmostEqual(body.render_position.x, 25)
        game.paused = True
        game.update(.1)
        self.assertAlmostEqual(body.render_position.x, 30)
        game.paused = False
        game.update(.01)
        self.assertAlmostEqual(body.render_position.x, 30)
        body.position = (80, 40)
        self.assertEqual(tuple(body.render_position), (80, 40))
        game.update(.08)
        self.assertNotEqual(body.render_position, body.position)
        game.physics_interpolation = False
        self.assertEqual(body.render_position, body.position)

    def test_option_is_off_by_default_and_available_in_project_settings(self):
        game = self.make_game()
        body = game.add(RigidBody(position=(20, 40)))
        body.velocity = (100, 0)
        game.update(.15)
        self.assertFalse(game.physics_interpolation)
        self.assertEqual(body.render_position, body.position)

        with TemporaryDirectory() as folder:
            config = Path(folder) / 'doku2d.toml'
            config.write_text('[window]\nphysics_interpolation = true\n', encoding='utf-8')
            configured = Game.from_project(config)
            try:
                self.assertTrue(configured.physics_interpolation)
            finally:
                configured.close()
