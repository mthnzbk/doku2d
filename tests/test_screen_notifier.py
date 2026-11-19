from unittest import TestCase

from doku2d import Camera, Entity, Game, ScreenNotifier, StaticBody


class ScreenNotifierTests(TestCase):
    def test_enter_exit_and_auto_process_leave_colliders_registered(self):
        class Actor(StaticBody):
            def update(self, dt):
                self.frames += 1

            def physics_update(self, dt):
                self.steps += 1

        game = Game(size=(120, 100))
        self.addCleanup(game.close)
        actor = game.add(Actor(position=(170, 30), radius=6))
        actor.frames = actor.steps = 0
        notifier = game.add(ScreenNotifier(actor, auto_process=True))
        events = []
        notifier.screen_entered.connect(lambda: events.append('enter'))
        notifier.screen_exited.connect(lambda: events.append('exit'))
        game.update(1/60)
        self.assertEqual((actor.frames, actor.steps), (0, 0))
        self.assertIs(game.physics.raycast((155, 30), (180, 30)).collider, actor)
        self.assertNotIn(notifier, game.draw_list())

        actor.position = (80, 30)
        game.update(1/60)
        game.update(1/60)
        self.assertEqual((actor.frames, actor.steps), (2, 2))
        self.assertTrue(notifier.on_screen)
        actor.position = (200, 30)
        game.update(1/60)
        self.assertFalse(notifier.on_screen)
        self.assertEqual(events, ['enter', 'exit'])
        self.assertEqual((actor.frames, actor.steps), (2, 2))

        actor.process_mode = 'always'
        game.remove(notifier)
        game.update(1/60)
        self.assertEqual((actor.frames, actor.steps), (3, 3))
        self.assertEqual(actor.process_mode, 'always')

    def test_follows_rotated_camera_canvas_and_margin_independently_of_draw_culling(self):
        game = Game(size=(120, 100))
        self.addCleanup(game.close)
        camera = game.add(Camera())
        camera.position, camera.rotation, camera.zoom = (240, 200), 35, (2, 2)
        camera.reset_smoothing()
        game.culling = False
        watcher = game.add(ScreenNotifier(rect=(0, 0, 0, 0)))
        watcher.position = game.screen_to_world((-6, 50))
        hud_watcher = game.add(ScreenNotifier(rect=(0, 0, 0, 0), canvas=game.ui.canvas))
        hud_watcher.position = (110, 45)
        game.update(0)
        self.assertFalse(watcher.on_screen)
        self.assertTrue(hud_watcher.on_screen)
        watcher.margin = 4
        game.update(0)
        self.assertTrue(watcher.on_screen)

    def test_signal_can_remove_a_notifier_and_plain_notifier_does_not_pause(self):
        game = Game(size=(64, 64))
        self.addCleanup(game.close)
        actor = game.add(Entity())
        actor.position = (200, 200)
        info = game.add(ScreenNotifier(actor))
        auto = game.add(ScreenNotifier(actor, auto_process=True))
        auto.screen_entered.connect(lambda: game.remove(auto))
        actor.position = (15, 15)
        game.update(0)
        self.assertTrue(info.on_screen)
        self.assertIsNone(auto.game)
        actor.position = (200, 200)
        game.update(0)
        self.assertFalse(info.on_screen)
        self.assertTrue(actor.can_process())
