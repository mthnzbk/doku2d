"""A small complete game using resources, save slots and visual composition."""
import argparse
from pathlib import Path
from doku2d import (Game,Entity,CharacterBody,Area,AnimatedSprite,CanvasGroup,DayNightCycle,
                    PointLight,LightOccluder,Panel,Label,Button,Slider,Color,SaveError,Key)
from doku2d.gui.theme import disk

PROJECT=Path(__file__).with_name('doku2d.toml')
DEFAULT_COINS=((250,180),(460,190),(720,180),(740,430),(470,430),(200,430))


class Player(CharacterBody):
    def __init__(self,position):
        super().__init__(position=position,size=(20,24))
        self.sprite=AnimatedSprite('res://player.png',frame_size=(24,32))
        self.sprite.add_animation('idle',range(4),fps=4)
        self.sprite.add_animation('walk',range(4,8),fps=10)
        self.sprite.follow_motion(self,run='walk',run_speed=180)
        self.sprite.scale=(1.3,1.3);self.z_index=10
    def physics_update(self,dt):
        self.velocity=self.input.get_vector()*180;self.move_and_slide()


class Coin(Area):
    def __init__(self,position,session):
        super().__init__(position=position,radius=18)
        self.session=session;self.z_index=4;self.collected=False
    def on_ready(self):self.body_entered.connect(self.collect)
    def collect(self,body):
        if body is self.session.player and not self.collected:
            self.collected=True;self.session.score+=1;self.destroy()
    def render(self,target,states):
        disk(target,states,(0,0),12,(252,211,110,50))
        disk(target,states,(0,0),6,(255,225,140))


class Starter(Entity):
    def __init__(self):super().__init__();self.score=0;self.coins=[]
    def on_ready(self):
        game=self.game
        world=game.add(game.resources.load_map('res://level.tmj',collisions=True))
        game.call_deferred(self.attach_occluders,world)
        game.input.bind('save',Key.F5,global_action=True)
        game.input.bind('load',Key.F9,global_action=True)
        self.clock=game.add(DayNightCycle(day_length=120,time=game.settings.get('hour',10)))
        self.player=game.add(Player((120,180)))
        game.add(PointLight(target=self.player,radius=165,color=(170,235,255),energy=.9,shadow=True))
        self.make_coins(DEFAULT_COINS)
        self.hud=game.add(CanvasGroup(canvas=game.ui.canvas))
        panel=self.hud.add(Panel());panel.size=(912,90)
        self.label=self.hud.add(Label(text=''));self.label.position=(16,8);self.label.size=(500,28);self.label.font_size=19
        self.notice=self.hud.add(Label(text='Işıkları topla. F5 kaydet / F9 yükle.'))
        self.notice.position=(16,45);self.notice.size=(570,26);self.notice.font_size=14
        self.hud.position=(24,18)
        for x,title,callback in ((610,'Kaydet',self.save),(748,'Yükle',self.load)):
            button=self.hud.add(Button(text=title));button.position=(x,23);button.size=(120,40);button.pressed.connect(callback)
        hour=game.add(Slider(min_value=0,max_value=24,value=self.clock.time,step=.1));hour.position=(164,584);hour.size=(250,32)
        hour.value_changed.connect(lambda value:setattr(self.clock,'time',value));hour.drag_ended.connect(lambda:game.ui.set_focus(None))
        opacity=game.add(Slider(min_value=.15,max_value=1,value=1,step=.05));opacity.position=(656,584);opacity.size=(250,32)
        opacity.value_changed.connect(lambda value:setattr(self.hud,'opacity',value));opacity.drag_ended.connect(lambda:game.ui.set_focus(None))
        for text,x in (('Saat',32),('HUD saydamlığı',478)):
            label=game.add(Label(text=text));label.position=(x,584);label.size=(160,32)
    def attach_occluders(self,world):
        for body in world.colliders:self.game.add(LightOccluder.from_body(body))
    def make_coins(self,positions):
        for coin in self.coins:
            if coin.game is self.game or coin._pending_game is self.game:self.game.remove(coin)
        self.coins=[self.game.add(Coin(position,self), scope=self.scope) for position in positions]
    def save(self):
        try:
            self.game.saves.save('slot1',dict(version=1,score=self.score,position=list(self.player.position),
                hour=self.clock.time,day=self.clock.day,coins=[list(c.position) for c in self.coins if not c.collected]))
            self.notice.text='Kaydedildi.'
        except (OSError,SaveError) as error:self.notice.text=f'Kayıt hatası: {error}'
        self.game.ui.set_focus(None)
    def load(self):
        try:
            data=self.game.saves.load('slot1')
            if data is None:self.notice.text='Henüz kayıt yok.';return
            if data.get('version')!=1:raise ValueError('Desteklenmeyen kayıt sürümü')
            self.player.teleport(data['position']);self.score=int(data['score'])
            self.clock.time=data['hour'];self.clock.day=data['day'];self.make_coins(data['coins'])
            self.notice.text='Kayıt yüklendi.'
        except (OSError,SaveError,ValueError,KeyError,TypeError) as error:self.notice.text=f'Yükleme hatası: {error}'
        finally:self.game.ui.set_focus(None)
    def update(self,dt):
        if self.input.is_action_just_pressed('save'):self.save()
        if self.input.is_action_just_pressed('load'):self.load()
        self.label.text=f'Işık: {self.score} / 6     Saat: {int(self.clock.time):02d}:{int(self.clock.time%1*60):02d}'
        self.game.settings['hour']=self.clock.time


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--frames',type=int)
    args=parser.parse_args(argv)
    game=Game.from_project(PROJECT)
    game.run(Starter(),max_frames=args.frames)


if __name__=='__main__':main()
