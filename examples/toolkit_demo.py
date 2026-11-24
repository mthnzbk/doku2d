"""Interactive checks for input, audio and developer tools."""
from pathlib import Path
from tempfile import TemporaryDirectory

from doku2d import (AudioPlayer, Button, CheckButton, Color, Entity, Game, InputHint,
                    Key, Label, Panel, ProgressBar, SpeechBubble, Sprite, SpriteAtlas, tr)
from doku2d.cli import build_atlas


ASSETS = Path(__file__).with_name('assets')


class ToolkitDemo(Entity):
    def on_ready(self):
        self.context = None
        self.temporary = TemporaryDirectory(prefix='doku2d-atlas-')
        self.atlas = None
        self.music = self.game.add(AudioPlayer('world/ambient.wav', bus='Music', loop=True, volume=35))
        self.announcement = self.game.add(AudioPlayer('world/beacon.wav', bus='Voice', loop=True, volume=22))
        self.game.audio.duck('Voice', 'Music', amount=72, attack=.18, release=.65)
        console = self.game.debug.console
        console.register('say', self.say)
        console.register('duck', lambda: f'{self.game.audio.duck_gain("Music"):.0%}')

        def place(control, x, y, width, height):
            control.position, control.size = (x, y), (width, height)
            return self.game.add(control)

        place(Label(text='Girdi, ses ve geliştirici araçları'), 24, 10, 650, 34).font_size = 24
        place(Panel(), 24, 68, 450, 315)
        place(Panel(), 492, 68, 484, 315)
        place(Label(text='Girdi bağlamı'), 45, 82, 415, 32).font_size = 20
        place(InputHint('interact', caption='Konuş'), 45, 125, 410, 30)
        place(Button(text='E / F atamasını değiştir'), 45, 164, 403, 36).pressed.connect(self.rebind)
        place(CheckButton(text='Diyalog bağlamı'), 45, 214, 403, 35).toggled.connect(self.set_context)
        place(Label(text='WASD ile karakteri hareket ettir.'), 45, 264, 403, 24)
        place(Label(text='Diyalog bağlamında sadece konuşma etkin.'), 45, 294, 403, 24)
        place(Label(text='F3 → F4   ·   say "Merhaba"   ·   duck'), 45, 337, 403, 24)

        place(Label(text='Ses kanalları'), 512, 82, 433, 32).font_size = 20
        place(CheckButton(text='Ambiyansı oynat'), 512, 125, 430, 35).toggled.connect(
            lambda enabled: self.toggle_audio(self.music, enabled))
        place(CheckButton(text='Anons kanalını oynat'), 512, 170, 430, 35).toggled.connect(
            lambda enabled: self.toggle_audio(self.announcement, enabled))
        self.gain = place(ProgressBar(value=100), 512, 221, 430, 23)
        self.gain_text = place(Label(), 512, 253, 430, 28)
        place(Button(text='PNG dosyalarından atlas üret'), 512, 301, 430, 39).pressed.connect(self.pack)
        self.atlas_text = place(Label(text='3 kaynak portre'), 512, 346, 430, 24)

        self.actor = self.game.add(Sprite(ASSETS / 'portraits/traveler.png'))
        self.actor.position, self.actor.scale = (220, 490), (2.2, 2.2)
        self.bubble = self.game.add(SpeechBubble(self.actor, offset=(0, -37)))
        self.bubble.z_index = 15
        self.previews = []
        for index, name in enumerate(('keeper', 'keeper-relieved', 'traveler')):
            sprite = self.game.add(Sprite())
            sprite.position, sprite.scale = (568+index*148, 490), (2, 2)
            self.previews.append((name, sprite))
            title = place(Label(text=name), 505+148*index, 541, 126, 22)
            title.horizontal_alignment = 'center'
        self.say()

    def say(self, *words):
        self.bubble.say(' '.join(words) if words else tr('demo.quick_line', default='İyi akşamlar, gezgin!'))
        return 'Konuşma balonu gösteriliyor'

    def rebind(self):
        bindings = self.input.get_bindings('interact')
        key = Key.F if bindings[0] == Key.E else Key.E
        self.input.set_bindings('interact', key, *bindings[1:])
        self.game.ui.set_focus(None)

    def set_context(self, enabled):
        self.game.ui.set_focus(None)
        if enabled and self.context is None:
            self.context = self.input.push_context('interact')
        elif not enabled and self.context is not None:
            self.input.pop_context(self.context)
            self.context = None

    def toggle_audio(self, player, enabled):
        if enabled:
            player.play()
        else:
            player.stop()
        self.game.ui.set_focus(None)

    def pack(self):
        output = Path(self.temporary.name) / 'portraits.json'
        try:
            # Pack once per session. Rendering shares the resulting texture.
            if self.atlas is None:
                self.atlas = SpriteAtlas.from_file(build_atlas(ASSETS / 'portraits', output),
                                                   resources=self.game.resources)
            for name, sprite in self.previews:
                sprite.texture = self.atlas[name]
            width, height = self.atlas.texture.size
            self.atlas_text.text = f'{len(self.atlas)} bölge · {int(width)} × {int(height)} px · tek doku'
        except (ValueError, OSError, RuntimeError) as error:
            self.atlas_text.text = str(error)
        self.game.ui.set_focus(None)

    def update(self, dt):
        x, y = self.actor.position
        dx, dy = self.input.get_vector()
        self.actor.position = min(427, max(68, x+dx*140*dt)), min(590, max(445, y+dy*140*dt))
        if self.input.is_action_just_pressed('interact'):
            self.say()
        gain = self.game.audio.duck_gain('Music')
        self.gain.value = gain*100
        self.gain_text.text = f'Ambiyans seviyesi  %{gain*100:.0f}'

    def on_removed(self):
        self.temporary.cleanup()


def make_demo():
    game = Game(title='Doku2D | Girdi, Ses ve Araçlar', size=(1000, 680), asset_root=ASSETS, debug=True)
    game.clear_color = Color(20, 28, 41)
    game.audio.add_bus('Voice')
    demo = game.add(ToolkitDemo())
    game.flush_deferred()
    return game, demo
