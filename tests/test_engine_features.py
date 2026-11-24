"""Regression checks for scopes, fixed resolution, themes, tile meshes and builds."""
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import os
import subprocess

from sfml.graphics import Color, Image, RectangleShape, RenderTexture, RenderWindow, Shader, Texture
from sfml.window import Event, VideoMode

from doku2d import AmbientLight, Button, Camera, CanvasGroup, DirectionalLight, Entity, Game, Label, PointLight, Signal, Theme, TileMap, TileSet, VBox
from doku2d.cli import build_project


class EngineFeatures(TestCase):
    def test_scope_releases_nested_entities_signals_and_deferred_work(self):
        game = Game()
        self.addCleanup(game.close)
        scope = game.create_scope()
        calls = []
        signal = Signal()

        class Root(Entity):
            def on_ready(self):
                self.child = self.game.add(Entity())


        persistent = game.add(Entity(), persistent=True)
        root = scope.add(Root())
        game.flush_deferred()
        self.assertIs(root.child.game, game)
        scope.defer(calls.append, 'stale')
        scope.connect(signal, calls.append)
        signal.emit('live')
        scope.close()
        signal.emit('closed')
        self.assertEqual(calls, ['live'])
        self.assertEqual(scope.members, ())
        self.assertEqual(game.objects, (persistent,))
        self.assertIsNone(root.child.game)

    def test_replace_closes_outgoing_scopes(self):
        game = Game()
        self.addCleanup(game.close)
        scope = game.create_scope()
        scope.add(Entity())
        signal = Signal()
        callback = scope.connect(signal, lambda: None)
        replacement = Entity()
        game.replace(replacement)
        self.assertTrue(scope.closed)
        self.assertFalse(signal.is_connected(callback))
        self.assertEqual(game.objects, (replacement,))

    def test_fit_bars_and_camera_coordinates_match_rendered_content(self):
        game = Game(size=(80, 40), window_size=(120, 120))
        self.addCleanup(game.close)
        class Square(Entity):
            def render(self, target, states):
                shape = RectangleShape((20, 20))
                shape.fill_color = Color.RED
                target.draw(shape, states)
        game.add(Square())
        target = RenderTexture(120, 120)
        game.render(target)
        target.display()
        image = target.texture.to_image()
        self.assertEqual(image[10, 20], Color.BLACK)
        self.assertEqual(image[10, 35], Color.RED)
        self.assertEqual(image[10, 63], game.clear_color)
        self.assertIsNone(game.window_to_screen((10, 20)))
        camera = game.add(Camera())
        camera.position = (31, 61)
        camera.zoom = (2, 1.5)
        camera.rotation = 23
        game.camera = camera
        game.update(0)
        point = (24, 66)
        pixel = game.world_to_window(point)
        actual = game.window_to_world(pixel)
        self.assertAlmostEqual(actual.x, point[0], places=4)
        self.assertAlmostEqual(actual.y, point[1], places=4)

    def test_live_window_resize_keeps_world_hud_and_pointer_aligned(self):
        game = Game(size=(160, 90))
        self.addCleanup(game.close)
        # SFML keeps this initial default view even after window.size changes.
        window = RenderWindow(VideoMode(240, 200), 'Doku2D resize test')
        self.addCleanup(window.close)
        game._window = window

        class Block(Entity):
            def __init__(self, color, size):
                super().__init__()
                self.shape = RectangleShape(size)
                self.shape.fill_color = color

            def render(self, target, states):
                target.draw(self.shape, states)

        game.add(Block(Color.WHITE, (160, 90)))
        game.add(AmbientLight(color=(80, 80, 80)))
        group = game.add(CanvasGroup(canvas=game.ui.canvas))
        marker = group.add(Block(Color.RED, (20, 20)))
        marker.position = (125, 50)
        button = group.add(Button(text='HUD'))
        button.position = (10, 10)
        button.size = (45, 26)

        for size in ((320, 220), (160, 90), (320, 110)):
            with self.subTest(size=size):
                window.size = size
                deadline = monotonic()+2
                image = None
                # A resize can leave the old back buffer in place until the
                # window system has processed the new size and swapped a frame.
                while monotonic() < deadline:
                    for _ in window.events:
                        pass
                    if tuple(window.size) == size:
                        window.clear(game.clear_color)
                        game.render(window)
                        pixels = Texture.create(*size)
                        pixels.update_from_window(window)
                        image = pixels.to_image()
                        window.display()
                        marker_pixel = tuple(map(round, game.screen_to_window((134, 58))))
                        world_pixel = tuple(map(round, game.screen_to_window((90, 45))))
                        if image[marker_pixel] == Color.RED and image[world_pixel] == Color(80, 80, 80):
                            break
                    sleep(.01)
                self.assertIsNotNone(image, f'Window resize to {size} did not arrive')
                self.assertEqual(image[marker_pixel], Color.RED)
                self.assertEqual(image[world_pixel], Color(80, 80, 80))
                if size != (160, 90):
                    self.assertEqual(image[0, 0], Color.BLACK)
                pointer = game.screen_to_window((30, 20))
                game.handle_event(SimpleNamespace(type=Event.MOUSE_MOVED, position=pointer))
                self.assertIs(game.ui.hover, button)

    def test_scaled_pointer_hits_ui_and_bars_do_not(self):
        game = Game(size=(100, 50), window_size=(200, 200))
        self.addCleanup(game.close)
        button = game.add(Button(text='Open'))
        button.position = (0, 0)
        button.size = (30, 20)
        game.handle_event(SimpleNamespace(type=Event.MOUSE_MOVED, position=(20, 30)))
        self.assertIsNone(game.ui.hover)
        game.handle_event(SimpleNamespace(type=Event.MOUSE_MOVED, position=(20, 65)))
        self.assertIs(game.ui.hover, button)

    def test_theme_file_and_layout_inheritance(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root/'theme.toml').write_text('[theme]\naccent=[1,2,3]\nradius=12\nfont_size=21\n', encoding='utf-8')
            (root/'doku2d.toml').write_text('[ui]\ntheme="theme.toml"\n[window]\ninitial_width=1200\n', encoding='utf-8')
            game = Game.from_project(root)
            try:
                self.assertEqual(game.window_size.x, 1200)
                self.assertEqual(game.ui.theme.accent, (1, 2, 3))
                layout = game.add(VBox())
                layout.theme = game.ui.theme.variant(radius=4)
                label = layout.add(Label(text='Theme'))
                self.assertEqual(label.theme.radius, 4)
                self.assertEqual(label.font_size, 21)
                label.theme = Theme(radius=1)
                self.assertEqual(label.theme.radius, 1)
            finally:
                game.close()

    def test_only_visible_animated_chunks_rebuild(self):
        game = Game(size=(160, 80))
        self.addCleanup(game.close)
        texture = Texture.from_image(Image.create(16, 8, Color.WHITE))
        tileset = TileSet(texture, tile_size=(8, 8))
        tileset.add_animation(0, [0, 1], fps=2)
        tilemap = TileMap(tile_set=tileset)
        tilemap.chunk = (4, 4)
        layer = tilemap.add_layer('ground')
        for point, tile in (((0, 0), 0), ((5, 0), 1), ((2000, 0), 1)):
            layer.set_cell(point, tile)
        game.add(tilemap)
        target = RenderTexture(160, 80)
        game.render(target)
        first = dict(layer._meshes)
        self.assertEqual(set(first), {(0, 0), (1, 0)})
        game.update(.25)
        game.update(.25)
        game.render(target)
        self.assertIsNot(first[0, 0], layer._meshes[0, 0])
        self.assertIs(first[1, 0], layer._meshes[1, 0])

    def test_scaled_ambient_draws_without_light_buffers_and_switches_to_point_lights(self):
        if not Shader.is_available():
            self.skipTest('Point and directional lights require OpenGL shaders')
        game = Game(size=(40, 20))
        self.addCleanup(game.close)
        class Surface(Entity):
            def render(self, target, states):
                target.draw(RectangleShape((40, 20)), states)
        game.add(Surface())
        game.add(AmbientLight(color=(40, 40, 40)))

        def center_pixel():
            target = RenderTexture(80, 60)
            game.render(target)
            target.display()
            return target.texture.to_image()[40, 30].r

        self.assertAlmostEqual(center_pixel(), 40, delta=1)
        self.assertIsNone(game._lighting._lights)
        lamp = game.add(PointLight(position=(20, 10), radius=12))
        self.assertGreater(center_pixel(), 150)
        self.assertIsNone(game._lighting._scratch)
        lamp.enabled = False
        sun = game.add(DirectionalLight(energy=.5))
        self.assertGreater(center_pixel(), 120)
        self.assertIsNotNone(game._lighting._scratch)
        sun.enabled = False
        self.assertAlmostEqual(center_pixel(), 40, delta=1)

    def test_standalone_build_returns_binary_and_keeps_previous_on_compile_failure(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root/'doku2d.toml').write_text('[game]\napp_id="sample"\n[ui]\ntheme="theme.toml"\n', encoding='utf-8')
            (root/'main.py').touch()
            (root/'theme.toml').write_text('font="menu.ttf"', encoding='utf-8')
            (root/'menu.ttf').touch()
            executable = 'sample.exe' if os.name == 'nt' else 'sample.bin'
            def compile_to_stage(command, **kwargs):
                self.assertIn(f'--include-data-files={root / "theme.toml"}=theme.toml', command)
                self.assertIn(f'--include-data-files={root / "menu.ttf"}=menu.ttf', command)
                stage = next(arg.split('=', 1)[1] for arg in command if arg.startswith('--output-dir='))
                package = Path(stage) / 'sample.dist'
                package.mkdir()
                (package / executable).write_text('compiled', encoding='utf-8')
            with patch('doku2d.cli.importlib.util.find_spec', return_value=True), patch('doku2d.cli.subprocess.run', side_effect=compile_to_stage):
                binary = build_project(root)
            self.assertEqual(binary, root/'dist'/'sample.dist'/executable)
            with patch('doku2d.cli.importlib.util.find_spec', return_value=True), patch('doku2d.cli.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'nuitka')):
                with self.assertRaises(subprocess.CalledProcessError):
                    build_project(root)
            self.assertEqual(binary.read_text(encoding='utf-8'), 'compiled')
