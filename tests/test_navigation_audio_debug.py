from types import SimpleNamespace
from unittest import TestCase

from sfml.graphics import Color, Image, RenderTexture, Texture
from sfml.window import Event

from doku2d import AudioListener, AudioPlayer, Camera, Game, Key, PositionalAudio, StaticBody, TileMap, TileSet
from doku2d.rendering.tiledparser import LayerData, MapData, MapObject


class NavigationAudioDebugTests(TestCase):
    def test_audio_master_and_buses_update_live_and_positional_voices(self):
        game = Game()
        self.addCleanup(game.close)
        game.add(AudioListener())
        music = game.add(AudioPlayer(volume=80, bus='Music'))
        positional = game.add(PositionalAudio(position=(50, 0), max_distance=100))
        music_voice = SimpleNamespace()
        positional_voice = SimpleNamespace()
        music._voices.append(music_voice)
        positional._voices.append(positional_voice)
        self.addCleanup(music._voices.clear)
        self.addCleanup(positional._voices.clear)

        game.audio['Master'].volume = 50
        game.audio['Music'].volume = 25
        self.assertEqual(music_voice.volume, 10)
        self.assertEqual(positional_voice.volume, 25)
        self.assertGreater(positional_voice.pan, 0)
        game.audio['Music'].muted = True
        self.assertEqual(music_voice.volume, 0)
        self.assertEqual(positional_voice.volume, 25)

        game.audio.add_bus('Ambience', volume=40)
        music.bus = 'Ambience'
        self.assertEqual(music_voice.volume, 16)
        with self.assertRaises(KeyError):
            music.bus = 'Missing'
        self.assertEqual(music.bus, 'Ambience')
        other = Game()
        self.addCleanup(other.close)
        self.assertEqual(other.audio['Master'].volume, 100)

    def test_path_uses_solid_tiles_then_reflects_edits(self):
        tiles = TileSet('unloaded-atlas.png', tile_size=(16, 16))
        tiles.set_solid(1)
        tilemap = TileMap(tile_set=tiles)
        layer = tilemap.add_layer('Walls')
        for y in range(3):
            layer.set_cell((2, y), 1)
        limits = (0, 0, 5, 4)
        path = tilemap.find_path((1, 1), (3, 1), bounds=limits)
        self.assertEqual(len(path), 7)
        self.assertIn((2, 3), path)

        layer.set_cell((2, 1), 0)
        straight = [(1, 1), (2, 1), (3, 1)]
        self.assertEqual(tilemap.find_path(straight[0], straight[-1], bounds=limits), straight)
        self.assertNotIn((2, 1), tilemap.find_path(straight[0], straight[-1], bounds=limits, blocked_layers='Walls'))
        self.assertNotIn((2, 1), tilemap.find_path(straight[0], straight[-1], bounds=limits, blocked=[(2, 1)]))
        tilemap.position = (25, 30)
        tilemap.rotation = 15
        world_path = tilemap.find_world_path(tilemap.map_to_world(straight[0]), tilemap.map_to_world(straight[-1]), bounds=limits)
        self.assertEqual([tilemap.world_to_map(point) for point in world_path], straight)

    def test_authored_objects_block_diagonal_corner_and_finite_bounds(self):
        walls = LayerData(name='Walls', kind='objectgroup', properties={'collision': True},
                          objects=(MapObject(position=(16, 0), size=(16, 16)),
                                   MapObject(position=(0, 16), size=(16, 16))))
        tilemap = TileMap(MapData(size=(3, 3), layers=(walls,)))
        self.assertEqual(tilemap.find_path((0, 0), (1, 1), diagonal=True), [])
        self.assertEqual(tilemap.find_path((1, 1), (2, 2), diagonal=True), [(1, 1), (2, 2)])
        self.assertEqual(tilemap.find_path((2, 2), (3, 3)), [])

    def test_debug_shortcut_is_gated_and_overridable(self):
        game = Game()
        self.addCleanup(game.close)
        game.input.bind('game_action', Key.F3)
        press = lambda key: SimpleNamespace(type=Event.KEY_PRESSED, code=key)
        release = lambda key: SimpleNamespace(type=Event.KEY_RELEASED, code=key)
        self.assertFalse(game.handle_event(press(Key.F3)))
        self.assertTrue(game.input.is_action_pressed('game_action'))
        self.assertFalse(game.debug.visible)
        game.handle_event(release(Key.F3))

        game.debug.enabled = True
        self.assertTrue(game.handle_event(press(Key.F3)))
        self.assertFalse(game.input.is_action_pressed('game_action'))
        self.assertTrue(game.debug.visible)
        game.handle_event(press(Key.F3))
        self.assertTrue(game.debug.visible)
        game.handle_event(release(Key.F3))
        game.debug.key = Key.F8
        self.assertFalse(game.handle_event(press(Key.F3)))
        self.assertTrue(game.input.is_action_pressed('game_action'))
        self.assertTrue(game.handle_event(press(Key.F8)))
        self.assertFalse(game.debug.visible)
        game.debug.key = None
        self.assertFalse(game.handle_event(press(Key.F8)))
        self.assertTrue(game.debug.toggle())
        game.debug.enabled = False
        self.assertFalse(game.debug.visible)
        self.assertFalse(game.debug.toggle())

    def test_debug_renders_physics_and_counts_only_drawn_chunks(self):
        game = Game(size=(320, 180), debug=True)
        self.addCleanup(game.close)
        camera = game.add(Camera())
        camera.bounds = (0, 0, 2000, 1000)
        body = game.add(StaticBody(position=(155, 105), radius=12))
        body.visible = False
        tiles = TileSet(Texture.from_image(Image.create(8, 8, Color.WHITE)), tile_size=(8, 8))
        tilemap = TileMap(tile_set=tiles)
        layer = tilemap.add_layer('Terrain')
        layer.set_cell((20, 12), 0)
        layer.set_cell((120, 12), 0)
        game.add(tilemap)
        game.update(1/60)
        target = RenderTexture(320, 180)
        game.debug.toggle()
        game.debug.show_stats = False
        target.clear(Color.BLACK)
        game.render(target)
        target.display()
        self.assertEqual(game.debug.tile_chunks, 1)
        self.assertAlmostEqual(game.debug.fps, 60)
        image = target.texture.to_image()
        self.assertTrue(any(image[x, 105].g > 100 for x in range(140, 150)))
