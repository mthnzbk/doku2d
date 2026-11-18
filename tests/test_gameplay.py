import unittest
from types import SimpleNamespace as EventData
from sfml.graphics import Color, Image, Texture, RenderTexture
from sfml.system import Vector2
from sfml.window import Event, Axis
from doku2d import (Game, Entity, Input, Key, JoyButton, JoyAxis, AnimatedSprite,
                    CharacterBody, RigidBody, StaticBody, Area, Circle, Box,
                    VirtualJoystick, TouchScreenButton, LineEdit)


def key(code, release=False):
    return EventData(type=Event.KEY_RELEASED if release else Event.KEY_PRESSED,
                     code=code, control=False, shift=False, alt=False, system=False)


class InputTests(unittest.TestCase):
    def test_keys_edges_repeat_and_diagonal(self):
        inputs = Input()
        inputs.handle_event(key(Key.D))
        inputs.handle_event(key(Key.S))
        self.assertAlmostEqual(sum(v*v for v in inputs.get_vector()), 1)
        self.assertTrue(inputs.is_action_just_pressed('move_right'))
        inputs._end_frame()
        inputs.handle_event(key(Key.D))
        self.assertFalse(inputs.is_action_just_pressed('move_right'))
        inputs.handle_event(key(Key.D, True), consumed=True)
        self.assertTrue(inputs.is_action_just_released('move_right'))
        inputs.handle_event(EventData(type=Event.LOST_FOCUS))
        self.assertEqual(tuple(inputs.get_vector()), (0,0))
        inputs._begin_physics()
        self.assertFalse(inputs.is_action_just_pressed('move_down'))

    def test_edges_survive_zero_ticks_but_not_repeat_ticks(self):
        game = Game()
        physics, frames = [], []
        class Probe(Entity):
            def physics_update(self, dt):
                physics.append(self.input.is_action_just_pressed('jump'))
            def update(self, dt):
                frames.append(self.input.is_action_just_pressed('jump'))
        game.add(Probe())
        game.handle_event(key(Key.SPACE))
        game.update(0)
        game.update(3/60)
        self.assertEqual(physics, [True,False,False])
        self.assertEqual(frames, [True,False])
        game.close()

    def test_gamepad_deadzone_disconnect_and_combined_sources(self):
        inputs = Input()
        inputs.handle_event(EventData(type=Event.JOYSTICK_MOVED, joystick_id=0, axis=Axis.X, position=10))
        self.assertEqual(inputs.get_action_strength('move_right'), 0)
        inputs.handle_event(EventData(type=Event.JOYSTICK_MOVED, joystick_id=0, axis=Axis.X, position=60))
        self.assertAlmostEqual(inputs.get_action_strength('move_right'), .5)
        inputs.action_press('move_right', .8, source='touch')
        inputs.handle_event(EventData(type=Event.JOYSTICK_DISCONNECTED, joystick_id=0))
        self.assertEqual(inputs.get_action_strength('move_right'), .8)
        inputs.release_source('touch')
        self.assertFalse(inputs.is_action_pressed('move_right'))
        inputs.bind('fire', JoyButton(2), JoyAxis('Z'))
        inputs.handle_event(EventData(type=Event.JOYSTICK_BUTTON_PRESSED, joystick_id=1, button=2))
        self.assertTrue(inputs.is_action_pressed('fire'))

    def test_gui_focus_and_virtual_controls_release(self):
        game = Game()
        edit = game.add(LineEdit())
        edit.grab_focus()
        game.handle_event(key(Key.D))
        self.assertFalse(game.input.is_action_pressed('move_right'))
        game.ui.set_focus(None)
        game.update(0)
        self.assertFalse(game.input.is_action_pressed('move_right'))
        game.handle_event(key(Key.D, True))
        game.handle_event(key(Key.D))
        self.assertTrue(game.input.is_action_pressed('move_right'))
        game.handle_event(key(Key.D, True))
        stick = game.add(VirtualJoystick())
        stick._pointer_down(Vector2(100,50))
        self.assertEqual(game.input.get_action_strength('move_right'), 1)
        stick._cancel_pointer()
        self.assertFalse(game.input.is_action_pressed('move_right'))
        button = game.add(TouchScreenButton())
        button.action = 'jump'
        button._pointer_down(Vector2(0,0))
        self.assertTrue(game.input.is_action_pressed('jump'))
        game.remove(button)
        self.assertFalse(game.input.is_action_pressed('jump'))
        game.close()


