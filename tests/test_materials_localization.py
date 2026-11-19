from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sfml.graphics import Color, Image, RenderTexture, Texture

from doku2d import AmbientLight, Button, CanvasGroup, Game, HBox, Label, LineEdit, OptionButton
from doku2d import RichLabel, ShaderMaterial, Sprite, tr


FRAGMENT = '''
uniform sampler2D u_texture;
uniform vec4 tint;
void main() {
    gl_FragColor = texture2D(u_texture, gl_TexCoord[0].xy) * gl_Color * tint;
}
'''


def frame(game):
    target = RenderTexture(*game.size)
    target.clear(Color.BLACK)
    game.render(target)
    target.display()
    return target.texture.to_image()


def square(color):
    sprite = Sprite(Texture.from_image(Image.create(12, 12, color)))
    sprite.centered = False
    return sprite


class MaterialsLocalizationTests(TestCase):
    def test_shader_file_and_independent_parameters_on_sprites(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            game = Game(size=(36, 12), asset_root=directory)
            self.addCleanup(game.close)
            Path(directory, 'tint.frag').write_text(FRAGMENT, encoding='utf-8')
            first, second = game.add(square(Color.WHITE)), game.add(square(Color.WHITE))
            second.position = (14, 0)
            first.material = ShaderMaterial('res://tint.frag').set_shader_parameter('tint', Color.RED)
            second.material = ShaderMaterial('res://tint.frag').set_shader_parameter('tint', Color.GREEN)
            image = frame(game)
            self.assertEqual(image[5, 5], Color.RED)
            self.assertEqual(image[18, 5], Color.GREEN)
            first.material.set_shader_parameter('tint', Color.BLUE)
            image = frame(game)
            self.assertEqual(image[5, 5], Color.BLUE)
            self.assertEqual(image[18, 5], Color.GREEN)

    def test_group_and_world_effects_preserve_alpha_and_leave_hud_separate(self):
        game = Game(size=(36, 24))
        self.addCleanup(game.close)
        group = game.add(CanvasGroup(opacity=.5))
        group.add(square(Color.WHITE))
        group.add(square(Color.WHITE))
        group.material = ShaderMaterial.from_source(FRAGMENT).set_shader_parameter('tint', Color.YELLOW)
        game.world.material = ShaderMaterial.from_source(FRAGMENT).set_shader_parameter('tint', Color.GREEN)
        game.add(AmbientLight(color=(128, 128, 128)))
        hud = game.add(square(Color.RED), canvas=game.ui.canvas)
        hud.position = (22, 0)
        image = frame(game)
        self.assertAlmostEqual(image[5, 5].g, 64, delta=2)
        self.assertEqual(image[5, 5].r, 0)
        self.assertEqual(image[17, 5], Color.BLACK)
        self.assertEqual(image[25, 5], Color.RED)
        self.assertEqual(image[5, 18], Color.BLACK)

    def test_live_locale_updates_captions_and_width_without_touching_input(self):
        game = Game(size=(480, 150))
        self.addCleanup(game.close)
        game.localization.add_catalog('en', {'save': 'Save', 'hint': 'Type here', 'count': '{n} coins'})
        game.localization.add_catalog('tr', {'save': 'Değişiklikleri kaydet', 'hint': 'Buraya yaz', 'count': '{n} para'})
        layout = game.add(HBox())
        layout.size = (440, 42)
        button = layout.add(Button(text=tr('save'), fit_text=True))
        adjacent = layout.add(Label(text=tr('count', n=2)))
        entry = game.add(LineEdit(text='save'))
        entry.placeholder = tr('hint')
        rich = game.add(RichLabel(text=tr('missing', default='[b]Fallback[/b]')))
        option = game.add(OptionButton())
        option.add_item(tr('save'))
        option.selected = 0
        before = button.size.x
        game.locale = 'TR-tr'
        frame(game)
        self.assertEqual(button.text, 'Değişiklikleri kaydet')
        self.assertGreater(button.size.x, before)
        self.assertEqual(adjacent.position.x, button.size.x + layout.spacing)
        self.assertEqual(adjacent.text, '2 para')
        self.assertEqual(entry.text, 'save')
        self.assertEqual(entry.placeholder, 'Buraya yaz')
        self.assertEqual(rich.text, '[b]Fallback[/b]')
        self.assertEqual(option.text, 'Değişiklikleri kaydet')
        game.locale = 'fr'
        self.assertEqual(button.text, 'Save')

    def test_project_loads_catalogs_and_restores_player_locale(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root/'assets').mkdir()
            (root/'assets'/'tr.json').write_text('{"play":"Oyna"}', encoding='utf-8')
            (root/'doku2d.toml').write_text('''[localization]
locale = "tr"
[localization.catalogs]
tr = "res://tr.json"
[preferences]
persist = true
[storage]
directory = "user"
''', encoding='utf-8')
            game = Game.from_project(root)
            try:
                self.assertEqual(game.localization.translate('play'), 'Oyna')
                game.locale = 'en'
            finally:
                game.close()
            reopened = Game.from_project(root)
            try:
                self.assertEqual(reopened.locale, 'en')
            finally:
                reopened.close()
