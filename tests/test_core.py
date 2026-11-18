import gc
import importlib
import inspect
import unittest
from dataclasses import dataclass
from sfml.graphics import Color, Image, RenderTexture, Texture
from doku2d import (AudioListener, Button, Camera, Canvas, CharacterBody, Entity,
                    Game, ItemList, Range, Signal, Sprite)
from doku2d.gui import ProgressBar, Slider, SpinBox, ScrollBar


class CoreTests(unittest.TestCase):
    def test_flat_registration_and_no_special_root(self):
        import doku2d
        game = Game()
        first, second = Entity(), Entity()
        game.add(first)
        game.add(second)
        self.assertEqual(game.objects, (first, second))
        self.assertIs(first.game, game)
        for name in ("Scene", "SceneTree", "Viewport", "Node", "HUD"):
            self.assertFalse(hasattr(doku2d, name))
        self.assertFalse(hasattr(first, "parent"))
        with self.assertRaises(ValueError):
            game.add(first)
        game.close()
        self.assertIsNone(first.game)

    def test_independent_state_and_all_properties(self):
        for module_name in ("gui.control", "gui.layout", "gui.utils", "audio.audio",
                            "physics.body", "physics.collision", "physics.navigation",
                            "rendering.camera", "rendering.light", "rendering.other",
                            "rendering.particles", "rendering.parallax", "rendering.tilemap",
                            "animation.animatedsprite"):
            module = importlib.import_module("doku2d." + module_name)
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ != module.__name__:
                    continue
                with self.subTest(cls=name):
                    instance = cls()
                    for attr, prop in inspect.getmembers(cls, lambda p: isinstance(p, property)):
                        getattr(instance, attr)
        self.assertIsNot(CharacterBody().collision_object, CharacterBody().collision_object)
        a, b = ItemList(), ItemList()
        a.items.append("item")
        self.assertEqual(b.items, [])
        first, second = Entity(), Entity()
        first.scale = (3, 2)
        self.assertEqual(tuple(second.scale), (1, 1))

    def test_instance_signals_disconnect_one_shot_and_dead_receivers(self):
        first, second = Button(), Button()
        calls = []
        first.pressed.connect(lambda: calls.append("first"))
        second.pressed.emit()
        self.assertEqual(calls, [])
        first.pressed.emit()
        self.assertEqual(calls, ["first"])
        signal = Signal()
        def once():
            calls.append("once")
            signal.emit()
        signal.connect(once, one_shot=True)
        signal.emit()
        self.assertEqual(calls.count("once"), 1)
        signal = Signal()
        def later():
            calls.append("later")
        signal.connect(lambda: signal.disconnect(later))
        signal.connect(later)
        signal.emit()
        self.assertNotIn("later", calls)
        class Receiver:
            def receive(self): calls.append("dead")
        receiver = Receiver()
        signal.connect(receiver.receive)
        del receiver
        gc.collect()
        signal.emit()
        self.assertNotIn("dead", calls)

    def test_lifecycle_and_normal_python_services(self):
        events = []
        class Tracked(Entity):
            def on_added(self): events.append("added")
            def on_ready(self): events.append("ready")
            def on_removed(self): events.append("removed")
        @dataclass
        class Session:
            score: int = 0
        game = Game(services={"session": Session, "ticker": Tracked})
        ticker = game.services["ticker"]
        session = game.services["session"]
        self.assertEqual(events, ["added", "ready"])
        game.replace(Tracked)
        self.assertIs(game.services["session"], session)
        self.assertIs(ticker.game, game)
        self.assertEqual(len(game.objects), 2)
        game.services.remove("ticker")
        self.assertIsNone(ticker.game)
        game.add(ticker)
        self.assertEqual(events.count("ready"), 2)
        game.close()

    def test_deferred_removal_addition_and_pause(self):
        calls = []
        new = Entity()
        class Switch(Entity):
            def update(self, dt):
                calls.append("switch")
                self.game.add(new)
                victim.destroy()
                self.destroy()
        class Tick(Entity):
            def update(self, dt): calls.append("tick")
        game = Game()
        switch = game.add(Switch())
        victim = game.add(Tick())
        game.update(0)
        self.assertEqual(calls, ["switch"])
        self.assertEqual(game.objects, (new,))
        self.assertIsNone(victim.game)
        ticking = game.add(Tick())
        game.paused = True
        game.update(0)
        self.assertEqual(calls, ["switch"])
        ticking.process_mode = "when_paused"
        game.update(0)
        self.assertEqual(calls, ["switch", "tick"])
        game.close()

    def test_failed_registration_and_replace_restore_registry(self):
        game = Game(services={"state": dict})
        old = game.add(Entity())
        class Broken(Entity):
            def on_ready(self): raise RuntimeError("setup failed")
        broken = Broken()
        with self.assertRaises(RuntimeError):
            game.replace(broken)
        self.assertEqual(game.objects, (old,))
        self.assertIsNone(broken.game)
        self.assertIn("state", game.services)
        with self.assertRaises(RuntimeError):
            game.services.add("broken", Broken)
        self.assertNotIn("broken", game.services)
        game.close()

    def test_close_cleans_all_objects_even_when_callback_raises(self):
        game = Game(services={"state": dict})
        class Broken(Entity):
            def on_removed(self):
                self.assertion = "state" in self.game.services
                raise RuntimeError("cleanup failed")
        broken = game.add(Broken())
        other = game.add(Entity())
        with self.assertRaises(RuntimeError):
            game.close()
        self.assertTrue(broken.assertion)
        self.assertIsNone(other.game)
        self.assertEqual(game.objects, ())
        self.assertEqual(len(game.services), 0)
        game.close()

    def test_range_controls_share_validation_not_storage(self):
        for cls in (ProgressBar, Slider, SpinBox, ScrollBar):
            with self.subTest(cls=cls.__name__):
                control = cls(min_value=-10, max_value=10, step=2, value=1)
                self.assertEqual(control.value, 2)
                events = []
                control.value_changed.connect(events.append)
                control.value = 100
                control.value = 100
                self.assertEqual(events, [10])
                control.max_value = 6
                self.assertEqual(control.value, 6)
                self.assertEqual(control.ratio, 1)
                with self.assertRaises(ValueError): control.min_value = 7
                with self.assertRaises(ValueError): control.step = -1
                with self.assertRaises(ValueError): control.value = float("nan")

    def test_fixed_step(self):
        calls = []
        class Tick(Entity):
            def physics_update(self, dt): calls.append(dt)
        game = Game(physics_fps=50)
        game.add(Tick())
        game.update(0.1)
        self.assertEqual(len(calls), 5)
        self.assertAlmostEqual(sum(calls), 0.1)
        game.close()

    def test_canvas_camera_and_order_in_pixels_and_events(self):
        game = Game(size=(64, 64))
        camera = game.add(Camera())
        camera.position = (132, 132)
        red = Texture.from_image(Image.create(8, 8, Color.RED))
        green = Texture.from_image(Image.create(8, 8, Color.GREEN))
        world = game.add(Sprite(red))
        world.position = (132, 132)
        overlay = Canvas("UI", order=1, screen_space=True)
        ui = game.add(Sprite(green), canvas=overlay)
        ui.position = (12, 12)
        target = RenderTexture(64, 64)
        target.clear(Color.BLACK)
        game.render(target)
        target.display()
        image = target.texture.to_image()
        self.assertEqual(image[32, 32], Color.RED)
        self.assertEqual(image[12, 12], Color.GREEN)
        self.assertIs(game.camera, camera)
        game.remove(camera)
        self.assertIsNone(game.camera)
        game.close()

    def test_canvas_parallax_and_frontmost_input(self):
        game = Game(size=(100, 80))
        camera = game.add(Camera())
        camera.position = (150, 40)
        background = Canvas(order=-1, parallax=(0.2, 1))
        self.assertAlmostEqual(game.make_view(background).center.x, 70)
        calls = []
        class Input(Entity):
            def handle_event(self, event):
                calls.append(self.name)
                return True
        game.add(Input("World"))
        game.add(Input("Overlay"), canvas=Canvas(order=1, screen_space=True))
        game.handle_event(object())
        self.assertEqual(calls, ["Overlay"])
        game.close()

    def test_pending_objects_cannot_be_added_to_another_game(self):
        other = Game()
        game = Game()
        child = Entity()
        class Spawner(Entity):
            def on_ready(self):
                self.game.add(child)
                with self_case.assertRaises(ValueError):
                    other.add(child)
        self_case = self
        game.add(Spawner())
        game.update(0)
        self.assertIs(child.game, game)
        game.close()
        other.close()

    def test_replace_reserves_objects_and_cancels_outgoing_pending_content(self):
        game, other = Game(), Game()
        replacement, stale = Entity(), Entity()
        test = self
        class Switch(Entity):
            def update(self, dt):
                self.game.add(stale)
                self.game.replace(replacement)
                with test.assertRaises(ValueError):
                    other.add(replacement)
                self.process_mode = "disabled"
        game.add(Switch())
        game.update(0)
        self.assertEqual(game.objects, (replacement,))
        self.assertIsNone(stale.game)
        self.assertIsNone(stale._pending_game)
        game.close()
        other.close()

    def test_plain_code_reference_service(self):
        game = Game(services={"data": "builtins:dict"})
        self.assertEqual(game.services["data"], {})
        game.close()


if __name__ == "__main__":
    unittest.main()
