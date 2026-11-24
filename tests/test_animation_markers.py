from unittest import TestCase

from doku2d import AnimatedSprite, CharacterBody


class AnimationMarkerTests(TestCase):
    def test_catch_up_emits_each_crossed_marker_and_loop_in_order(self):
        sprite = AnimatedSprite()
        sprite.add_animation('walk', [0, 1, 2, 3], fps=10,
                             markers={0:'start', 1:('step', 'dust'), 3:'step'})
        emitted = []
        sprite.marker_reached.connect(lambda *event: emitted.append(event))
        sprite.play('walk')
        sprite.play('walk')
        sprite.advance(.51)
        self.assertEqual(emitted, [('start','walk',0), ('step','walk',1), ('dust','walk',1),
                                   ('step','walk',3), ('start','walk',0),
                                   ('step','walk',1), ('dust','walk',1)])
        sprite.pause()
        sprite.play()
        self.assertEqual(len(emitted), 7)
        sprite.stop()
        sprite.play()
        self.assertEqual(emitted[-1], ('start','walk',0))

    def test_direction_change_does_not_repeat_the_current_footstep(self):
        sprite = AnimatedSprite()
        sprite.add_animation('idle', [0])
        sprite.add_animation('run', range(4), fps=10)
        for direction in ('east','south'):
            sprite.add_animation(f'run_{direction}', range(4), fps=10, markers={1:'step', 3:'step'})
        body = CharacterBody()
        sprite.follow_motion(body, directions=4)
        emitted = []
        sprite.marker_reached.connect(lambda *event: emitted.append(event))
        body.velocity = (0,200)
        sprite.advance(.12)
        body.velocity = (200,0)
        sprite.advance(0)
        self.assertEqual(emitted, [('step','run_south',1)])
        sprite.advance(.20)
        self.assertEqual(emitted[-1], ('step','run_east',3))

    def test_reverse_playback_emits_markers_at_entered_frames(self):
        sprite = AnimatedSprite()
        sprite.add_animation('reverse', [0,1,2], fps=10, loop=False,
                             markers={0:'end', 1:'middle', 2:'start'})
        emitted = []
        sprite.marker_reached.connect(lambda marker, *_: emitted.append(marker))
        sprite.play('reverse', speed=-1, from_end=True)
        sprite.advance(.4)
        self.assertEqual(emitted, ['start','middle','end'])
