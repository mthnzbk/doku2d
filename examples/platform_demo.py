"""Platform physics + Tiled collisions + animated autotile painting.

python -m examples.platform_demo [--frames 120]
"""
import argparse
from math import sin,pi
from pathlib import Path
from sfml.window import Event
from doku2d import (Game,Entity,CharacterBody,AnimatableBody,Area,AnimatedSprite,TileMap,
                    Camera,AudioPlayer,Button,CheckButton,Label,Panel,Color,Key,MouseButton)
from doku2d.gui.theme import box,disk

ASSETS=Path(__file__).parent/'assets/platform'


class Player(CharacterBody):
    def __init__(self,spawn,jump_sound):
        super().__init__(position=spawn,size=(20,30),motion_mode='grounded')
        self.speed=240
        self.max_angle=50
        self.constant_speed=True
        self.snap_length=6
        self.jump_sound=jump_sound
        self.sprite=AnimatedSprite(ASSETS/'hero.png',frame_size=(24,32))
        self.sprite.scale=(1.25,1.25)
        self.sprite.offset=(0,-2)
        for index,name in enumerate(('idle','run','jump','fall')):
            self.sprite.add_animation(name,range(index*4,index*4+4),fps=4 if name=='idle' else 10)
        self.sprite.follow_motion(self,run_speed=self.speed)
        self.z_index=10
    def physics_update(self,dt):
        self.velocity=(self.input.get_axis('move_left','move_right')*self.speed,self.velocity.y)
        if self.input.is_action_just_pressed('jump') and self.jump(500):self.jump_sound.play()
        self.move_and_slide()


class MovingPlatform(AnimatableBody):
    def __init__(self):
        super().__init__(position=(1376,548),size=(104,18))
        self.elapsed=0
        self.z_index=6
    def physics_update(self,dt):
        self.elapsed+=dt
        self.move_to((1376+sin(self.elapsed*2*pi/3.6)*100,548))
    def render(self,target,states):
        box(target,states,(-52,-9,104,18),(72,111,147),(123,190,218),2,radius=5)
        for x in (-34,0,34):disk(target,states,(x,0),2,(178,232,239))


class Goal(Area):
    def __init__(self,position,demo):
        super().__init__(position=position,radius=28)
        self.demo=demo;self.elapsed=0;self.z_index=5
    def on_ready(self):self.body_entered.connect(self.entered)
    def entered(self,body):
        if body is self.demo.player:self.demo.won=True
    def update(self,dt):self.elapsed+=dt
    def render(self,target,states):
        disk(target,states,(0,-20),24+sin(self.elapsed*3)*3,(244,211,117,25))
        disk(target,states,(0,-20),10,(255,221,132))
        box(target,states,(-3,-9,6,39),(135,111,76),radius=2)
        box(target,states,(3,-3,25,14),(249,211,113),radius=3)


class Backdrop(Entity):
    def __init__(self):super().__init__();self.z_index=-20
    def render(self,target,states):
        box(target,states,(-200,-300,3000,1500),(16,30,48))
        for x,y,r in ((200,180,90),(680,120,150),(1100,190,120),(1800,150,160)):
            disk(target,states,(x,y),r,(22,41,59))
            box(target,states,(x-r,y,2*r,700),(22,41,59))
        for x in range(40,2300,89):disk(target,states,(x,90+(x*13)%200),1,(64,100,117))