class PhysicsTests(unittest.TestCase):
    def setUp(self):
        self.game = Game()
    def tearDown(self):
        self.game.close()
    def steps(self, count=120):
        for _ in range(count): self.game.update(1/60)

    def test_character_stops_at_wall_and_slides(self):
        class Player(CharacterBody):
            def physics_update(self, dt):
                self.velocity = (100,20)
                self.move_and_slide()
        player = self.game.add(Player(size=(20,20)))
        wall = self.game.add(StaticBody(position=(70,0),size=(20,400)))
        self.steps()
        self.assertLess(player.position.x, 52)
        self.assertGreater(player.position.y, 35)
        self.assertTrue(player.is_on_wall())
        self.assertIs(player.get_slide_collision(0).collider, wall)

    def test_gravity_floor_pause_and_impulse(self):
        self.game.physics.gravity = (0,400)
        floor = self.game.add(StaticBody(position=(0,100),size=(400,20)))
        body = self.game.add(RigidBody(size=(20,20)))
        self.steps()
        self.assertAlmostEqual(body.position.y,80,delta=1)
        self.game.paused = True
        position = tuple(body.position)
        self.steps(10)
        self.assertEqual(tuple(body.position),position)
        self.game.paused = False
        body.apply_impulse((100,-200))
        self.steps(10)
        self.assertGreater(body.position.x, 5)
        self.assertLess(body.position.y,80)

    def test_sensor_signals_queries_removal_and_areas(self):
        area = self.game.add(Area(radius=30))
        area.collision_layer = 2
        other_area = self.game.add(Area(radius=10))
        body = self.game.add(CharacterBody(size=(10,10)))
        entered,exited,areas = [],[],[]
        area.body_entered.connect(entered.append)
        area.body_exited.connect(exited.append)
        area.area_entered.connect(areas.append)
        self.steps(2)
        self.assertEqual(entered,[body])
        self.assertEqual(areas,[other_area])
        self.assertIn(body,area.get_overlapping_bodies())
        body.position = (100,0)
        self.steps(2)
        self.assertEqual(exited,[body])
        body.position = (0,0)
        self.steps(2)
        self.game.remove(body)
        self.game.flush_deferred()
        self.assertEqual(exited,[body,body])
        self.assertNotIn(body,area.get_overlapping_bodies())

    def test_masks_raycast_and_resize(self):
        wall = self.game.add(StaticBody(position=(50,0),size=(10,100)))
        hit = self.game.physics.raycast((0,0),(100,0))
        self.assertIs(hit.collider,wall)
        self.assertAlmostEqual(hit.point.x,45)
        self.assertIsNone(self.game.physics.raycast((0,0),(100,0),exclude=(wall,)))
        wall.collision_layer = 2
        self.steps(1)
        self.assertIsNone(self.game.physics.raycast((0,0),(100,0),mask=1))
        wall.shape = Circle(20)
        self.assertIsNotNone(self.game.physics.raycast((0,0),(100,0),mask=2))
        wall.scale = (2,2)
        self.assertAlmostEqual(self.game.physics.raycast((0,0),(100,0),mask=2).point.x,10)

    def test_sensor_bounding_boxes_overlap_without_geometric_contact(self):
        area = self.game.add(Area(radius=16))
        body = self.game.add(CharacterBody(position=(25,25),size=(22,22)))
        self.steps(2)
        self.assertEqual(area.get_overlapping_bodies(),())
        body.position = (15,15)
        self.steps(2)
        self.assertIn(body,area.get_overlapping_bodies())

    def test_collect_removes_inside_signal_without_locked_space(self):
        area = self.game.add(Area(radius=30))
        body = self.game.add(CharacterBody())
        area.body_entered.connect(lambda other:self.game.remove(area))
        self.steps(2)
        self.assertIsNone(area.game)
        self.assertIs(body.game,self.game)


