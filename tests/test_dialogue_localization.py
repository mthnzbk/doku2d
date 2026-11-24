from unittest import TestCase

from doku2d import DialogueBox, DialogueFormatError, DialogueTree, Game
from examples.gallery import dialogue_demo


class DialogueLocalizationTests(TestCase):
    def test_switch_locale_preserves_reveal_progress_events_and_choice_identity(self):
        game = Game(locale='tr', fallback_locale='tr')
        self.addCleanup(game.close)
        game.localization.add_catalog('en', {'meet.name': 'Hello {name}', 'meet.answer': 'Take {count}'})
        tree = DialogueTree.parse('~ start\n@event started\nAyla: [tr meet.name] Selam {name}\n'
                                  '- [tr meet.answer] {count} al => next [if ready]\n'
                                  '~ next\nAyla: {{done}} {missing} {name.__class__}')
        box = game.add(DialogueBox(characters_per_second=10))
        events, chosen = [], []
        box.event_triggered.connect(events.append)
        box.choice_selected.connect(chosen.append)
        state = {'name': 'Lale', 'count': 2, 'ready': True}
        box.start(tree, state=state)
        box.update(.5)
        self.assertEqual(box.visible_text, 'Selam')
        checkpoint = box.snapshot()
        game.locale = 'en-GB'
        self.assertEqual(box.visible_text, 'Hello')
        box.restore(tree, checkpoint, state=state)
        self.assertEqual(box.visible_text, 'Hello')
        self.assertEqual(events, ['started'])
        box.skip()
        choice, = box.choices
        self.assertEqual(box.choice_text(choice), 'Take 2')
        state['name'] = 'Deniz'
        state['count'] = 4
        self.assertEqual(box.visible_text, 'Hello Deniz')
        self.assertEqual(box.choice_text(choice), 'Take 4')
        box.choose(0)
        self.assertIs(chosen[0], choice)
        self.assertEqual(box.display_text, '{done} {missing} {name.__class__}')

    def test_parser_identifies_invalid_translation_by_source_line(self):
        with self.assertRaisesRegex(DialogueFormatError, r'demo\.dialogue:3:'):
            DialogueTree.parse('~ start\nAyla: Merhaba\n- [tr] Evet => END', source='demo.dialogue')

    def test_preview_changes_language_reports_missing_keys_and_updates_state(self):
        game, preview = dialogue_demo()
        self.addCleanup(game.close)
        self.assertEqual(preview.missing_translations, ())
        preview.play()
        preview.box.skip()
        preview.select_language(preview.languages.index('en'))
        self.assertEqual([(ref.line, ref.key) for ref in preview.missing_translations], [(26, 'harbor.archive')])
        self.assertTrue(preview.apply_values('{"player_name": "Ada", "letter_count": 3}'))
        self.assertIn('Welcome, Ada.', preview.box.visible_text)
        self.assertEqual(game.locale, 'en')
        preview.play('archive')
        self.assertIn('eksik varlık', preview.box.display_text)
        target = game.create_render_texture()
        game.render(target)
        target.display()
