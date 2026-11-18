import inspect
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from sfml.graphics import Color, Image, RenderTexture, Texture
from sfml.system import Vector2
from sfml.window import Event, Keyboard
from doku2d import Canvas, Entity, Game
from doku2d.gui import *
from doku2d.gui.theme import measure as measure_for_test


def pointer(kind,x,y,**extra):
    return SimpleNamespace(type=kind,position=Vector2(x,y),button=0,delta=0,**extra)


def key(code,*,shift=False,control=False,release=False):
    return SimpleNamespace(type=Event.KEY_RELEASED if release else Event.KEY_PRESSED,
                           code=code,shift=shift,control=control)


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.game=Game(size=(640,480))

    def tearDown(self):
        self.game.close()

    def click(self,x,y):
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_PRESSED,x,y))
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_RELEASED,x,y))

    def test_button_signal_order_capture_and_keyboard(self):
        button=self.game.add(Button(text="Go"))
        events=[]
        button.button_down.connect(lambda:events.append("down"))
        button.button_up.connect(lambda:events.append("up"))
        button.pressed.connect(lambda:events.append("pressed"))
        self.click(20,20)
        self.assertEqual(events,["down","up","pressed"])
        events.clear()
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_PRESSED,20,20))
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_RELEASED,400,400))
        self.assertEqual(events,["down","up"])
        button.grab_focus()
        self.game.handle_event(key(Keyboard.SPACE))
        self.game.handle_event(key(Keyboard.SPACE,release=True))
        self.assertEqual(events[-3:],["down","up","pressed"])

    def test_checkbox_tab_focus_and_disabled(self):
        first=self.game.add(CheckBox(text="A"))
        second=self.game.add(Button(text="B"))
        second.position=(0,60)
        self.click(10,10)
        self.assertTrue(first.button_pressed)
        self.game.handle_event(key(Keyboard.TAB))
        self.assertIs(self.game.ui.focus,second)
        self.game.handle_event(key(Keyboard.TAB,shift=True))
        self.assertIs(self.game.ui.focus,first)
        first.disabled=True
        self.assertIsNone(self.game.ui.focus)
        self.click(10,10)
        self.assertTrue(first.button_pressed)

    def test_overlapping_control_blocks_game_input(self):
        calls=[]
        class World(Entity):
            def handle_event(self,event):calls.append(event)
        self.game.add(World())
        self.game.add(Panel())
        self.click(20,20)
        self.assertEqual(calls,[])
        self.click(300,300)
        self.assertEqual(len(calls),2)

    def test_editor_unicode_selection_limits_and_submission(self):
        editor=self.game.add(LineEdit())
        editor.max_length=8
        editor.grab_focus()
        for char in "Türkçe":
            self.game.handle_event(SimpleNamespace(type=Event.TEXT_ENTERED,unicode=ord(char)))
        self.assertEqual(editor.text,"Türkçe")
        self.game.handle_event(key(Keyboard.A,control=True))
        self.assertEqual(editor.selected_text,"Türkçe")
        self.game.handle_event(SimpleNamespace(type=Event.TEXT_ENTERED,unicode="Yeni"))
        self.assertEqual(editor.text,"Yeni")
        self.game.handle_event(key(Keyboard.BACK_SPACE))
        self.assertEqual(editor.text,"Yen")
        submitted=[]
        editor.text_submitted.connect(submitted.append)
        self.game.handle_event(key(Keyboard.RETURN))
        self.assertEqual(submitted,["Yen"])
        editor.editable=False
        self.game.handle_event(SimpleNamespace(type=Event.TEXT_ENTERED,unicode="x"))
        self.assertEqual(editor.text,"Yen")

    def test_multiline_navigation_and_render_after_edits(self):
        editor=self.game.add(TextEdit(text="first"))
        editor.grab_focus()
        self.game.handle_event(key(Keyboard.END))
        self.game.handle_event(key(Keyboard.RETURN))
        self.game.handle_event(SimpleNamespace(type=Event.TEXT_ENTERED,unicode="second"))
        self.assertEqual(editor.text,"first\nsecond")
        self.game.handle_event(key(Keyboard.HOME))
        self.game.handle_event(key(Keyboard.UP))
        self.assertEqual(editor.cursor,0)
        self.game.render(RenderTexture(640,480))

    def test_slider_drag_outside_capture_and_scroll(self):
        slider=self.game.add(Slider(min_value=0,max_value=10,step=1))
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_PRESSED,90,16))
        self.game.handle_event(pointer(Event.MOUSE_MOVED,600,16))
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_RELEASED,600,16))
        self.assertEqual(slider.value,10)
        self.assertEqual(self.game.ui.capture,{})
        self.game.handle_event(key(Keyboard.HOME))
        self.assertEqual(slider.value,0)

    def test_item_list_disabled_and_keyboard_activation(self):
        listing=self.game.add(ItemList())
        listing.items=[Item("one"),Item("disabled",disabled=True),Item("three")]
        self.click(15,15)
        self.assertEqual(listing.selected_indices,(0,))
        self.game.handle_event(key(Keyboard.DOWN))
        self.assertEqual(listing.selected_indices,(2,))
        activated=[]
        listing.item_activated.connect(activated.append)
        self.game.handle_event(key(Keyboard.RETURN))
        self.assertEqual(activated,[2])

    def test_tab_bar_and_option_popup(self):
        tabs=self.game.add(TabBar())
        tabs.size=(160,38)
        tabs.tabs=["First","Second"]
        self.click(120,15)
        self.assertEqual(tabs.current_tab,1)
        options=self.game.add(OptionButton())
        options.position=(0,60)
        options.add_item("Easy")
        options.add_item("Hard")
        self.click(20,75)
        self.assertIs(self.game.ui.popup,options)
        x,y,w,h=options._popup_rect
        self.click(x+15,y+48)
        self.assertEqual(options.selected,1)
        self.assertIsNone(self.game.ui.popup)

    def test_color_picker_changes_color(self):
        picker=self.game.add(ColorPickerButton())
        colors=[]
        picker.color_changed.connect(colors.append)
        self.click(20,15)
        x,y,_,_=picker._popup_rect
        self.click(x+42,y+25)
        self.assertEqual(picker.color.r,0)
        self.assertTrue(colors)
        self.game.handle_event(key(Keyboard.ESCAPE))
        self.assertIsNone(self.game.ui.popup)

    def test_layout_registration_expansion_and_anchor(self):
        layout=VBox()
        layout.size=(200,120)
        first=layout.add(Button(text="First"))
        first.size=(100,30)
        second=layout.add(Button(text="Second"),expand=True)
        self.game.add(layout)
        self.game.update(0)
        self.game.ui.arrange()
        self.assertEqual(tuple(first.position),(0,0))
        self.assertEqual(tuple(second.position),(0,40))
        self.assertEqual(tuple(second.size),(200,80))
        self.assertIs(first.game,self.game)
        self.game.remove(layout)
        self.game.flush_deferred()
        self.assertIsNone(first.game)
        anchored=self.game.add(Button())
        anchored.anchor=Anchor.BOTTOM_RIGHT
        self.game.ui.arrange()
        self.assertEqual(tuple(anchored.position),(480,444))
        self.game.size=(800,600)
        self.game.ui.arrange()
        self.assertEqual(tuple(anchored.position),(640,564))

    def test_touch_button_and_joystick_independent_fingers(self):
        button=self.game.add(TouchScreenButton())
        button.action="fire"
        joystick=self.game.add(VirtualJoystick())
        joystick.position=(250,0)
        self.game.handle_event(pointer(Event.TOUCH_BEGAN,20,20,finger=0))
        self.game.handle_event(pointer(Event.TOUCH_BEGAN,300,50,finger=1))
        self.assertTrue(self.game.ui.is_action_pressed("fire"))
        self.game.handle_event(pointer(Event.TOUCH_MOVED,345,50,finger=1))
        self.assertGreater(joystick.value.x,0.8)
        self.game.handle_event(pointer(Event.TOUCH_ENDED,20,20,finger=0))
        self.assertFalse(self.game.ui.is_action_pressed("fire"))
        self.assertGreater(joystick.value.x,0.8)
        self.game.handle_event(pointer(Event.TOUCH_ENDED,345,50,finger=1))
        self.assertEqual(tuple(joystick.value),(0,0))

    def test_ninepatch_pixels_preserve_corner_color(self):
        image=Image.create(6,6,Color.BLUE)
        for x in range(2):
            for y in range(2):image[x,y]=Color.RED
        panel=self.game.add(NinePatchRect())
        panel.texture=Texture.from_image(image)
        panel.patch_margin=[2,2,2,2]
        panel.size=(40,40)
        target=RenderTexture(640,480)
        target.clear(Color.BLACK)
        self.game.render(target)
        target.display()
        result=target.texture.to_image()
        self.assertEqual(result[0,0],Color.RED)
        self.assertEqual(result[20,20],Color.BLUE)

    def test_focus_and_capture_are_removed_with_control(self):
        button=self.game.add(Button())
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_PRESSED,10,10))
        self.game.remove(button)
        self.assertIsNone(self.game.ui.focus)
        self.assertEqual(self.game.ui.capture,{})

    def test_editor_undo_and_context_menu(self):
        editor=self.game.add(TextEdit(text="Original"))
        editor.grab_focus()
        editor.select_all()
        self.game.handle_event(SimpleNamespace(type=Event.TEXT_ENTERED,unicode="Updated"))
        self.game.handle_event(key(Keyboard.Z,control=True))
        self.assertEqual(editor.text,"Original")
        self.game.handle_event(key(Keyboard.Y,control=True))
        self.assertEqual(editor.text,"Updated")
        event=pointer(Event.MOUSE_BUTTON_PRESSED,20,20)
        event.button=1
        self.game.handle_event(event)
        self.assertIs(self.game.ui.popup,editor)
        self.game.handle_event(key(Keyboard.ESCAPE))
        self.assertIsNone(self.game.ui.popup)
        editor.add_gutter()
        self.game.render(RenderTexture(640,480))

    def test_rich_label_links_and_whitespace(self):
        from doku2d.gui.theme import measure
        rich=self.game.add(RichLabel(text="[b]Bold[/b] words [url=test]link[/url]"))
        rich.bbcode_enabled=True
        rich.size=(400,60)
        self.game.render(RenderTexture(640,480))
        self.assertGreater(measure(rich," "),0)
        self.assertEqual(rich._links[0][1],"test")
        clicked=[]
        rich.meta_clicked.connect(clicked.append)
        (x,y,w,h),_=rich._links[0]
        self.click(x+2,y+2)
        self.assertEqual(clicked,["test"])

    def test_clip_and_layout_visibility(self):
        from sfml.graphics import RectangleShape
        class Oversized(Control):
            def render(self,target,states):
                shape=RectangleShape((100,100))
                shape.fill_color=Color.RED
                target.draw(shape,states)
        control=self.game.add(Oversized())
        control.size=(20,20)
        target=RenderTexture(640,480)
        target.clear(Color.BLACK)
        self.game.render(target)
        target.display()
        image=target.texture.to_image()
        self.assertEqual(image[10,10],Color.RED)
        self.assertEqual(image[30,30],Color.BLACK)
        layout=VBox()
        child=layout.add(Button())
        self.game.add(layout)
        self.game.update(0)
        layout.visible=False
        self.assertFalse(child.visible)
        layout.visible=True
        self.assertTrue(child.visible)
        with self.assertRaises(ValueError):
            layout.add(layout)

    def test_password_masks_text_and_protects_copy(self):
        editor=self.game.add(LineEdit(text="secret123"))
        editor.secret=True
        self.assertEqual(editor._display(editor.text),"*********")
        self.assertEqual(editor.text,"secret123")
        editor.select_all()
        with patch("doku2d.gui.text.set_text") as copy:
            editor._copy(cut=True)
            copy.assert_not_called()
            self.assertEqual(editor.text,"secret123")
        editor.grab_focus()
        with patch("doku2d.gui.text.get_text",return_value="newpass"):
            self.game.handle_event(key(Keyboard.V,control=True))
        self.assertEqual(editor.text,"newpass")
        editor.text=""
        editor.placeholder="Password"
        text,_,_=editor._line_geometry(editor.placeholder,masked=False)
        self.assertEqual(text.string,"Password")

    def test_editor_copy_cut_paste_and_failed_clipboard(self):
        for cls in (LineEdit,TextEdit):
            with self.subTest(cls=cls.__name__):
                editor=self.game.add(cls(text="Türkçe test"))
                editor.grab_focus()
                editor.select_all()
                with patch("doku2d.gui.text.set_text",return_value=False):
                    self.game.handle_event(key(Keyboard.X,control=True))
                self.assertEqual(editor.text,"Türkçe test")
                with patch("doku2d.gui.text.set_text",return_value=True) as copy:
                    self.game.handle_event(key(Keyboard.X,control=True))
                    copy.assert_called_once_with("Türkçe test")
                self.assertEqual(editor.text,"")
                with patch("doku2d.gui.text.get_text",return_value="Türkçe test"):
                    self.game.handle_event(key(Keyboard.V,control=True))
                self.assertEqual(editor.text,"Türkçe test")
                editor.select_all()
                with patch("doku2d.gui.text.get_text",return_value=None):
                    self.game.handle_event(key(Keyboard.V,control=True))
                self.assertEqual(editor.text,"Türkçe test")
                self.game.remove(editor)

    def test_editor_text_caret_and_hit_test_share_geometry(self):
        editor=self.game.add(LineEdit(text="Agyp"))
        for height in (36,42,60):
            editor.size=(240,height)
            text,top,glyph_height=editor._line_geometry(editor.text)
            self.assertAlmostEqual(top+glyph_height/2,height/2,delta=0.5)
            baseline=text.find_character_pos(len(editor.text))
            self.assertAlmostEqual(baseline.x,10+measure_for_test(editor,editor.text))
            for index in range(len(editor.text)+1):
                point=text.find_character_pos(index)
                self.assertEqual(editor._index_at(Vector2(point.x,height/2)),index)
        editor.alignment="center"
        text,_,_=editor._line_geometry(editor.text)
        self.assertGreater(text.position.x,10)
        self.game.render(RenderTexture(640,480))

    def test_visible_glyphs_center_for_password_and_plain_text(self):
        editor=self.game.add(LineEdit())
        for value,secret in (("Hello",False),("gyp",False),("123456",True),("Agyp",False)):
            editor.text=value
            editor.secret=secret
            for height in (36,42,60):
                editor.size=(240,height)
                text,top,caret_height=editor._line_geometry(value)
                bounds=text.local_bounds
                self.assertAlmostEqual(text.position.y+bounds.position.y+bounds.size.y/2,height/2,delta=0.5)
                self.assertAlmostEqual(top+caret_height/2,height/2,delta=0.5)
        self.assertFalse(Slider().show_focus)
        self.assertFalse(CheckButton().show_focus)

    def test_textedit_both_scrollbars_drag_and_shrink(self):
        editor=self.game.add(TextEdit(text=("A long line "*30+"\n")*20))
        editor.size=(240,120)
        editor._viewport()
        self.assertTrue(editor.h_scrollbar.visible)
        self.assertTrue(editor.v_scrollbar.visible)
        bar=editor.v_scrollbar
        x,y,width,height=bar.thumb_rect()
        start=bar.position+Vector2(x+width/2,y+height/2)
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_PRESSED,start.x,start.y))
        self.game.handle_event(pointer(Event.MOUSE_MOVED,start.x,110))
        self.game.handle_event(pointer(Event.MOUSE_BUTTON_RELEASED,start.x,110))
        self.assertGreater(editor._scroll_y,0)
        self.assertEqual(self.game.ui.capture,{})
        editor.h_scrollbar.value=100
        self.assertEqual(editor._scroll_x,100)
        self.game.render(RenderTexture(640,480))
        editor.text="Short"
        editor._viewport()
        self.assertFalse(editor.h_scrollbar.visible)
        self.assertFalse(editor.v_scrollbar.visible)
        self.assertEqual(editor._scroll_x,0)
        self.assertEqual(editor._scroll_y,0)

    def test_richlabel_builtin_effects_nested_custom_and_clock(self):
        from doku2d.gui.effects import CharacterEffect,DEFAULT_EFFECTS
        self.assertEqual(set(DEFAULT_EFFECTS),{"wave","tornado","shake","rainbow","pulse"})
        for name,callback in DEFAULT_EFFECTS.items():
            first=CharacterEffect(3,0,(255,255,255,255))
            second=CharacterEffect(3,0.3,(255,255,255,255))
            callback(first,{})
            callback(second,{})
            self.assertNotEqual((tuple(first.offset),first.color),(tuple(second.offset),second.color))
        rich=self.game.add(RichLabel(text="[wave amp=3][rainbow]Motion[/rainbow][/wave] [url=target][pulse]link[/pulse][/url]"))
        rich.bbcode_enabled=True
        rich.size=(400,70)
        runs=list(rich._styled_runs())
        self.assertEqual([name for name,_ in runs[0][-1]],["wave","rainbow"])
        self.game.update(0.1)
        self.assertAlmostEqual(rich.elapsed,0.1)
        target=RenderTexture(640,480)
        self.game.render(target)
        self.assertTrue(rich._links)
        calls=[]
        def custom(character,options):
            calls.append(character.index)
            character.offset=Vector2(0,1)
        rich.install_effect("custom",custom)
        rich.text="[custom]abc[/custom]"
        self.game.render(target)
        self.assertEqual(calls,[0,1,2])
        rich.restart_effects()
        self.assertEqual(rich.elapsed,0)
        with self.assertRaises(ValueError):
            rich.install_effect("b",custom)

    def test_render_every_public_widget(self):
        import doku2d.gui as gui
        target=RenderTexture(640,480)
        for name in gui.__all__:
            cls=getattr(gui,name)
            if name in ("Anchor","Theme","Item"):continue
            with self.subTest(name=name):
                control=self.game.add(cls())
                self.game.render(target)
                self.game.remove(control)


if __name__=="__main__":unittest.main()
