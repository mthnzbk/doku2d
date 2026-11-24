import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sfml.graphics import Color, Image, Texture

from doku2d import CharacterBody, Entity, Game, MapData, TileMap, TileMapStream, TileSet


class StreamNavigationTests(TestCase):
    def test_follower_crosses_regions_through_a_gap_without_loading_the_rest_of_the_map(self):
        game = Game()
        self.addCleanup(game.close)
        calls = []
        texture = Texture.from_image(Image.from_size(16, 16, Color.WHITE))

        def loader(origin, size):
            calls.append(origin)
            tilemap = TileMap(MapData(size=size))
            tiles = TileSet(texture)
            tiles.set_solid(0)
            tilemap.add_tileset(tiles)
            wall = tilemap.add_layer('Walls')
            if origin == (4, 0):
                for y in (0, 2, 3):
                    wall.set_cell((0, y), 0)
            tilemap.enable_collisions('Walls')
            return tilemap

        player = game.add(Entity())
        player.position = (8, 8)
        stream = game.add(TileMapStream(loader, size=(40, 4), target=player,
                                        chunk_size=(4, 4), radius=0, loads_per_step=1,
                                        position=(-16, -16)))
        npc = game.add(CharacterBody(position=stream.map_to_world((1, 2)), radius=3))
        path = stream.find_path((1, 2), (10, 2), radius=3)
        self.assertIn((4, 1), path)
        self.assertEqual(set(stream.loaded_chunks), {(0, 0)})
        follower = npc.navigate_to(stream, stream.map_to_world((10, 2)), speed=96)
        visited = set()
        maximum = 0
        for _ in range(200):
            game.update(1/60)
            visited.add(stream.world_to_map(npc.position))
            maximum = max(maximum, len(stream.loaded_chunks))
            if follower.state == 'arrived':
                break
        self.assertEqual(follower.state, 'arrived')
        self.assertIn((4, 1), visited)
        self.assertLessEqual(maximum, 3)
        self.assertNotIn((36, 0), calls)
        game.update(1/60)
        self.assertEqual(set(stream.loaded_chunks), {(0, 0)})

    def test_editing_loaded_navigation_layer_replans_before_taking_the_old_route(self):
        game = Game()
        self.addCleanup(game.close)
        npc = game.add(CharacterBody(position=(24, 24), radius=2))
        texture = Texture.from_image(Image.from_size(16, 16, Color.WHITE))

        def loader(origin, size):
            tilemap = TileMap(MapData(size=size))
            tilemap.add_tileset(TileSet(texture))
            tilemap.add_layer('Navigation')
            return tilemap

        stream = game.add(TileMapStream(loader, size=(12, 4), target=npc, chunk_size=(4, 4)))
        follower = npc.navigate_to(stream, stream.map_to_world((10, 1)), blocked_layers='Navigation')
        game.update(1/60)
        blocked = stream.map_to_world((4, 1))
        self.assertIn(blocked, follower.path)
        stream.loaded_chunks[1, 0].layers['Navigation'].set_cell((0, 1), 0)
        game.update(1/60)
        self.assertNotIn(blocked, follower.path)
        for _ in range(130):
            game.update(1/60)
            if follower.state == 'arrived':
                break
        self.assertEqual(follower.state, 'arrived')

    def test_tiled_navigation_can_read_unloaded_regions_and_treats_missing_ones_as_blocked(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            region = dict(width=4, height=4, tilewidth=16, tileheight=16, layers=[])
            for name in ('0_0.tmj', '1_0.tmj', '3_0.tmj'):
                (root/name).write_text(json.dumps(region), encoding='utf-8')
            game = Game(asset_root=root)
            try:
                stream = game.add(TileMapStream.from_directory('.', size=(16, 4), target=lambda:(24,24),
                                                                chunk_size=(4, 4), radius=0))
                self.assertEqual(stream.find_path((3, 1), (5, 1)), [(3, 1), (4, 1), (5, 1)])
                self.assertEqual(stream.find_path((3, 1), (13, 1)), [])
                self.assertEqual(set(stream.loaded_chunks), {(0, 0)})
                self.assertEqual(game.resources.cache_info['maps'], 0)
            finally:
                game.close()
