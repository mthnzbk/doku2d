from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from sfml.graphics import Color, Image, Texture
from sfml.window import Axis, Event

from doku2d import CharacterBody, Entity, Game, JoyAxis, JoyButton, Key, MapData, MouseButton, TileMap, TileSet


class PreferencesPathFollowerTests(TestCase):
    def test_player_preferences_round_trip_and_keep_game_action_flags(self):
        with TemporaryDirectory(dir=Path.cwd(), prefix='.prefs-check-') as directory:
            options = dict(save_dir=directory, persist_preferences=True)
            original = Game(**options)
            bindings = (Key.F, MouseButton(2), JoyAxis('Z', -1, .1, 2), JoyButton(4, 1))
            try:
                original.input.bind('ability', Key.E, global_action=True)
                original.input.set_bindings('ability', *bindings)
                original.input.set_bindings('jump')
                original.input.joy_deadzone = .45
                original.audio['Music'].volume = 53
                original.audio['SFX'].muted = True
                original.audio.add_bus('Ambience').volume = 37
                original.settings['checkpoint'] = 3
            finally:
                original.close()

            reopened = Game(**options)
            try:
                reopened.input.bind('ability', Key.R, global_action=True)
                self.assertEqual(reopened.input.get_bindings('ability'), bindings)
                self.assertEqual(reopened.input.get_bindings('jump'), ())
                self.assertEqual(reopened.input.joy_deadzone, .45)
                self.assertEqual(reopened.audio['Music'].volume, 53)
                self.assertTrue(reopened.audio['SFX'].muted)
                self.assertEqual(reopened.audio.add_bus('Ambience').volume, 37)
                self.assertEqual(reopened.settings['checkpoint'], 3)
                reopened.input.set_gui_captured(True)
                reopened.input.handle_event(SimpleNamespace(type=Event.KEY_PRESSED, code=Key.F))
                self.assertTrue(reopened.input.is_action_pressed('ability'))
                reopened.input.set_gui_captured(False)
                for position, active in ((40, False), (65, True)):
                    reopened.input.handle_event(SimpleNamespace(type=Event.JOYSTICK_MOVED, axis=Axis.X,
                                                                      joystick_id=0, position=position))
                    self.assertEqual(reopened.input.is_action_pressed('move_right'), active)
            finally:
                reopened.close()

    def _world(self, size):
        game = Game()
        self.addCleanup(game.close)
        tilemap = TileMap(MapData(size=size))
        tiles = TileSet(Texture.from_image(Image.create(16, 16, Color.WHITE)))
        tiles.set_solid(0)
        tilemap.add_tileset(tiles)
        layer = tilemap.add_layer('Walls')
        tilemap.enable_collisions('Walls')
        game.add(tilemap)
        npc = game.add(CharacterBody(position=tilemap.map_to_world((0, size[1]//2)), radius=3))
        return game, tilemap, layer, npc

    def test_follower_reroutes_after_an_edit_and_stops_on_arrival(self):
        game, tilemap, layer, npc = self._world((7, 3))
        goal = tilemap.map_to_world((6, 1))
        follower = npc.navigate_to(tilemap, goal, speed=75, repath_interval=.1)
        arrivals = []
        follower.arrived.connect(lambda: arrivals.append(npc.position))
        for _ in range(10):
            game.update(1/60)
        layer.set_cell((3, 1), 0)
        rows = set()
        for _ in range(210):
            game.update(1/60)
            rows.add(tilemap.world_to_map(npc.position)[1])
        self.assertEqual(follower.state, 'arrived')
        self.assertEqual(len(arrivals), 1)
        self.assertTrue(rows - {1})
        self.assertLess(abs(npc.position.x - goal.x), 1.1)
        self.assertLess(abs(npc.position.y - goal.y), 1.1)
        self.assertEqual(tuple(npc.velocity), (0, 0))

    def test_follower_waits_for_a_route_then_follows_a_moving_entity(self):
        game, tilemap, layer, npc = self._world((5, 1))
        target = game.add(Entity())
        target.position = tilemap.map_to_world((3, 0))
        layer.set_cell((1, 0), 0)
        follower = npc.navigate_to(tilemap, target, speed=65, repath_interval=.08)
        failures = []
        follower.path_failed.connect(lambda: failures.append(follower.state))
        for _ in range(20):
            game.update(1/60)
        self.assertEqual(follower.state, 'waiting')
        self.assertEqual(failures, ['waiting'])
        self.assertEqual(tuple(npc.velocity), (0, 0))
        layer.erase_cell((1, 0))
        for _ in range(15):
            game.update(1/60)
        target.position = tilemap.map_to_world((4, 0))
        for _ in range(100):
            game.update(1/60)
        self.assertEqual(follower.state, 'arrived')
        self.assertLess(abs(npc.position.x-target.position.x), 1.1)
