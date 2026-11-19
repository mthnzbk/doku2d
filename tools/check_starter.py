"""Exercise the installed template's game state and level lifecycle."""
import importlib.util
import json
from pathlib import Path
import sys

from sfml.graphics import Color

from doku2d import Game, TileMap


def check(project):
    spec = importlib.util.spec_from_file_location('release_starter', project/'main.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    game = Game.from_project(project)
    try:
        first = game.create_scope()
        starter = first.add(module.Starter())
        game.flush_deferred()
        game.update(1/60)
        old_map = next(obj for obj in first.members if isinstance(obj, TileMap))
        assert old_map.colliders, 'Starter map has no physics geometry'

        starter.player.teleport(starter.coins[0].position)
        game.update(1/60)
        assert starter.score == 1, 'Coin collection did not update the score'
        checkpoint = tuple(starter.player.position)
        starter.save()
        starter.score = 0
        starter.player.teleport((80, 100))
        starter.load()
        game.flush_deferred()
        assert tuple(starter.player.position) == checkpoint and starter.score == 1

        for size in ((1180, 640), (600, 900)):
            target = game.create_render_texture(size)
            game.render(target)
            target.display()
            assert target.texture.to_image()[0, 0] == Color.BLACK, 'Letterbox should be black'
            point = (200, 125)
            mapped = game.window_to_screen(game.screen_to_window(point, output_size=size), output_size=size)
            assert max(abs(a-b) for a, b in zip(mapped, point)) < .01

        # Switch to an independent chapter using the template assets. Keep this
        # fixture inside the temporary project so the shipped template stays small.
        data = json.loads((project/'assets'/'level.tmj').read_text(encoding='utf-8'))
        path = project/'assets'/'release_chapter.tmj'
        path.write_text(json.dumps(data), encoding='utf-8')
        first.close()
        game.flush_deferred()
        assert old_map.game is None and starter.player.game is None and not first.members
        assert not any(getattr(obj, '_tilemap_owner', None) is old_map for obj in game.objects)
        second = game.create_scope()
        new_map = second.add(game.resources.load_map('res://release_chapter.tmj', collisions=True))
        game.flush_deferred()
        assert new_map.game is game and new_map.colliders and new_map is not old_map
        assert game.saves.load('slot1')['score'] == 1
        second.close()
        assert not game.objects
        path.unlink()
    finally:
        game.close()
    print('Starter verified: collection, save/load, resizing, and chapter lifecycle', flush=True)


if __name__ == '__main__':
    check(Path(sys.argv[1]).resolve())
