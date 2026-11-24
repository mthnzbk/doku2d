from time import monotonic, sleep
from types import SimpleNamespace
from unittest import TestCase

from sfml.system import Vector2
from sfml.window import Event, Keyboard

from doku2d import Button
from examples import engine_demo
from examples.gallery import DEMOS, dialogue_demo, make_demo, make_gallery


class RecentGalleryExamplesTests(TestCase):
    def test_gallery_opens_both_new_examples_with_return_buttons(self):
        game, gallery = make_gallery()
        self.addCleanup(game.close)
        for title, factory in DEMOS[:2]:
            button = next(item for item in game.objects if isinstance(item, Button) and item.text == title)
            button.pressed.emit()
            self.assertIs(gallery.selection, factory)
            example = make_demo(factory)
            try:
                self.assertTrue(any(isinstance(item, Button) and item.text == 'Galeriye dön'
                                    for item in example.objects))
                example.update(1/60)
                target = example.create_render_texture()
                example.render(target)
                target.display()
            finally:
                example.close()

    def test_dialogue_preview_handles_missing_assets_flags_and_resume(self):
        game, demo = dialogue_demo()
        self.addCleanup(game.close)
        self.assertEqual([(ref.line, ref.path) for ref in demo.missing],
                         [(4, 'portraits/missing.png'), (27, 'voices/missing.ogg')])
        self.assertEqual(demo.sections.selected.data, 'start')
        demo.play()
        self.assertEqual(demo.box.portrait_side, 'left')
        demo.box.skip()
        self.assertEqual(len(demo.box.choices), 1)
        flag = demo.flags.index('has_letter')
        demo.flag_list.select(flag)
        demo.flag_list.grab_focus()
        game.handle_event(SimpleNamespace(type=Event.KEY_PRESSED, code=Keyboard.SPACE))
        self.assertEqual(len(demo.box.choices), 2)
        demo.box.choose(0)
        self.assertEqual(demo.box.line.expression, 'relieved')
        demo.save_checkpoint()
        demo.play('archive')
        self.assertIsNone(demo.box.line.voice)
        self.assertIsNone(demo.box.portrait_side)
        demo.resume_checkpoint()
        self.assertEqual(demo.box.line.expression, 'relieved')
        self.assertTrue(demo.state['has_letter'])

    def test_workshop_moves_tasks_follows_route_and_replaces_room(self):
        game, demo = engine_demo.make_demo()
        self.addCleanup(game.close)
        waiting, done = demo.tree.roots
        task = waiting.children[0]
        source = Vector2(58, 45)
        destination = Vector2(58, 135)
        self.assertIs(demo.tree.get_drag_data(source).data, task)
        self.assertTrue(demo.tree.can_drop_data(destination, task))
        demo.tree.drop_data(destination, task)
        self.assertEqual(done.children, (task,))

        demo.navigate((14, 7))
        visited = set()
        for _ in range(450):
            game.update(1/60)
            visited.add(demo.stream.world_to_map(demo.actor.position))
            if demo.follower.state == 'arrived':
                break
        self.assertEqual(demo.follower.state, 'arrived')
        self.assertTrue(visited.intersection({(8, 4), (8, 5)}))
        self.assertGreater(demo.steps, 0)

        old_room = demo.room_scope
        demo.change_room()
        deadline = monotonic()+3
        while demo.transition_button.disabled and monotonic() < deadline:
            game.update(1/60)
            sleep(.001)
        self.assertEqual(demo.room, 1)
        self.assertTrue(old_room.closed)
        self.assertIsNot(demo.room_scope, old_room)
        self.assertEqual(done.children, (task,))
