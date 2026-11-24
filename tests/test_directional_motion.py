from unittest import TestCase

from doku2d import AnimatedSprite, CharacterBody, Game, MapData, TileMap


class DirectionalMotionTests(TestCase):
    def test_four_directions_keep_the_fractional_walk_phase_through_a_turn(self):
        sprite = AnimatedSprite()
        sprite.add_animation('idle', [0])
        sprite.add_animation('idle_east', [1])
        sprite.add_animation('run', range(4))
        sprite.add_animation('run_south', range(4), fps=8)
        sprite.add_animation('run_east', range(8), fps=20)
        body = CharacterBody()
        motion = sprite.follow_motion(body, directions=4)
        sprite.advance(0)
        self.assertEqual(motion.facing, 'south')

        body.velocity = (0, 200)
        sprite.advance(.15625)
        self.assertEqual(sprite.frame, 1)
        observed = []
        sprite.animation_changed.connect(lambda: observed.append((sprite.animation, sprite.frame)))
        body.velocity = (200, 0)
        sprite.advance(0)
        self.assertEqual(observed, [('run_east', 2)])
        sprite.advance(.024)
        self.assertEqual(sprite.frame, 2)
        sprite.advance(.002)
        self.assertEqual(sprite.frame, 3)

        body.velocity = (0, 0)
        sprite.advance(0)
        self.assertEqual((motion.facing, sprite.animation, sprite.frame), ('east', 'idle_east', 0))

    def test_eight_directions_use_authored_clips_without_mirroring(self):
        body = CharacterBody()
        sprite = AnimatedSprite()
        directions = ('east', 'south_east', 'south', 'south_west', 'west', 'north_west', 'north', 'north_east')
        velocities = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
        for direction in directions:
            sprite.add_animation(f'stand_{direction}', [0])
            sprite.add_animation(f'walk_{direction}', [0, 1])
        motion = sprite.follow_motion(body, directions=8, idle='stand', run='walk')
        for direction, velocity in zip(directions, velocities):
            body.velocity = velocity
            sprite.advance(0)
            self.assertEqual((motion.facing, sprite.animation), (direction, f'walk_{direction}'))
            self.assertFalse(sprite.flip_h)
        body.velocity = (.1, -.1)
        sprite.advance(0)
        self.assertEqual(sprite.animation, 'stand_north_east')

    def test_path_follower_drives_diagonal_animation_and_keeps_facing_on_arrival(self):
        game = Game()
        self.addCleanup(game.close)
        tilemap = game.add(TileMap(MapData(size=(5, 5))))
        npc = game.add(CharacterBody(position=tilemap.map_to_world((0, 0)), radius=3))
        sprite = npc.sprite = AnimatedSprite()
        for animation in ('idle', 'run', 'idle_south_east', 'run_south_east'):
            sprite.add_animation(animation, [0, 1])
        motion = sprite.follow_motion(npc, directions=8)
        follower = npc.navigate_to(tilemap, tilemap.map_to_world((4, 4)), diagonal=True)
        game.update(1/60)
        self.assertEqual(sprite.animation, 'run_south_east')
        for _ in range(120):
            game.update(1/60)
            if follower.state == 'arrived':
                break
        self.assertEqual(follower.state, 'arrived')
        self.assertEqual(motion.facing, 'south_east')
        self.assertEqual(sprite.animation, 'idle_south_east')
