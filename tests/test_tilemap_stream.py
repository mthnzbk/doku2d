import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, get_ident
from unittest import TestCase

from doku2d import Camera, Entity, Game, MapData, MapObject, TileMap, TileMapChunk, TileMapStream
from doku2d.rendering.tiledparser import LayerData


def region(origin, size):
    obstacle = MapObject(position=(12, 8), size=(8, 16))
    layer = LayerData(name='Wall', kind='objectgroup', objects=(obstacle,),
                      properties={'collision_enabled': True})
    visual = Entity()
    visual.position = (4, 5)
    return TileMapChunk(TileMap(MapData(size=size, layers=(layer,))), (visual,))


class TileMapStreamTests(TestCase):
    def setUp(self):
        self.game = Game()
        self.addCleanup(self.game.close)
        self.player = self.game.add(Entity())

    def test_teleport_replaces_the_regions_and_removes_old_colliders(self):
        stream = self.game.add(TileMapStream(region, size=(10_000, 10_000),
                                            target=self.player, radius=0))
        self.game.update(1/60)
        first = stream.loaded_chunks[0, 0]
        self.assertIsNotNone(self.game.physics.raycast((0, 15), (25, 15)))
        self.assertTrue(any(tuple(obj.position) == (4, 5) for obj in first.scope.members))
        self.player.position = (159_993, 159_993)
        self.game.update(1/60)
        new, = stream.loaded_chunks
        self.assertEqual(new, (312, 312))
        self.assertEqual(tuple(stream.loaded_chunks[new].map_size), (16, 16))
        self.assertIsNone(first.game)
        self.assertIsNone(self.game.physics.raycast((0, 15), (25, 15)))
        offset = 312 * 32 * 16
        self.assertIsNotNone(self.game.physics.raycast((offset, offset+15), (offset+25, offset+15)))
        self.game.remove(stream)
        self.game.flush_deferred()
        self.assertEqual(stream.loaded_chunks, {})
        self.assertIsNone(self.game.physics.raycast((offset, offset+15), (offset+25, offset+15)))

    def test_budget_and_missing_regions_are_bounded_by_the_local_window(self):
        loads = []
        self.player.position = (520, 520)

        def loader(origin, size):
            loads.append(origin)
            if origin[0] != 32:
                return TileMap(MapData(size=size))
            return None

        stream = self.game.add(TileMapStream(loader, size=(10000, 10000), target=self.player,
                                            loads_per_step=1))
        self.assertEqual(loads, [(32, 32)])
        self.game.update(1/60)
        self.assertEqual(len(loads), 2)
        stream.refresh(full=True)
        self.assertEqual(len(loads), 9)
        self.assertEqual(len(stream.loaded_chunks), 6)
        stream.refresh(full=True)
        self.assertEqual(len(loads), 9)
        self.player.position = (-1000, -1000)
        stream.refresh(full=True)
        self.assertEqual(stream.loaded_chunks, {})
        self.player.position = (520, 520)
        stream.refresh(full=True)
        self.assertEqual(len(loads), 18)

    def test_reads_local_tiled_files_without_retaining_parsed_maps(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = {'width': 32, 'height': 32, 'tilewidth': 16, 'tileheight': 16,
                    'layers': [{'name': 'Collision', 'type': 'objectgroup',
                                'properties': [{'name': 'collision_enabled', 'value': True}],
                                'objects': [{'x': 10, 'y': 4, 'width': 4, 'height': 22}]}]}
            (root/'0_0.tmj').write_text(json.dumps(data), encoding='utf-8')
            stream = self.game.add(TileMapStream.from_directory(
                root, size=(64, 32), target=self.player, radius=0))
            self.game.update(1/60)
            self.assertIsNotNone(self.game.physics.raycast((0, 15), (25, 15)))
            self.assertEqual(self.game.resources.cache_info['maps'], 0)
            self.player.position = (520, 8)
            self.game.update(1/60)
            self.assertEqual(stream.loaded_chunks, {})
            self.assertIsNone(self.game.physics.raycast((0, 15), (25, 15)))

    def test_camera_coverage_retains_visible_regions_and_fills_new_view_before_draw(self):
        self.game.size = (32, 32)
        self.player.position = (32, 32)
        camera = self.game.add(Camera())
        camera.position = (48, 32)
        stream = self.game.add(TileMapStream(region, size=(32, 4), target=self.player,
                                            chunk_size=(4, 4), radius=0, loads_per_step=1,
                                            cover_view=True))
        self.assertEqual(set(stream.loaded_chunks), {(0, 0)})

        self.player.position = (70, 32)
        self.game.update(1/60)
        self.assertEqual(set(stream.loaded_chunks), {(0, 0), (1, 0)})

        camera.position = (128, 32)
        self.game.update(0)
        self.assertIn((2, 0), stream.loaded_chunks)
        self.game.update(1/60)
        self.assertEqual(set(stream.loaded_chunks), {(1, 0), (2, 0)})

    def test_prepares_the_next_region_off_thread_before_the_target_crosses(self):
        prepared = Event()
        preparation_threads = []
        main_thread = get_ident()

        def prepare(origin, size):
            if origin == (4, 0):
                preparation_threads.append(get_ident())
                prepared.set()
            return MapData(size=size)

        def load(origin, size, data):
            self.assertEqual(get_ident(), main_thread)
            return TileMap(data)

        self.player.position = (20, 32)
        stream = self.game.add(TileMapStream(load, size=(24, 4), target=self.player,
                                            chunk_size=(4, 4), radius=0, loads_per_step=1,
                                            prepare=prepare, lookahead=3))
        self.player.position = (48, 32)
        self.game.update(1/60)
        self.assertTrue(prepared.wait(timeout=3))
        self.assertEqual(set(stream.loaded_chunks), {(0, 0)})
        self.player.position = (70, 32)
        self.game.update(1/60)
        self.assertEqual(set(stream.loaded_chunks), {(1, 0)})
        worker, = preparation_threads
        self.assertNotEqual(worker, main_thread)
