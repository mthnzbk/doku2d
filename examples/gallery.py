"""Run the demo gallery with python -m examples.gallery."""
import argparse
from pathlib import Path

from doku2d import Button, CheckBox, CheckButton, Color, Entity, Game, Label, LineEdit
from doku2d import Panel, ProgressBar, Slider, Theme
from . import collect_game, effects_demo, example1, gui_demo, platform_demo, world_demo
from .starter_project.main import PROJECT, Starter


THEMES = Path(__file__).with_name('themes')


def starter_game():
    game = Game.from_project(PROJECT)
    game.add(Starter())
    return game


DEMOS = (
    ('Arayüz kontrolleri', gui_demo.make_demo),
    ('Işık toplama', collect_game.make_game),
    ('Tiled, kamera ve ses', world_demo.make_demo),
    ('Platform ve autotile', platform_demo.make_demo),
    ('Animasyon, parçacık ve ışık', effects_demo.make_demo),
    ('Bağımsız nesneler ve kamera', example1.create_demo),
    ('Başlangıç projesi', starter_game),
)


class Gallery(Entity):
    def __init__(self, theme_name='gece'):
        super().__init__()
        self.theme_name = theme_name
        self.selection = None

    def on_ready(self):
        self.themes = {name: Theme.load(THEMES / f'{name}.toml', resources=self.game.resources)
                       for name in ('gece', 'kum')}

        def place(control, x, y, width, height):
            control.position = (x, y)
            control.size = (width, height)
            return self.game.add(control)

        title = place(Label(text='Doku2D Örnek Galerisi'), 34, 24, 800, 42)
        title.font_size = 30
        place(Panel(), 28, 92, 326, 560)
        place(Panel(), 374, 92, 598, 560)
        place(Label(text='Örnekler'), 52, 111, 250, 36).font_size = 20
        for index, (label, factory) in enumerate(DEMOS):
            button = place(Button(text=label), 52, 160 + index * 64, 278, 48)
            button.pressed.connect(lambda factory=factory: self.open_demo(factory))

        place(Label(text='Tema önizlemesi'), 404, 111, 450, 36).font_size = 20
        place(Button(text='Gece'), 404, 160, 255, 44).pressed.connect(lambda: self.apply_theme('gece'))
        place(Button(text='Kum'), 687, 160, 255, 44).pressed.connect(lambda: self.apply_theme('kum'))
        self.theme_label = place(Label(), 404, 219, 520, 30)
        place(CheckBox(text='Bildirimler'), 404, 264, 250, 35)
        place(CheckButton(text='Ses efektleri'), 687, 264, 250, 35)
        entry = place(LineEdit(), 404, 320, 538, 44)
        entry.placeholder = 'Buraya yazabilirsin'
        place(Label(text='Ses seviyesi'), 404, 389, 520, 28)
        slider = place(Slider(value=65), 404, 428, 538, 35)
        progress = place(ProgressBar(value=65), 404, 479, 538, 30)
        slider.value_changed.connect(lambda value: setattr(progress, 'value', value))
        action = place(Button(text='Düğmeyi dene'), 404, 546, 255, 44)
        disabled = place(Button(text='Devre dışı'), 687, 546, 255, 44)
        disabled.disabled = True
        status = place(Label(), 404, 606, 538, 25)
        action.pressed.connect(lambda: setattr(status, 'text', 'Düğme çalıştı.'))
        self.apply_theme(self.theme_name)

    def apply_theme(self, name):
        self.theme_name = name
        self.game.ui.theme = self.themes[name]
        self.game.clear_color = Color(*self.themes[name].background)
        self.theme_label.text = f'Etkin tema: {name.title()}'

    def open_demo(self, factory):
        self.selection = factory
        self.game.quit()


def make_gallery(theme_name='gece'):
    game = Game(title='Doku2D | Örnek Galerisi', size=(1000, 680))
    gallery = game.add(Gallery(theme_name))
    game.flush_deferred()
    return game, gallery


def make_demo(factory):
    result = factory()
    game = result if isinstance(result, Game) else result[0]
    back = Button(text='Galeriye dön')
    back.size = (134, 33)
    back.position = (game.size.x - back.size.x - 12, 10)
    back.font_size = 13
    back.process_mode = 'always'
    back.z_index = 10000
    back.pressed.connect(game.quit)
    game.add(back)
    return game


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames', type=int)
    args = parser.parse_args(argv)
    theme_name = 'gece'
    while True:
        game, gallery = make_gallery(theme_name)
        game.run(max_frames=args.frames)
        if gallery.selection is None:
            return
        theme_name = gallery.theme_name
        make_demo(gallery.selection).run()


if __name__ == '__main__':
    main()
