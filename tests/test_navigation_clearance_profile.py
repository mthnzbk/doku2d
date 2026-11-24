from unittest import TestCase
from unittest.mock import Mock, patch

from sfml.graphics import RenderTexture

from doku2d import AnimatableBody, Area, CharacterBody, Entity, Game, MapData, TileMap, TileSet


class ClearanceAndProfileTests(TestCase):
    def test_body_size_selects_the_wide_passage(self):
        tilemap = TileMap(MapData(size=(9, 9)))
        tiles = TileSet('not-loaded.png')
        tiles.set_solid(0)
        tilemap.add_tileset(tiles)
        layer = tilemap.add_layer('Walls')
        for y in (0, 1, 3, 4, 8):
            layer.set_cell((4, y), 0)

        small = CharacterBody(radius=5)
        large = CharacterBody(radius=9)
        start, goal = (2, 2), (6, 2)
        self.assertIn((4, 2), tilemap.find_path(start, goal, agent=small))
        wide_route = tilemap.find_path(start, goal, agent=large)
        self.assertTrue(wide_route)
        self.assertNotIn((4, 2), wide_route)
        self.assertTrue(any(x == 4 and 5 <= y <= 7 for x, y in wide_route))
        self.assertEqual(tilemap.find_path(start, goal, agent=large, bounds=(0, 0, 9, 5)), [])

    def test_follower_avoids_a_body_that_steps_into_its_route(self):
        game = Game()
        self.addCleanup(game.close)
        tilemap = game.add(TileMap(MapData(size=(10, 6))))
        npc = game.add(CharacterBody(position=tilemap.map_to_world((1, 2)), radius=4))
        mover = game.add(AnimatableBody(position=tilemap.map_to_world((4, 4)), radius=7))
        game.add(Area(position=tilemap.map_to_world((2, 2)), radius=8))
        goal = tilemap.map_to_world((8, 2))
        follower = npc.navigate_to(tilemap, goal, speed=60, repath_interval=.12)
        for _ in range(12):
            game.update(1/60)
        self.assertTrue(all(tilemap.world_to_map(point)[1] == 2 for point in follower.path))

        mover.position = tilemap.map_to_world((4, 2))
        rows = set()
        for _ in range(195):
            game.update(1/60)
            rows.add(tilemap.world_to_map(npc.position)[1])
        self.assertTrue(rows - {2})
        self.assertEqual(follower.state, 'arrived')
        self.assertEqual(tuple(npc.velocity), (0, 0))

    def test_mover_collision_masks_and_stopping_near_a_solid_target(self):
        game = Game()
        self.addCleanup(game.close)
        tilemap = game.add(TileMap(MapData(size=(8, 1))))
        npc = game.add(CharacterBody(position=tilemap.map_to_world((0, 0)), radius=3))
        npc.collision_mask = 1
        target = game.add(AnimatableBody(position=tilemap.map_to_world((6, 0)), radius=5))
        excluded = game.add(AnimatableBody(position=tilemap.map_to_world((2, 0)), radius=6))
        excluded.collision_layer = 2
        game.update(1/60)
        self.assertTrue(tilemap.find_path((0, 0), (4, 0), agent=npc))
        excluded.collision_layer = 1
        game.update(1/60)
        self.assertEqual(tilemap.find_path((0, 0), (4, 0), agent=npc), [])
        game.remove(excluded)
        follower = npc.navigate_to(tilemap, target, speed=90)
        for _ in range(130):
            game.update(1/60)
        self.assertEqual(follower.state, 'arrived')
        self.assertGreaterEqual(target.position.x - npc.position.x, 7.9)
        self.assertLessEqual(target.position.x - npc.position.x, 9)

    def test_profiler_separates_nested_navigation_and_stays_off_in_release(self):
        game = Game(size=(320, 180), debug=True)
        self.addCleanup(game.close)
        game.debug.visible = True
        tilemap = game.add(TileMap(MapData(size=(3, 3))))

        class QueryDuringPhysics(Entity):
            def physics_update(self, dt):
                tilemap.find_path((0, 0), (1, 0))

        game.add(QueryDuringPhysics())
        target = RenderTexture(*game.size)
        with patch('doku2d.core.debug.perf_counter', side_effect=(0, .001, .004, .010, .010, .016, .017, .020)):
            game.update(1/60)
            game.render(target)
        self.assertEqual(game.debug.path_queries, 1)
        for section, expected in dict(physics=7, update=6, render=3, navigation=3).items():
            self.assertAlmostEqual(game.debug.profile_ms[section], expected)

        game.debug.enabled = False
        with patch('doku2d.core.debug.perf_counter', side_effect=AssertionError('release should not use timers')):
            game.update(1/60)
            game.render(target)
        self.assertEqual(game.debug.path_queries, 0)
        self.assertFalse(any(game.debug.profile_ms.values()))

    def test_window_profile_publishes_polling_rendering_and_presentation_together(self):
        game = Game(size=(320, 180), debug=True)
        window = Mock(is_open=True, events=())
        clock = Mock()
        clock.restart.return_value.seconds = .012
        window.display.side_effect = lambda: self.assertEqual(game.debug.profile_ms['render'], 0)
        ticks = (0, .002, .002, .005, .005, .008, .008, .019)
        with (patch('doku2d.rendering.targets.MeasuredWindow', return_value=window),
              patch('doku2d.core.game.Clock', return_value=clock),
              patch('doku2d.core.debug.perf_counter', side_effect=ticks),
              patch.object(game, '_render_frame')):
            game.run(max_frames=1)
        for section, elapsed in {'events': 2, 'update': 3, 'render': 3, 'present': 11}.items():
            self.assertAlmostEqual(game.debug.profile_ms[section], elapsed)
        self.assertAlmostEqual(game.debug.peak_frame_ms, 12)
        game.debug.show_profile = False
        self.assertEqual(game.debug.peak_frame_ms, 0)
