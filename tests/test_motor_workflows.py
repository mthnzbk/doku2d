from pathlib import Path
from tempfile import TemporaryDirectory
from threading import get_ident
from types import SimpleNamespace
from unittest import TestCase

from sfml.window import Event, Keyboard

from doku2d import Camera, Canvas, DialogueBox, DialogueTree, Entity, Game, Tree


class MotorWorkflowTests(TestCase):
    def test_dialogue_flags_filter_choices_and_events_change_the_next_branch(self):
        game = Game()
        self.addCleanup(game.close)
        panel = game.add(DialogueBox(characters_per_second=0))
        tree = DialogueTree.parse(
            '~ start\nAyla: Mektubu getirdin mi?\n'
            '- Teslim et => delivered [if has_letter]\n- Geri dön => END [if not has_letter]\n'
            '~ delivered\nAyla: Teşekkürler.\n@event letter_delivered\n'
            '=> reward [if delivered]\n=> END\n~ reward\nAyla: Bu ödül senin.\n')
        state = {}
        events = []

        def receive(name):
            events.append(name)
            state['delivered'] = True

        panel.event_triggered.connect(receive)
        panel.start(tree, state=state)
        self.assertEqual([item.text for item in panel.choices], ['Geri dön'])
        state['has_letter'] = True
        self.assertEqual([item.text for item in panel.choices], ['Teslim et'])
        panel.choose(0)
        self.assertEqual(events, [])
        panel.confirm()
        self.assertEqual(events, ['letter_delivered'])
        self.assertEqual(panel.line.text, 'Bu ödül senin.')
        panel.confirm()
        self.assertFalse(panel.active)

    def test_tree_keyboard_navigation_and_collapse_keep_selection_visible(self):
        game = Game(size=(320,240))
        self.addCleanup(game.close)
        tree = game.add(Tree())
        folder = tree.add_item('Görevler', expanded=False)
        quest = tree.add_item('İlk görev', parent=folder, data=5)
        tree.grab_focus()
        activated = []
        tree.item_activated.connect(activated.append)

        def press(code):
            game.handle_event(SimpleNamespace(type=Event.KEY_PRESSED, code=code))

        press(Keyboard.DOWN)
        press(Keyboard.RIGHT)
        self.assertTrue(folder.expanded)
        press(Keyboard.RIGHT)
        self.assertIs(tree.selected, quest)
        press(Keyboard.RETURN)
        self.assertEqual(activated, [quest])
        self.assertEqual(activated[0].data, 5)
        tree.set_expanded(folder, False)
        self.assertIs(tree.selected, folder)
        surface = game.create_render_texture()
        game.render(surface)
        surface.display()

    def test_y_sort_uses_depth_anchors_and_preserves_manual_layers(self):
        game = Game()
        self.addCleanup(game.close)
        world = Canvas(y_sort=True)
        tree = game.add(Entity('Tree'), canvas=world)
        tree.position = (0,10)
        tree.y_sort_offset = 60
        player = game.add(Entity('Player'), canvas=world)
        player.position = (0,66)
        decal = game.add(Entity('Decal'), canvas=world)
        decal.z_index = -1
        decal.position = (0,500)
        self.assertEqual(game.draw_list(), [decal,player,tree])
        player.position = (0,71)
        self.assertEqual(game.draw_list(), [decal,tree,player])
        world.y_sort = False
        player.position = (0,0)
        self.assertEqual(game.draw_list(), [decal,tree,player])

    def test_transition_waits_for_preparation_and_replaces_only_the_selected_scope(self):
        with TemporaryDirectory() as directory:
            path = Path(directory).resolve()
            (path/'data.txt').write_text('ready')
            game = Game(asset_root=path)
            self.addCleanup(game.close)
            old = game.create_scope()
            old.add(Entity('Old'))
            previous_camera = old.add(Camera())
            other = game.add(Entity('Keep'))
            owner = get_ident()
            completed = []

            def build(scope, worker):
                self.assertNotEqual(worker, owner)
                self.assertEqual(get_ident(), owner)
                self.assertEqual(game.resources.get_text('data.txt'), 'ready')
                scope.add(Entity('New'))
                scope.add(Camera('New Camera'))

            transition = game.transition(build, old_scope=old, prepare=get_ident,
                                         preload='data.txt', fade_out=0, fade_in=0)
            transition.finished.connect(completed.append)
            transition._future.result(timeout=3)
            game.resources._pending_preloads[path/'data.txt'][1].result(timeout=3)
            game.update(0)
            self.assertFalse(old.closed)
            self.assertTrue(game.paused)
            self.assertIs(game.camera, previous_camera)
            game.update(0)
            self.assertTrue(old.closed)
            game.update(0)
            self.assertEqual(completed, [transition.new_scope])
            self.assertEqual([item.name for item in transition.new_scope.members], ['New','New Camera'])
            self.assertEqual(game.camera.name, 'New Camera')
            self.assertIn(other, game.objects)
            self.assertFalse(game.paused)

    def test_transition_builder_failure_removes_new_objects_and_restores_old_scope(self):
        game = Game()
        self.addCleanup(game.close)
        old = game.create_scope()
        previous = old.add(Entity('Previous'))

        def build(scope):
            scope.add(Entity('Incomplete'))
            raise RuntimeError('incomplete level')

        transition = game.transition(build, old_scope=old, fade_out=0, fade_in=0)
        failed = []
        transition.failed.connect(failed.append)
        for _ in range(3):
            game.update(0)
        self.assertEqual([str(error) for error in failed], ['incomplete level'])
        self.assertEqual(game.objects, (previous,))
        self.assertFalse(old.closed)
        self.assertFalse(game.paused)
