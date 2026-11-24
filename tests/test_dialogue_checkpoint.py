from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import PropertyMock, patch
import wave

from sfml.graphics import Color, Image

from doku2d import AudioPlayer, DialogueBox, DialogueTree, Game


class DialogueCheckpointTests(TestCase):
    def test_saved_typewriter_progress_does_not_replay_passed_events(self):
        tree = DialogueTree.parse(
            '~ start\n@event started\nLale: Mektubu bıraktım.\n@event delivered\n'
            'Lale: Rüzgâr çıkıyor.\n@event leaving')
        with TemporaryDirectory() as directory:
            game = Game(save_dir=directory)
            try:
                box = game.add(DialogueBox(characters_per_second=10))
                events = []
                box.event_triggered.connect(events.append)
                box.start(tree)
                box.confirm()
                box.confirm()
                game.update(.25)
                self.assertEqual(box.visible_text, 'Rü')
                game.saves.save('scene', {'dialogue':box.snapshot()})
            finally:
                game.close()
            self.assertEqual(events, ['started','delivered'])

            game = Game(save_dir=directory)
            try:
                box = game.add(DialogueBox(characters_per_second=10))
                resumed = []
                box.event_triggered.connect(resumed.append)
                box.restore(tree, game.saves.load('scene')['dialogue'])
                self.assertEqual(box.visible_text, 'Rü')
                game.update(.05)
                self.assertEqual(box.visible_text, 'Rüz')
                box.confirm()
                box.confirm()
                self.assertEqual(resumed, ['leaving'])
                self.assertFalse(box.active)
            finally:
                game.close()

    def test_restore_during_resolved_choice_continues_without_repeating_side_effects(self):
        game = Game()
        self.addCleanup(game.close)
        tree = DialogueTree.parse(
            '~ start\nAyla: Mektup sende mi?\n@event reward\n@event note\n'
            '- Evet => next\n~ next\nAyla: Teşekkür ederim.')
        box = game.add(DialogueBox(characters_per_second=0))
        box.start(tree)
        snapshots = []
        box.event_triggered.connect(lambda name: snapshots.append(box.snapshot()) if name == 'reward' else None)
        box.choose(0)
        self.assertEqual(box.line.text, 'Teşekkür ederim.')
        box.close()

        choices, events = [], []
        box.choice_selected.connect(choices.append)
        box.event_triggered.connect(events.append)
        box.restore(tree, snapshots[0])
        self.assertEqual(box.line.text, 'Mektup sende mi?')
        game.update(0)
        self.assertEqual(box.line.text, 'Teşekkür ederim.')
        self.assertEqual(choices, [])
        self.assertEqual(events, ['note'])

    def test_expression_delay_and_voice_resume_use_the_original_cue(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            Image.from_size(12, 12, Color.RED).to_file(str(root/'idle.png'))
            Image.from_size(12, 12, Color.BLUE).to_file(str(root/'relieved.png'))
            with wave.open(str(root/'voice.wav'), 'wb') as sound:
                sound.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
                sound.writeframes(b'\x00\x00' * 8000)
            (root/'scene.dialogue').write_text(
                '@portrait Ayla left "idle.png"\n'
                '@portrait Ayla right "relieved.png" relieved\n'
                '~ start\nAyla: Buradayım.\n'
                '@expression relieved\n@pause 0.5\n@voice "voice.wav"\n'
                '| Kapıyı kapatma.\nAyla: Hoşça kal.', encoding='utf-8')
            game = Game(asset_root=root)
            try:
                box = game.add(DialogueBox(characters_per_second=10))
                with (patch.object(AudioPlayer, 'play', autospec=True) as play,
                      patch.object(AudioPlayer, 'playing', new_callable=PropertyMock, return_value=True),
                      patch.object(AudioPlayer, 'get_playback_position', return_value=.2)):
                    box.start('scene.dialogue')
                    self.assertEqual(box.portrait_side, 'right')
                    self.assertEqual(box.line.expression, 'relieved')
                    self.assertIn('\nKapıyı kapatma.', box.line.text)
                    game.update(.25)
                    self.assertEqual(box.visible_text, '')
                    self.assertFalse(play.called)
                    checkpoint = box.snapshot()
                    box.restore('scene.dialogue', checkpoint)
                    game.update(.25)
                    play.assert_called_once_with(box._voice_player, 0.0)
                    game.update(.2)
                    self.assertEqual(box.visible_text, 'Bu')
                    checkpoint = box.snapshot()
                    self.assertEqual(checkpoint['voice_position'], .2)
                    box.restore('scene.dialogue', checkpoint)
                    self.assertEqual(box.visible_text, 'Bu')
                    play.assert_called_with(box._voice_player, .2)
                    box.confirm()
                    box.confirm()
                    self.assertEqual(box.portrait_side, 'left')
                    player = box._voice_player
                    game.remove(box)
                    game.flush_deferred()
                    self.assertIsNone(player.game)
            finally:
                game.close()