class Demo(Entity):
    def __init__(self):super().__init__();self.process_mode='always';self.won=False
    def control(self,item,x,y,w,h):
        item.position,item.size=(x,y),(w,h);item.process_mode='always'
        return self.game.add(item)
    def text(self,value,x,y,w=900,h=24,size=14):
        label=Label(text=value);label.font_size=size
        return self.control(label,x,y,w,h)
    def on_ready(self):
        game=self.game;game.physics.gravity=(0,900)
        game.add(Backdrop())
        self.world=game.add(TileMap.from_tiled(ASSETS/'platform.tmj',collisions=True))
        self.world.layers['Water'].z_index=4
        self.spawn=next(obj.position for obj in self.world.objects if obj.name=='Spawn')
        self.jump_sound=game.add(AudioPlayer(ASSETS.parent/'world/beacon.wav',volume=25,pitch_scale=1.8))
        self.player=game.add(Player(self.spawn,self.jump_sound))
        self.camera=game.add(Camera().follow(self.player,smoothing=8,dead_zone=(180,70)))
        self.camera.zoom=(1.2,1.2);self.camera.bounds=self.world.world_bounds
        self.platform=game.add(MovingPlatform())
        goal=next(obj.position for obj in self.world.objects if obj.name=='Goal')
        game.add(Goal(goal,self))
        game.input.bind('restart',Key.R)
        for name,button in (('paint_ground',0),('paint_water',1),('erase_tile',2)):
            game.input.bind(name,MouseButton(button))
        self.control(Panel(),20,18,1040,76)
        self.text('PLATFORM LAB',38,28,700,28,22)
        self.text('A/D veya oklar: yürü    •    Space: zıpla    •    R: başlangıca dön    •    P: duraklat',40,65,900,20,14)
        self.pause_button=self.control(Button(text='Duraklat'),925,34,115,38)
        self.pause_button.pressed.connect(self.pause)
        self.control(Panel(),20,594,1040,106)
        self.status=self.text('',40,605,1000,23,14)
        self.text('Haritaya çiz: sol tık = zemin  /  sağ tık = animasyonlu su  /  orta tık = sil',40,640,950,22,14)
        self.text('Kenarlar kendiliğinden birleşir. Suyun animasyonu komşular değişince de devam eder.',40,671,990,20,13)
        self.banner=self.text('',360,118,580,36,22)
    def pause(self):
        self.game.ui.set_focus(None);self.game.paused=not self.game.paused
        self.pause_button.text='Devam et' if self.game.paused else 'Duraklat'
    def reset(self):
        self.player.teleport(self.spawn);self.camera.reset_smoothing();self.won=False
    def update(self,dt):
        if self.input.is_action_just_pressed('pause'):self.pause()
        if self.input.is_action_just_pressed('restart') or self.player.position.y>950:self.reset()
        motion=self.player.sprite.motion.state
        self.status.text=(f'Durum: {motion}     Zeminde: {"evet" if self.player.is_on_floor() else "hayır"}'
                          f'     Eğim: {self.player.get_floor_angle():.0f}°     Hız: {self.player.get_real_velocity().x:.0f}'
                          f'     Çarpışma gövdesi: {len(self.world.colliders)}')
        self.banner.text='Hedefe ulaştın! R ile yeniden dene.' if self.won else ''
    def handle_event(self,event):
        if self.game.paused or self.game.window is None:return False
        if event.type not in (Event.MOUSE_MOVED,Event.MOUSE_BUTTON_PRESSED):return False
        ground=self.input.is_action_pressed('paint_ground')
        water=self.input.is_action_pressed('paint_water')
        erase=self.input.is_action_pressed('erase_tile')
        if not (ground or water or erase):return False
        point = self.game.window_to_world(event.position)
        if point is None:
            return False
        cell=self.world.world_to_map(point)
        if not 0<=cell[0]<70 or not 0<=cell[1]<24:return False
        for name in ('Ground','Water','Slopes'):self.world.layers[name].erase_cell(cell)
        if not erase:
            name='Ground' if ground else 'Water'
            self.world.layers[name].set_terrain(cell,name)
        return True


def make_demo():
    game=Game(title='Doku2D | Platform & Animated Autotile',size=(1080,720))
    game.clear_color=Color(16,30,48)
    demo=game.add(Demo());game.flush_deferred();game.flush_deferred()
    return game,demo


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--frames',type=int,default=None)
    args=parser.parse_args();game,demo=make_demo();game.run(max_frames=args.frames)
