import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from sfml.system import Vector2
from sfml.window import Event

from doku2d import DialogueBox, DialogueTree, Game, Key, analyze_dialogue
from doku2d.dialogue.preview import make_preview
from examples.gallery import DEMOS, dialogue_demo, make_demo
from examples.toolkit_demo import make_demo as make_toolkit


class BacklogExamplesTests(TestCase):
    def test_gallery_dialogue_exercises_timer_locked_response_inputs_and_call_checkpoint(self):
        game, preview = dialogue_demo()
        self.addCleanup(game.close)
        box = preview.box
        preview.play('gate')
        box.skip()
        box.update(.2)
        self.assertFalse(box.choose(0))
        saved = box.snapshot()
        self.assertAlmostEqual(saved['time_left'], 11.8)
        box.update(12)
        self.assertIn('Kapı kapandı', box.display_text)
        box.restore(preview._playable, json.loads(json.dumps(saved)), state=preview.state)
        self.assertAlmostEqual(box.time_left, 11.8)
        preview.state['has_letter'] = True
        self.assertTrue(box.choose(0))
        box.skip()
        box.update(0)
        game.flush_deferred()
        self.assertFalse(box.submit_input('1'))
        self.assertTrue(box.submit_input('42'))
        box.skip()
        self.assertFalse(box.submit_input('A'))
        self.assertTrue(box.submit_input('Ada'))
        self.assertIn('Ada', box.display_text)
        box.skip()
        box.confirm()
        self.assertEqual(box.line.speaker, 'Bekçi')
        saved = box.snapshot()
        box.close()
        box.restore(preview._playable, saved, state=preview.state)
        for _ in range(2):
            box.skip()
            box.confirm()
        self.assertIn('Tekrar hoş geldin, Ada', box.display_text)
        self.assertEqual([entry.text for entry in box.history if entry.kind == 'choice'], ['Şifreyi gir'])
        preview.toggle_history()
        self.assertTrue(preview.conversation_log.items)
        self.assertFalse(box.confirm())

    def test_inline_effects_pause_at_character_and_resume_checkpoint(self):
        game = Game()
        self.addCleanup(game.close)
        tree = DialogueTree.parse('~ start\nAyla: Ab[pause=1][shake]CD[/shake]')
        box = game.add(DialogueBox(characters_per_second=10))
        box.start(tree)
        box.update(.4)
        self.assertEqual(box.visible_text, 'Ab')
        saved = box.snapshot()
        self.assertAlmostEqual(saved['inline_wait'], .8)
        box.restore(tree, saved)
        box.update(.91)
        self.assertEqual(box.visible_text, 'AbC')
        self._render(game)

    def test_preview_graph_warning_and_automatic_reload(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.dialogue'
            path.write_text('~ start\nHi\n- Yes => END [if ready]\n~ elsewhere\nNo route there', encoding='utf-8')
            game, preview = make_preview(path)
            try:
                warnings = analyze_dialogue(preview.tree)
                self.assertEqual([(warning.section, warning.line) for warning in warnings],
                                 [('start', 3), ('elsewhere', 4)])
                preview._open_warning(0, None, 0)
                self.assertTrue(preview.box.active)
                self.assertFalse(preview.state['ready'])
                preview.toggle_graph()
                self._render(game)
                x, y, _, _ = preview.graph._rect('elsewhere')
                preview.graph._pointer_down(Vector2(x+1, y+1))
                self.assertEqual(preview.box.display_text, 'No route there')
                path.write_text('~ start\n- bad syntax', encoding='utf-8')
                preview.update(.4)
                self.assertEqual(preview.box.display_text, 'No route there')
                path.write_text('~ start\nHi\n~ elsewhere\nChanged while open', encoding='utf-8')
                preview.update(.4)
                self.assertEqual(preview.box.display_text, 'Changed while open')
            finally:
                game.close()

    def test_toolkit_exposes_input_audio_console_atlas_and_bubble(self):
        self.assertIn('Girdi, ses ve araçlar', dict(DEMOS))
        game, demo = make_toolkit()
        self.addCleanup(game.close)

        def key(code, kind=Event.KEY_PRESSED):
            game.handle_event(SimpleNamespace(type=kind, code=code))

        key(Key.D)
        self.assertTrue(game.input.is_action_pressed('move_right'))
        demo.set_context(True)
        self.assertFalse(game.input.is_action_pressed('move_right'))
        demo.set_context(False)
        self.assertFalse(game.input.is_action_pressed('move_right'))
        key(Key.D, Event.KEY_RELEASED)
        key(Key.D)
        self.assertTrue(game.input.is_action_just_pressed('move_right'))
        demo.rebind()
        self.assertEqual(game.input.binding_hint('interact'), 'F')
        game.handle_event(SimpleNamespace(type=Event.JOYSTICK_BUTTON_PRESSED, joystick_id=0, button=0))
        self.assertEqual(game.input.binding_hint('interact'), 'Gamepad 1')

        demo.announcement.play()
        game.audio._update_ducking(.18)
        self.assertAlmostEqual(game.audio.duck_gain('Music'), .28)
        demo.announcement.stop()
        game.audio._update_ducking(.65)
        self.assertEqual(game.audio.duck_gain('Music'), 1)

        key(Key.F3)
        key(Key.F4, Event.KEY_RELEASED)
        self.assertTrue(game.debug.console.opened)
        game.debug.console.execute('say "Merhaba gezgin"')
        game.update(.15)
        self.assertTrue(demo.bubble.visible)
        self.assertEqual(demo.bubble.text, 'Merhaba gezgin')
        demo.pack()
        self.assertEqual(len(demo.atlas), 3)
        self.assertTrue(all(sprite.texture is demo.atlas.texture for _, sprite in demo.previews))
        self._render(game)

    def test_new_gallery_screens_render_with_return_action(self):
        for title, factory in DEMOS[:3]:
            with self.subTest(title=title):
                game = make_demo(factory)
                try:
                    game.update(.02)
                    self._render(game)
                    self.assertTrue(any(getattr(obj, 'text', None) == 'Galeriye dön' for obj in game.objects))
                finally:
                    game.close()

    @staticmethod
    def _render(game):
        output = game.create_render_texture()
        game.render(output)
        output.display()
