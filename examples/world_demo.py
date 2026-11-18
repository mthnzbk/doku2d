"""Tiled layers, smooth camera and stereo/distance audio in one demo.

Run: python -m examples.world_demo [--frames 120]
"""
import argparse
from pathlib import Path
from math import sin
from doku2d import (Game,Entity,TileMap,Camera,AudioPlayer,PositionalAudio,AudioListener,
                    StaticBody,Color,Key,JoyButton,Button,CheckButton,Label,Panel,Slider)
from doku2d.gui.theme import box,disk
from .collect_game import Player

ASSETS = Path(__file__).parent/'assets/world'


class Beacon(Entity):
    def __init__(self,position,color):
        super().__init__()
        self.position=position
        self.color=color
        self.elapsed=0
        self.z_index=8
    def update(self,dt):self.elapsed+=dt
    def render(self,target,states):
        r,g,b=self.color
        for radius,alpha in ((28+sin(self.elapsed*4)*4,20),(17,40),(9,255)):
            disk(target,states,(0,-12),radius,(r,g,b,alpha))
        box(target,states,(-6,-4,12,10),(57,77,69),radius=3)
        disk(target,states,(-2,-15),3,(245,255,225))


class Demo(Entity):
    def __init__(self):
        super().__init__()
        self.process_mode='always'
        self.sounds=[]
    def add_control(self,item,position,size):
        item.position,item.size=position,size
        item.process_mode='always'
        self.game.add(item)
        return item
    def text(self,value,position,size=(400,24),font_size=15):
        label=Label(text=value);label.font_size=font_size
        return self.add_control(label,position,size)

    def on_ready(self):
        game=self.game
        self.tilemap=game.add(TileMap.from_tiled(ASSETS/'forest.tmj'))
        self.tilemap.layers['Canopy'].z_index=20
        self.player=Player()
        spawn=next(obj for obj in self.tilemap.objects if obj.name=='PlayerSpawn')
        self.player.position=spawn.position
        game.add(self.player)
        self.camera=game.add(Camera())
        self.camera.follow(self.player,smoothing=7,dead_zone=(160,100))
        self.camera.bounds=self.tilemap.world_bounds
        self.camera.zoom=(1.25,1.25)
        game.add(AudioListener(target=self.player))
        for index,obj in enumerate(obj for obj in self.tilemap.objects if obj.type=='beacon'):
            game.add(Beacon(obj.position,(255,216,115) if index==0 else (134,197,255)))
            sound=PositionalAudio(ASSETS/'beacon.wav',autoplay=True,loop=True)
            sound.position=obj.position
            sound.volume=55
            sound.pitch_scale=1 if index==0 else 1.5
            sound.max_distance=650
            sound.panning_distance=300
            sound.attenuation=1.4
            game.add(sound)
            self.sounds.append(sound)
        music=AudioPlayer(ASSETS/'ambient.wav',stream=True,loop=True,autoplay=True)
        music.volume=18
        self.music=game.add(music)
        # Only the map perimeter uses existing physics. Map tiles are editable visuals.
        w,h=self.tilemap.pixel_size
        for x,y,ww,hh in ((w/2,0,w,16),(w/2,h,w,16),(0,h/2,16,h),(w,h/2,16,h)):
            game.add(StaticBody(position=(x,y),size=(ww,hh)))
        game.input.bind('shake',Key.SPACE,JoyButton(1))
        self.add_control(Panel(),(20,18),(960,78))
        self.text('FOREST  /  TILED',(38,28),(500,30),22)
        self.text('WASD / oklar: yürü    •    Space: kamera sarsıntısı    •    P: duraklat',(40,65),(820,22),14)
        self.pause_button=self.add_control(Button(text='Duraklat'),(842,35),(118,40))
        self.pause_button.pressed.connect(self.toggle_pause)
        self.add_control(Panel(),(20,560),(960,120))
        canopy=self.add_control(CheckButton(text='Ön plan katmanı'),(38,575),(240,32))
        canopy.button_pressed=True
        canopy.toggled.connect(self.toggle_canopy)
        sound_switch=self.add_control(CheckButton(text='Sesler'),(310,575),(160,32))
        sound_switch.button_pressed=True
        sound_switch.toggled.connect(self.toggle_audio)
        self.text('Yakınlaştırma',(510,579),(150,24),14)
        zoom=self.add_control(Slider(min_value=.75,max_value=2,value=1.25,step=.05),(668,575),(286,32))
        zoom.value_changed.connect(lambda value:setattr(self.camera,'zoom',(value,value)))
        zoom.drag_ended.connect(lambda:game.ui.set_focus(None))
        self.status=self.text('',(40,619),(915,22),14)
        self.text('Işıklara yaklaş: ses yükselir. Sağa/sola geç: stereo yön değişir.',(40,649),(915,22),14)

    def toggle_pause(self):
        self.game.ui.set_focus(None)
        self.game.paused=not self.game.paused
        self.pause_button.text='Devam et' if self.game.paused else 'Duraklat'
    def toggle_canopy(self,shown):
        self.tilemap.layers['Canopy'].visible=shown
        self.game.ui.set_focus(None)
    def toggle_audio(self,enabled):
        self.game.ui.set_focus(None)
        for sound in (*self.sounds,self.music):sound.stream_paused=not enabled
    def update(self,dt):
        if self.input.is_action_just_pressed('pause'):self.toggle_pause()
        if self.input.is_action_just_pressed('shake'):self.camera.shake(14,.45)
        cell=self.tilemap.world_to_map(self.player.position)
        sound=self.sounds[0]
        self.status.text=(f'Hücre: {cell[0]}, {cell[1]}     Katman: {len(self.tilemap.layers)}'
                          f'     Sarı ışık: %{sound.effective_volume:.0f} ses / {sound.pan:+.2f} yön')


def make_demo():
    game=Game(title='Doku2D | Tiled, Camera & Audio',size=(1000,700))
    game.clear_color=Color(20,43,43)
    demo=game.add(Demo())
    game.flush_deferred()
    game.flush_deferred()
    return game,demo


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--frames',type=int,default=None)
    args=parser.parse_args()
    game,demo=make_demo()
    game.run(max_frames=args.frames)
