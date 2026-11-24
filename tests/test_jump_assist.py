from unittest import TestCase

from doku2d import CharacterBody, Game, StaticBody


STEP = 1 / 60


class JumpAssistTests(TestCase):
    def setup_character(self, position, **options):
        game = Game()
        self.addCleanup(game.close)
        game.physics.gravity = (0, 800)
        game.add(StaticBody(position=(60, 120), size=(100, 12)))
        actor = game.add(CharacterBody(position=position, size=(16, 20),
                                       motion_mode='grounded', **options))
        return game, actor

    def walk_off(self, game, actor):
        for _ in range(20):
            game.update(STEP)
        self.assertTrue(actor.is_on_floor())
        actor.velocity = (180, 0)
        for _ in range(30):
            game.update(STEP)
            if not actor.is_on_floor():
                break
        self.assertFalse(actor.is_on_floor())

    def test_coyote_jump_is_available_once_then_expires(self):
        game, actor = self.setup_character((96, 90), coyote_time=.1)
        self.walk_off(game, actor)
        self.assertTrue(actor.jump(320))
        self.assertFalse(actor.jump(320))
        game.update(STEP)
        self.assertLess(actor.velocity.y, -300)
        self.assertFalse(actor.jump(320))
        actor.teleport((96, 90))
        self.walk_off(game, actor)
        for _ in range(8):
            game.update(STEP)
        self.assertFalse(actor.jump())

    def test_buffer_applies_the_requested_speed_on_landing(self):
        game, actor = self.setup_character((60, 92), jump_buffer=.12)
        actor.velocity = (35, 90)
        self.assertFalse(actor.jump(310))
        for _ in range(12):
            game.update(STEP)
            if actor.velocity.y < 0:
                break
        self.assertAlmostEqual(actor.velocity.y, -310)
        self.assertAlmostEqual(actor.velocity.x, 35)
        game.update(STEP)
        self.assertLess(actor.velocity.y, -290)
        self.assertFalse(actor.is_on_floor())

    def test_buffer_expires_and_teleport_clears_pending_jump(self):
        game, actor = self.setup_character((60, 20), jump_buffer=.1)
        self.assertFalse(actor.jump())
        for _ in range(42):
            game.update(STEP)
        self.assertTrue(actor.is_on_floor())
        actor.teleport((60, 92))
        self.assertFalse(actor.jump())
        actor.teleport((60, 92))
        for _ in range(12):
            game.update(STEP)
        self.assertTrue(actor.is_on_floor())

    def test_drop_through_cancels_edge_grace(self):
        game, actor = self.setup_character((60, 52), coyote_time=.1)
        game.add(StaticBody(position=(60, 80), size=(90, 8), one_way=True))
        for _ in range(24):
            game.update(STEP)
        self.assertTrue(actor.drop_through())
        self.assertFalse(actor.jump())
        for _ in range(28):
            game.update(STEP)
        self.assertTrue(actor.is_on_floor())
        self.assertGreater(actor.position.y, 95)

    def test_both_options_default_to_zero_and_validate_duration(self):
        game, actor = self.setup_character((96, 90))
        self.assertEqual((actor.coyote_time, actor.jump_buffer), (0, 0))
        self.walk_off(game, actor)
        self.assertFalse(actor.jump())
        with self.assertRaises(ValueError):
            actor.coyote_time = -1
        with self.assertRaises(ValueError):
            actor.jump_buffer = float('inf')
