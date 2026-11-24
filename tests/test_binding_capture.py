from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from sfml.window import Axis, Event

from doku2d import Entity, Game, Input, JoyAxis, JoyButton, Key, LineEdit


def key(code, *, release=False):
    return SimpleNamespace(type=Event.KEY_RELEASED if release else Event.KEY_PRESSED,
                           code=code, shift=False, control=False, alt=False, system=False)


def button(number, *, release=False, device=0):
    return SimpleNamespace(type=Event.JOYSTICK_BUTTON_RELEASED if release else Event.JOYSTICK_BUTTON_PRESSED,
                           joystick_id=device, button=number)


def axis(value, name=Axis.X, device=0):
    return SimpleNamespace(type=Event.JOYSTICK_MOVED, joystick_id=device, axis=name, position=value)


class BindingCaptureTests(TestCase):
    def test_key_replaces_binding_and_needs_a_fresh_press_after_capture(self):
        inputs = Input()
        captured = []
        inputs.capture_binding('jump', captured.append)
        self.assertEqual(inputs.binding_capture_action, 'jump')
        inputs.handle_event(key(Key.F))
        self.assertEqual(inputs.get_bindings('jump'), (Key.F,))
        self.assertEqual(captured, [Key.F])
        self.assertIsNone(inputs.binding_capture_action)
        inputs.handle_event(key(Key.F))
        self.assertFalse(inputs.is_action_pressed('jump'))
        inputs.handle_event(key(Key.F, release=True))
        inputs.handle_event(key(Key.F))
        self.assertTrue(inputs.is_action_just_pressed('jump'))

    def test_buttons_append_once_and_are_portable_across_gamepads(self):
        inputs = Input()
        original = inputs.get_bindings('jump')
        for _ in range(2):
            inputs.capture_binding('jump', append=True)
            inputs.handle_event(button(4, device=2))
            self.assertFalse(inputs.is_action_pressed('jump'))
            inputs.handle_event(button(4, release=True, device=2))
        self.assertEqual(inputs.get_bindings('jump'), (*original, JoyButton(4)))
        inputs.handle_event(button(4, device=3))
        self.assertTrue(inputs.is_action_pressed('jump'))

    def test_axis_waits_for_threshold_and_handles_nonzero_trigger_rest_position(self):
        inputs = Input()
        captured = []
        inputs.handle_event(axis(85))
        inputs.capture_binding('interact', captured.append)
        inputs.handle_event(axis(90))
        inputs.handle_event(axis(5))
        inputs.handle_event(axis(-43))
        self.assertEqual(captured, [])
        inputs.handle_event(axis(-74))
        self.assertEqual(captured, [JoyAxis(Axis.X, -1)])
        inputs.handle_event(axis(-92))
        self.assertFalse(inputs.is_action_pressed('interact'))
        inputs.handle_event(axis(0))
        inputs.handle_event(axis(-92))
        self.assertTrue(inputs.is_action_pressed('interact'))

        inputs.handle_event(axis(-100, Axis.Z))
        inputs.capture_binding('jump', captured.append)
        inputs.handle_event(axis(-99, Axis.Z))
        inputs.handle_event(axis(80, Axis.Z))
        self.assertEqual(captured[-1], JoyAxis(Axis.Z))
        inputs.handle_event(axis(-100, Axis.Z))
        inputs.handle_event(axis(85, Axis.Z))
        self.assertTrue(inputs.is_action_pressed('jump'))

    def test_held_key_and_cancel_do_not_change_bindings_or_pause_game(self):
        inputs = Input()
        original = inputs.get_bindings('jump')
        inputs.handle_event(key(Key.F))
        results = []
        inputs.capture_binding('jump', results.append)
        inputs.handle_event(key(Key.F))
        inputs.handle_event(key(Key.F, release=True))
        self.assertEqual(results, [])
        inputs.handle_event(key(Key.ESCAPE))
        self.assertFalse(inputs.is_action_just_pressed('pause'))
        self.assertEqual(inputs.get_bindings('jump'), original)
        self.assertEqual(results, [None])
        self.assertFalse(inputs.cancel_binding_capture())

    def test_game_routes_capture_before_gui_debug_and_entity_handlers(self):
        class Recorder(Entity):
            def __init__(self):
                super().__init__()
                self.events = []

            def handle_event(self, event):
                self.events.append(event.type)

        game = Game(debug=True)
        self.addCleanup(game.close)
        edit = game.add(LineEdit())
        recorder = game.add(Recorder())
        edit.grab_focus()
        game.input.capture_binding('jump')
        self.assertTrue(game.handle_event(key(Key.F3)))
        self.assertFalse(game.debug.visible)
        game.handle_event(key(Key.F3, release=True))
        game.input.capture_binding('jump')
        game.handle_event(key(Key.F))
        text = SimpleNamespace(type=Event.TEXT_ENTERED, unicode=ord('f'))
        self.assertTrue(game.handle_event(text))
        self.assertEqual(edit.text, '')
        self.assertEqual(recorder.events, [])
        game.handle_event(key(Key.F, release=True))
        game.handle_event(key(Key.G))
        game.handle_event(SimpleNamespace(type=Event.TEXT_ENTERED, unicode=ord('g')))
        self.assertEqual(edit.text, 'g')

    def test_cancel_on_lost_focus_and_restart_capture(self):
        inputs = Input()
        results = []
        inputs.capture_binding('jump', results.append)
        inputs.handle_event(SimpleNamespace(type=Event.LOST_FOCUS))
        self.assertEqual(results, [None])
        inputs.capture_binding('jump', results.append, cancel_key=None)
        inputs.handle_event(key(Key.ESCAPE))
        self.assertEqual(results[-1], Key.ESCAPE)

    def test_capture_ignores_a_debug_key_that_was_already_held(self):
        game = Game(debug=True)
        self.addCleanup(game.close)
        game.handle_event(key(Key.F3))
        self.assertTrue(game.debug.visible)
        game.input.capture_binding('jump')
        game.handle_event(key(Key.F3))
        self.assertEqual(game.input.binding_capture_action, 'jump')
        game.handle_event(key(Key.F3, release=True))
        game.input.cancel_binding_capture()
        game.handle_event(key(Key.F3))
        self.assertFalse(game.debug.visible)

    def test_captured_binding_survives_reopening_a_game(self):
        with TemporaryDirectory() as folder:
            config = dict(save_dir=Path(folder), app_id='capture', persist_preferences=True)
            game = Game(**config)
            try:
                game.input.capture_binding('jump')
                game.handle_event(button(5, device=1))
                self.assertEqual(game.input.get_bindings('jump'), (JoyButton(5),))
            finally:
                game.close()
            game = Game(**config)
            try:
                game.input.bind('jump', Key.SPACE)
                self.assertEqual(game.input.get_bindings('jump'), (JoyButton(5),))
            finally:
                game.close()