class AnimationTests(unittest.TestCase):
    def sprite(self):
        image = Image.create(32,8,Color.RED)
        sprite = AnimatedSprite(Texture.from_image(image),frame_size=(8,8))
        sprite.add_animation('walk',[0,1,2,3],fps=10)
        sprite.add_animation('once',[0,1],fps=10,loop=False)
        return sprite

    def test_loop_repeat_play_pause_reverse_and_finish(self):
        sprite = self.sprite()
        loops,finished = [],[]
        sprite.animation_looped.connect(lambda:loops.append(True))
        sprite.animation_finished.connect(lambda:finished.append(True))
        sprite.play('walk')
        sprite.advance(.1)
        sprite.play('walk')
        self.assertEqual(sprite.frame,1)
        sprite.advance(.3)
        self.assertEqual(sprite.frame,0)
        self.assertEqual(len(loops),1)
        sprite.pause()
        sprite.advance(1)
        self.assertEqual(sprite.frame,0)
        sprite.play('walk',speed=-1,from_end=True)
        sprite.advance(.1)
        self.assertEqual(sprite.frame,2)
        sprite.play('once')
        sprite.advance(.2)
        self.assertEqual(sprite.frame,1)
        self.assertFalse(sprite.playing)
        self.assertEqual(len(finished),1)
        sprite.advance(1)
        self.assertEqual(len(finished),1)
        sprite.play('once')
        self.assertEqual(sprite.frame,0)
        sprite.advance(.2)
        self.assertEqual(len(finished),2)

    def test_auto_advance_composition_and_paused_game(self):
        game = Game()
        sprite = self.sprite()
        body = game.add(CharacterBody())
        body.sprite = sprite
        sprite.play('walk')
        game.update(.1)
        self.assertEqual(sprite.frame,1)
        game.paused = True
        game.update(.1)
        self.assertEqual(sprite.frame,1)
        game.paused = False
        target = RenderTexture(64,64)
        game.render(target)
        target.display()
        game.close()

    def test_invalid_frames_and_immutable_animation_map(self):
        sprite = self.sprite()
        with self.assertRaises(ValueError): sprite.add_animation('bad',[9])
        with self.assertRaises(ValueError): sprite.add_animation('bad',[],fps=10)
        with self.assertRaises(TypeError): sprite.sprite_frames['new'] = None
        with self.assertRaises(ValueError): sprite.frame_size = (7,8)
        self.assertEqual(tuple(sprite.frame_size),(8,8))


class PlayableExampleTests(unittest.TestCase):
    def test_input_collection_pause_restart_and_win(self):
        from examples.collect_game import make_game, Spark, COINS
        game, session = make_game()
        try:
            game.handle_event(key(Key.D))
            for _ in range(20): game.update(1/60)
            game.handle_event(key(Key.D,True))
            self.assertGreater(session.player.position.x,170)
            self.assertEqual(session.score,1)
            self.assertEqual(len([obj for obj in game.objects if isinstance(obj,Spark)]),7)
            game.handle_event(key(Key.ESCAPE))
            game.update(1/60)
            self.assertTrue(game.paused)
            self.assertTrue(all(obj.visible for obj in session.menu))
            game.handle_event(key(Key.ESCAPE,True))
            game.handle_event(key(Key.ESCAPE))
            game.update(1/60)
            self.assertFalse(game.paused)
            game.handle_event(key(Key.ESCAPE,True))
            session.restart()
            game.flush_deferred()
            self.assertEqual(session.score,0)
            self.assertEqual(tuple(session.player.position),(108,200))
            for position in COINS:
                session.player.position = position
                session.player.velocity = (0,0)
                game.update(1/60)
            self.assertEqual(session.score,len(COINS))
            self.assertTrue(game.paused)
            self.assertIn('toplad',session.menu_title.text)
            self.assertTrue(session.entry.disabled)
            session.restart()
            game.flush_deferred()
            self.assertFalse(game.paused)
            self.assertEqual(session.score,0)
        finally:
            game.close()


if __name__ == '__main__':
    unittest.main()
