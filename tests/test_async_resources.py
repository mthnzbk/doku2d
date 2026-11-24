from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sfml.graphics import Color, Image

from doku2d import Game


class AsyncResourceTests(TestCase):
    def test_ready_assets_apply_to_the_existing_cache_with_a_frame_budget(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            Image.from_size(4, 4, Color.WHITE).to_file(str(root/'tile.png'))
            (root/'data.json').write_text('{"level": 1}', encoding='utf-8')
            game = Game(asset_root=root)
            self.addCleanup(game.close)
            resources = game.resources
            resources.preloads_per_frame = 1
            request = resources.preload_async('res://tile.png', 'data.json', 'missing.txt')
            duplicate = resources.preload_async(root/'tile.png')
            self.assertEqual(len(resources._pending_preloads), 3)
            for path, (_, prepared, _) in resources._pending_preloads.items():
                # Waiting for preparation does not upload textures or populate caches.
                if path.name == 'missing.txt':
                    with self.assertRaises(FileNotFoundError):
                        prepared.result(timeout=3)
                else:
                    prepared.result(timeout=3)
            self.assertEqual(request.progress, 0)
            self.assertEqual(resources.cache_info['textures'], 0)
            game.update(0)
            self.assertTrue(duplicate.done)
            self.assertEqual(resources.cache_info['textures'], 1)
            self.assertAlmostEqual(request.progress, 1/3)
            game.update(0)
            self.assertEqual(resources.get_json('data.json'), {'level': 1})
            game.update(0)
            self.assertTrue(request.done)
            self.assertIsInstance(request.errors[root/'missing.txt'], FileNotFoundError)
            self.assertTrue(resources.preload_async('tile.png').done)

    def test_unload_retires_in_flight_work_without_repopulating_the_cache(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root/'item.txt').write_text('old', encoding='utf-8')
            game = Game(asset_root=root)
            self.addCleanup(game.close)
            resources = game.resources
            old = resources.preload_async('item.txt')
            resources.unload('item.txt')
            self.assertTrue(old.done)
            self.assertIn(root/'item.txt', old.errors)
            game.update(0)
            self.assertEqual(resources.cache_info['text'], 0)
            (root/'item.txt').write_text('new', encoding='utf-8')
            new = resources.preload_async('item.txt')
            resources._pending_preloads[root/'item.txt'][1].result(timeout=3)
            game.update(0)
            self.assertTrue(new.done)
            self.assertEqual(resources.get_text('item.txt'), 'new')
