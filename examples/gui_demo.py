"""Interactive GUI gallery: python -m examples.gui_demo [--frames 120]."""
import argparse
from sfml.graphics import Color, Image, Texture
from doku2d import Entity, Game
from doku2d.gui import (Anchor, Button, CheckBox, CheckButton, ColorPickerButton,
                        HBox, Item, ItemList, Label, LineEdit, NinePatchRect,
                        OptionButton, Panel, ProgressBar, RichLabel, ScrollBar,
                        Slider, SpinBox, TabBar, TextEdit, TextureButton,
                        TextureProgressBar, TouchScreenButton, VirtualJoystick)


def make_demo():
    game = Game(title="Doku2D | GUI", size=(1120, 790))
    game.clear_color = Color(13, 19, 30)
    pages = [[], [], [], []]

    def add(control, x, y, width, height, page=None):
        control.position = (x, y)
        control.size = (width, height)
        game.add(control)
        if page is not None:
            pages[page].append(control)
            control.visible = page == 0
        return control

    def text(value, x, y, width=450, height=26, size=15, page=None):
        item = Label(text=value)
        item.font_size = size
        return add(item, x, y, width, height, page)

    text("Doku2D", 32, 20, size=30, height=44)
    text("GUI controls", 34, 66, size=16)
    status = text("Ready. Try a control below.", 32, 744, 1056, 26)
    status.anchor = Anchor.BOTTOM_LEFT
    status.offset = (32, -20)
    tabs = add(TabBar(), 32, 112, 1056, 42)
    tabs.tabs = ["Controls", "Lists & choices", "Textures & touch", "Text effects"]
    tabs.current_tab = 0

    def select_page(index):
        for page, controls in enumerate(pages):
            for control in controls:
                control.visible = page == index
        game.ui.set_focus(None)
        status.text = "Tab / Shift+Tab move focus. Enter and Space activate buttons."

    tabs.tab_changed.connect(select_page)
    for page in range(4):
        add(Panel(), 32, 178, 510, 536, page)
        add(Panel(), 566, 178, 522, 536, page)

    # Page one: live controls and text input.
    text("Buttons & values", 54, 194, page=0, size=20)
    button = add(Button(text="Run action"), 54, 240, 210, 42, 0)
    disabled = add(Button(text="Disabled"), 280, 240, 238, 42, 0)
    disabled.disabled = True
    counter = [0]
    def clicked():
        counter[0] += 1
        status.text = f"Action called {counter[0]} times."
    button.pressed.connect(clicked)
    check = add(CheckBox(text="Enable notifications"), 54, 300, 430, 34, 0)
    switch = add(CheckButton(text="Sound effects"), 54, 348, 430, 34, 0)
    switch.button_pressed = True
    check.toggled.connect(lambda value: setattr(status, "text", f"Notifications: {value}"))
    switch.toggled.connect(lambda value: setattr(status, "text", f"Sound effects: {value}"))
    text("Volume", 54, 400, page=0)
    slider = add(Slider(value=65, step=1), 54, 434, 330, 34, 0)
    spin = add(SpinBox(value=65, step=1), 400, 432, 118, 38, 0)
    progress = add(ProgressBar(value=65, step=1), 54, 492, 464, 30, 0)
    slider.value_changed.connect(lambda value: setattr(spin, "value", value))
    spin.value_changed.connect(lambda value: setattr(slider, "value", value))
    slider.value_changed.connect(lambda value: setattr(progress, "value", value))
    text("Type a number and press Enter, or use the arrow keys.", 54, 540, 464, 44, page=0, size=13)
    text("Accent color", 54, 610, page=0)
    picker = add(ColorPickerButton(), 54, 648, 160, 38, 0)
    picker.color = Color(100, 224, 199)
    def set_accent(value):
        game.ui.theme.accent = (value.r, value.g, value.b)
        status.text = f"Accent: #{value.r:02x}{value.g:02x}{value.b:02x}"
    picker.color_changed.connect(set_accent)
    text("Text input", 590, 194, page=0, size=20)
    text("Display name", 590, 238, page=0)
    entry = add(LineEdit(), 590, 270, 472, 42, 0)
    entry.placeholder = "Write something..."
    entry.text_submitted.connect(lambda value: setattr(status, "text", f"Submitted: {value}"))
    text("Password", 590, 334, 240, page=0)
    password = add(LineEdit(text="demo1234"), 590, 366, 472, 42, 0)
    password.secret = True
    password.placeholder = "Password"
    reveal = add(CheckBox(text="Show password"), 882, 330, 180, 30, 0)
    reveal.toggled.connect(lambda visible: setattr(password, "secret", not visible))
    text("Notes", 590, 426, page=0)
    notes = add(TextEdit(text="Editable notes.\n\nUse the scrollbar on the right to explore longer text.\nThis intentionally long line demonstrates horizontal scrolling without changing the text or wrapping it to fit the field.\n\nCtrl+A selects all.\nCtrl+C / X / V copy, cut and paste.\nCtrl+Z / Y undo and redo.\n\nShift + wheel scrolls horizontally.\nBoth scrollbars adapt when you resize the control.\nYou can keep typing here."),
                590, 458, 472, 142, 0)
    text("Ctrl+A  Select all     Ctrl+C / V  Copy / paste", 590, 610, 472, 26, page=0, size=13)
    rich = add(RichLabel(text="[b]Rich text[/b] with [color=#64e0c7]color[/color], [i]italics[/i] and a [url=demo]clickable link[/url]."),
               590, 654, 472, 50, 0)
    rich.bbcode_enabled = True
    rich.meta_clicked.connect(lambda value: setattr(status, "text", f"Link signal: {value}"))

    # Page two: lists, option menus and flat layout references.
    text("Item list", 54, 194, page=1, size=20)
    listing = add(ItemList(), 54, 240, 464, 286, 1)
    listing.items = [Item("Forest"), Item("Desert"), Item("Mountains"),
                     Item("Locked area", disabled=True), Item("Coast"), Item("City")]
    listing.item_selected.connect(lambda index: setattr(status, "text", f"Selected: {listing.items[index].text}"))
    listing.item_activated.connect(lambda index: setattr(status, "text", f"Activated: {listing.items[index].text}"))
    text("Double-click or press Enter to activate an item.", 54, 542, 464, 26, page=1, size=13)
    multi = add(CheckBox(text="Multiple selection (Ctrl+click)"), 54, 590, 464, 38, 1)
    multi.toggled.connect(lambda value: setattr(listing, "select_mode", "multi" if value else "single"))
    text("Options & layout", 590, 194, page=1, size=20)
    text("Difficulty", 590, 240, page=1)
    option = add(OptionButton(), 590, 274, 472, 42, 1)
    for value in ("Story", "Normal", "Hard", "Expert"):
        option.add_item(value)
    option.item_selected.connect(lambda index: setattr(status, "text", f"Difficulty: {option.items[index].text}"))
    text("HBox shares the available width", 590, 356, page=1)
    row = HBox()
    row.spacing = 12
    for title in ("Previous", "Next", "Apply"):
        child = row.add(Button(text=title), expand=True)
        pages[1].append(child)
        child.visible = False
        child.pressed.connect(lambda value=title: setattr(status, "text", f"Layout button: {value}"))
    add(row, 590, 398, 472, 42, 1)
    text("Scroll bar", 590, 494, page=1)
    scroll = add(ScrollBar(value=30, step=1), 590, 534, 472, 22, 1)
    scroll.scrolling.connect(lambda: setattr(status, "text", f"Scroll position: {scroll.value:g}"))
    text("The controls are independent entities.\nLayouts only calculate their positions.".replace("\\n", "\n"),
         590, 598, 472, 72, page=1)

    # Page three: generated textures, nine-patch scaling and touch input.
    text("Texture controls", 54, 194, page=2, size=20)
    image = Image.create(24, 24, Color(36, 69, 84))
    for x in range(24):
        for y in range(24):
            if x < 5 or x >= 19 or y < 5 or y >= 19:
                image[x, y] = Color(100, 224, 199)
    frame = add(NinePatchRect(), 54, 240, 464, 132, 2)
    frame.texture = Texture.from_image(image)
    frame.patch_margin = [5, 5, 5, 5]
    text("NinePatchRect preserves border thickness", 70, 286, 430, 26, page=2)
    texture_button = add(TextureButton(), 54, 412, 210, 48, 2)
    texture_button.texture_normal = Texture.from_image(Image.create(64, 24, Color(36, 104, 119)))
    texture_button.texture_hover = Texture.from_image(Image.create(64, 24, Color(64, 145, 153)))
    texture_button.texture_pressed = Texture.from_image(Image.create(64, 24, Color(100, 224, 199)))
    texture_button.pressed.connect(lambda: setattr(status, "text", "Texture button pressed"))
    text("TextureButton", 280, 422, 220, 28, page=2)
    textured_progress = add(TextureProgressBar(value=72), 54, 514, 464, 30, 2)
    textured_progress.texture_under = Texture.from_image(Image.create(16, 16, Color(16, 27, 41)))
    textured_progress.texture_progress = Texture.from_image(Image.create(16, 16, Color(70, 177, 160)))
    text("TextureProgressBar", 54, 562, page=2)
    text("Touch input", 590, 194, page=2, size=20)
    text("Drag the joystick with a mouse or a touch pointer.", 590, 238, 472, 44, page=2)
    joystick = add(VirtualJoystick(), 638, 308, 160, 160, 2)
    joystick.joystick_size = 160
    joystick.tip_size = 58
    value_label = text("X 0.00   Y 0.00", 590, 510, page=2)
    joystick.moved.connect(lambda value: setattr(value_label, "text", f"X {value.x:.2f}   Y {value.y:.2f}"))
    touch = add(TouchScreenButton(), 886, 350, 130, 64, 2)
    touch.text = "FIRE"
    touch.action = "fire"
    touch.pressed.connect(lambda: setattr(status, "text", "Virtual fire action: pressed"))
    touch.released.connect(lambda: setattr(status, "text", "Virtual fire action: released"))
    text("TouchScreenButton", 854, 438, 200, 30, page=2)
    # Page four: the five built-in character effects and nested formatting.
    text("Animated text", 54, 194, page=3, size=20)
    presets = [
        ("Wave", "[wave amp=4 freq=1.3]A little motion goes a long way.[/wave]"),
        ("Tornado", "[tornado radius=3 freq=0.7]Letters moving in orbit.[/tornado]"),
        ("Shake", "[shake rate=16 level=1.8]Something is about to happen![/shake]"),
        ("Rainbow", "[rainbow speed=0.16 sat=0.55]A spectrum of possibilities.[/rainbow]"),
        ("Pulse", "[pulse freq=0.8]Waiting for your next move...[/pulse]"),
    ]
    for index, (name, markup) in enumerate(presets):
        y = 240+index*88
        text(name, 54, y, 464, 24, size=13, page=3)
        effect = RichLabel(text=markup)
        effect.bbcode_enabled = True
        effect.font_size = 20
        add(effect, 54, y+28, 464, 44, 3)
    text("Combine & customize", 590, 194, page=3, size=20)
    combined = RichLabel(text="[wave amp=3 freq=1][rainbow speed=0.12][b]Your text, brought to life.[/b][/rainbow][/wave]")
    combined.bbcode_enabled = True
    combined.font_size = 24
    add(combined, 590, 248, 472, 68, 3)
    text("Nest tags to combine effects", 590, 346, page=3)
    snippet = add(LineEdit(text="[wave][rainbow]Hello![/rainbow][/wave]"),590,388,472,42,3)
    snippet.editable = False
    text("Formatting and links keep working.\nEach label has its own animation clock.",
         590, 454, 472, 76, page=3)
    replay = add(Button(text="Restart animations"),590,574,234,42,3)
    def restart_effects():
        for control in pages[3]:
            if isinstance(control,RichLabel):
                control.restart_effects()
    replay.pressed.connect(restart_effects)
    text("Custom effects use install_effect(name, callback).",590,642,472,44,size=13,page=3)

    game.flush_deferred()
    return game


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=None)
    args = parser.parse_args()
    make_demo().run(max_frames=args.frames)
