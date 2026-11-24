from types import SimpleNamespace
from unittest import TestCase

from sfml.graphics import Color, Image, Texture
from sfml.window import Event, Keyboard

from doku2d import Button, DragData, Game, Panel, Tree


class DragDropTests(TestCase):
    def setUp(self):
        self.game = Game(size=(320, 180))
        self.addCleanup(self.game.close)
        self.source = self.game.add(Button(text='Apple'))
        self.source.position = (10, 10)
        self.source.size = (70, 36)
        self.slot = self.game.add(Panel())
        self.slot.position = (125, 15)
        self.slot.size = (90, 50)
        image = Texture.from_image(Image.from_size(12, 16, Color.GREEN))
        self.source.drag_source = lambda point: DragData('apple', image)
        self.slot.drop_filter = lambda point, data: data == 'apple' and point.x < 50

    def pointer(self, kind, position):
        self.game.handle_event(SimpleNamespace(type=kind, position=position, button=0))

    def test_drag_highlights_the_slot_and_releases_once_without_clicking(self):
        trace = []
        self.source.pressed.connect(lambda: trace.append('click'))
        self.source.drag_started.connect(lambda data: trace.append(('start', data)))
        self.source.drag_finished.connect(lambda data, accepted: trace.append(('finish', data, accepted)))
        self.slot.dropped.connect(lambda data, point: trace.append(('drop', data, tuple(point))))
        self.pointer(Event.MOUSE_BUTTON_PRESSED, (25, 20))
        self.pointer(Event.MOUSE_MOVED, (27, 21))
        self.pointer(Event.MOUSE_BUTTON_RELEASED, (27, 21))
        self.assertEqual(trace, ['click'])
        trace.clear()

        self.pointer(Event.MOUSE_BUTTON_PRESSED, (25, 20))
        self.pointer(Event.MOUSE_MOVED, (200, 30))
        self.assertFalse(self.slot.drop_hovered)
        self.pointer(Event.MOUSE_MOVED, (140, 30))
        self.assertTrue(self.slot.drop_hovered)
        target = self.game.create_render_texture()
        target.clear(Color.BLACK)
        self.game.render(target)
        target.display()
        self.pointer(Event.MOUSE_BUTTON_RELEASED, (140, 30))
        self.assertFalse(self.slot.drop_hovered)
        self.assertEqual(trace, [('start','apple'), ('drop','apple',(15,15)), ('finish','apple',True)])

    def test_escape_and_source_removal_cancel_without_delivering_payload(self):
        finished = []
        self.source.drag_finished.connect(lambda data, accepted: finished.append(accepted))
        self.slot.dropped.connect(lambda *args: self.fail('Cancelled payload was delivered'))
        self.pointer(Event.MOUSE_BUTTON_PRESSED, (25, 20))
        self.pointer(Event.MOUSE_MOVED, (140, 30))
        self.game.handle_event(SimpleNamespace(type=Event.KEY_PRESSED, code=Keyboard.ESCAPE))
        self.pointer(Event.MOUSE_BUTTON_RELEASED, (140, 30))
        self.assertFalse(self.slot.drop_hovered)
        self.pointer(Event.MOUSE_BUTTON_PRESSED, (25, 20))
        self.pointer(Event.MOUSE_MOVED, (140, 30))
        self.game.remove(self.source)
        self.pointer(Event.MOUSE_BUTTON_RELEASED, (140, 30))
        self.assertEqual(finished, [False, False])

    def test_same_tree_can_move_an_item_including_its_child_branch(self):
        tree = self.game.add(Tree())
        tree.position = (10, 75)
        old = tree.add_item('Old parent')
        item = tree.add_item('Item', parent=old)
        leaf = tree.add_item('Leaf', parent=item)
        new = tree.add_item('New parent')
        with self.assertRaises(ValueError):
            tree.move_item(item, parent=leaf)
        tree.drag_source = tree.item_at
        tree.drop_filter = lambda point, data: tree.item_at(point) is new
        tree.dropped.connect(lambda moving, point: tree.move_item(moving, parent=tree.item_at(point)))
        self.pointer(Event.MOUSE_BUTTON_PRESSED, (65, 115))
        self.pointer(Event.MOUSE_MOVED, (65, 175))
        self.assertTrue(tree.drop_hovered)
        self.pointer(Event.MOUSE_BUTTON_RELEASED, (65, 175))
        self.assertEqual(old.children, ())
        self.assertEqual(new.children, (item,))
        self.assertEqual(item.children, (leaf,))
