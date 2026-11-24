from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from sfml.graphics import Color, Image
from sfml.window import Event, Keyboard

from doku2d import DialogueBox, DialogueFormatError, DialogueTree, Game


class DialogueTests(TestCase):
    def test_format_validates_named_targets_and_keeps_multiline_text(self):
        tree = DialogueTree.parse('~ start\nLale: Merhaba.\n| İkinci satır.\n=> end\n~ end\nGörüşürüz.')
        self.assertEqual(tree.sections['start'].lines[0].text, 'Merhaba.\nİkinci satır.')
        self.assertEqual(tree.sections['start'].next_section, 'end')
        with self.assertRaisesRegex(DialogueFormatError, r'test\.dialogue:3: Unknown section'):
            DialogueTree.parse('~ start\nLale: Merhaba.\n- Evet => missing', source='test.dialogue')

    def test_typewriter_choices_and_both_portrait_sides_in_game(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            Image.from_size(12, 8, Color.RED).to_file(str(root/'left.png'))
            Image.from_size(8, 12, Color.BLUE).to_file(str(root/'right.png'))
            (root/'test.dialogue').write_text(
                '@portrait "Liman kâtibi" left "left.png"\n'
                '@portrait Lale right "res://right.png"\n'
                '~ start\nLiman kâtibi: İskeleden geçecek misin?\nLale: Karar vermeliyim.\n'
                '- Evet => accepted\n- Hayır => END\n'
                '~ accepted\nLiman kâtibi: Yol açık.\n=> END\n', encoding='utf-8')
            with TemporaryDirectory() as saves:
                game = Game(size=(480,260), asset_root=root, save_dir=saves)
                self.addCleanup(game.close)
                panel = game.add(DialogueBox(characters_per_second=8))
                choices = []
                done = []
                panel.choice_selected.connect(lambda choice: choices.append(choice.text))
                panel.finished.connect(lambda: done.append(True))
                panel.start('res://test.dialogue')
                self.assertIs(game.ui.focus, panel)
                self.assertEqual(panel.visible_text, '')
                self.assertEqual(panel.portrait_side, 'left')
                game.update(.25)
                self.assertEqual(panel.visible_text, 'İs')
                self.assertFalse(panel.choices)
                self.assert_portrait(game, panel, Color.RED)
                self.key(game, Keyboard.RETURN)
                self.assertFalse(panel.typing)
                self.assertFalse(panel.choices)
                self.key(game, Keyboard.SPACE)
                self.assertEqual(panel.portrait_side, 'right')
                self.assert_portrait(game, panel, Color.BLUE)
                self.key(game, Keyboard.RETURN)
                self.assertEqual([option.text for option in panel.choices], ['Evet','Hayır'])
                self.click_first_choice(game, panel)
                self.assertEqual(panel.line.text, 'Yol açık.')
                self.assertEqual(choices, ['Evet'])
                panel.confirm()
                panel.confirm()
                self.assertFalse(panel.active)
                self.assertIsNone(game.ui.focus)
                self.assertEqual(done, [True])

                panel.characters_per_second = 0
                panel.start('test.dialogue')
                panel.confirm()
                self.key(game, Keyboard.DOWN, Event.KEY_PRESSED)
                self.key(game, Keyboard.RETURN)
                self.assertEqual(choices, ['Evet','Hayır'])
                self.assertFalse(panel.visible)

    @staticmethod
    def key(game, code, kind=Event.KEY_RELEASED):
        game.handle_event(SimpleNamespace(type=kind, code=code))

    @staticmethod
    def click_first_choice(game, panel):
        footer = panel._layout_boxes()[2]
        x, y = panel.position
        point = (int(x+footer[0]+8), int(y+footer[1]+8))
        for kind in (Event.MOUSE_BUTTON_PRESSED, Event.MOUSE_BUTTON_RELEASED):
            game.handle_event(SimpleNamespace(type=kind, button=0, position=point))

    def assert_portrait(self, game, panel, expected):
        surface = game.create_render_texture()
        surface.clear(Color.BLACK)
        game.render(surface)
        surface.display()
        pad, _, _, _, edge = panel._layout_boxes()
        x = pad+edge/2 if panel.portrait_side == 'left' else panel.size.x-pad-edge/2
        self.assertEqual(surface.texture.to_image()[int(panel.position.x+x), int(panel.position.y+pad+edge/2)],
                         expected)
