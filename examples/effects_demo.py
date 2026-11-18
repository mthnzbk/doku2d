"""Tween, Timeline, particles and canvas lighting/shadows in one interactive room.

python -m examples.effects_demo [--frames 120]
"""
import argparse
from sfml.graphics import Color,VertexArray,Vertex,PrimitiveType
from doku2d import (Game,Entity,Signal,Timeline,AnimationPlayer,Particles,PointLight,
                    DirectionalLight,LightOccluder,CanvasModulate,StaticBody,AnimatableBody,
                    Panel,Label,Button,CheckButton,Slider,Key,JoyButton)
from doku2d.gui.theme import box,disk
from .collect_game import Player


class Lab(Entity):
    def __init__(self):
        super().__init__();self.z_index=-20
        self.grid=VertexArray(PrimitiveType.LINES)
        for x in range(44,1040,32):
            self.grid.append(Vertex((x,130),Color(75,93,109)));self.grid.append(Vertex((x,578),Color(75,93,109)))
        for y in range(130,580,32):
            self.grid.append(Vertex((30,y),Color(75,93,109)));self.grid.append(Vertex((1050,y),Color(75,93,109)))
    def render(self,target,states):
        box(target,states,(28,126,1024,454),(96,114,130),radius=16)
        target.draw(self.grid,states)
        box(target,states,(166,380,120,90),(105,90,72),radius=18)
        box(target,states,(202,420,48,32),(84,65,47),radius=8)


class Block(StaticBody):
    def __init__(self,position,size):
        super().__init__(position=position,size=size,color=(150,169,183))
        self.z_index=3
    def render(self,target,states):
        w,h=self.shape.size
        box(target,states,(-w/2,-h/2,w,h),self.color,(203,218,223),2,radius=6)
        box(target,states,(-w/2+6,-h/2+6,w-12,4),(187,204,216),radius=1)


class Crate(AnimatableBody):
    def __init__(self):
        super().__init__(position=(490,350),size=(68,54),color=Color(196,139,80))
        self.z_index=4
    def render(self,target,states):
        box(target,states,(-34,-27,68,54),self.color,(242,201,139),2,radius=6)
        box(target,states,(-4,-22,8,44),(107,78,57),radius=2)
        box(target,states,(-27,-4,54,8),(107,78,57),radius=2)


class LampDots(Entity):
    def __init__(self,lights):super().__init__();self.lights=lights;self.z_index=12
    def render(self,target,states):
        for light in self.lights:
            if not light.enabled:continue
            point=light.transform.transform_point(light.offset)
            disk(target,states,point,7,light.color)
            disk(target,states,point,3,Color.WHITE)


class Demo(Entity):
    cue=Signal()
    def __init__(self):
        super().__init__();self.process_mode='always';self.last_cue='Hazır';self.cues=0;self.effects=[]
    def control(self,item,x,y,w,h):
        item.position,item.size=(x,y),(w,h);item.process_mode='always';return self.game.add(item)
    def text(self,value,x,y,w=980,h=24,size=14):
        item=Label(text=value);item.font_size=size;return self.control(item,x,y,w,h)
    def on_ready(self):
        game=self.game;game.add(Lab())
        self.ambient=game.add(CanvasModulate(color=Color(68,78,99)))
        self.warm=game.add(PointLight(position=(236,408),radius=310,color=(255,194,122),energy=1.5,shadow=True))
        self.cool=game.add(PointLight(position=(900,210),radius=330,color=(128,181,255),energy=1.7,shadow=True))
        self.sun=game.add(DirectionalLight(direction=(.8,1),color=(135,160,220),energy=.15,shadow=True))
        self.player=Player();self.player.position=(430,490);game.add(self.player)
        self.lamp=game.add(PointLight(target=self.player,position=(0,-4),radius=140,color=(125,255,213),energy=1,shadow=True))
        self.lights=[self.warm,self.cool,self.sun,self.lamp]
        game.add(LampDots([self.warm,self.cool]))
        for position,size in (((365,275),(42,154)),((740,420),(180,34)),((680,230),(75,60))):
            block=game.add(Block(position,size));game.add(LightOccluder.from_body(block))
        for position,size in (((540,124),(1024,8)),((540,582),(1024,8)),((26,352),(8,460)),((1054,352),(8,460))):
            game.add(StaticBody(position=position,size=size))
        self.crate=game.add(Crate());game.add(LightOccluder.from_body(self.crate))
        self.smoke=game.add(Particles.smoke(position=(236,415),seed=10));self.smoke.z_index=7
        self.sparks=game.add(Particles.sparks(position=(236,410),seed=20));self.sparks.z_index=9
        self.rain=game.add(Particles.rain(position=(540,128),amount=120,emitting=False,seed=30));self.rain.z_index=8
        self.clip=game.add(AnimationPlayer())
        timeline=Timeline(6,loop=True)
        timeline.property(self.crate,'position',[(0,(490,350)),(1.5,(555,350)),(3,(555,485)),(4.5,(490,485)),(6,(490,350))],ease='in_out_sine')
        timeline.property(self.crate,'rotation',[(0,0),(6,360)])
        timeline.call(1.5,self.burst,False)
        timeline.signal(3,self.cue,'Zaman çizelgesi sinyali')
        timeline.call(4.5,self.burst,False)
        self.clip.add_animation('crate',timeline);self.clip.play('crate')
        self.cue.connect(self.mark_cue)
        game.call_deferred(self.start_tweens)
        game.input.bind('burst',Key.SPACE,JoyButton(0))
        self.control(Panel(),20,18,1040,78)
        self.text('EFFECTS LAB',38,28,h=30,size=24)
        self.text('WASD / oklar: yürü    •    Space: kıvılcım    •    P: duraklat',40,65,w=860,h=22)
        self.pause_button=self.control(Button(text='Duraklat'),930,35,110,40);self.pause_button.pressed.connect(self.pause)
        self.control(Panel(),20,600,1040,142)
        burst=self.control(Button(text='Kıvılcım patlat'),40,616,166,38);burst.pressed.connect(self.burst)
        self.clip_button=self.control(Button(text='Çizelgeyi durdur'),220,616,180,38);self.clip_button.pressed.connect(self.toggle_clip)
        shadows=self.control(CheckButton(text='Gölgeler'),424,619,180,32);shadows.button_pressed=True;shadows.toggled.connect(self.toggle_shadows)
        rain=self.control(CheckButton(text='Yağmur'),626,619,158,32);rain.toggled.connect(self.toggle_rain)
        lighting=self.control(CheckButton(text='Aydınlatma'),816,619,220,32);lighting.button_pressed=True;lighting.toggled.connect(self.toggle_lighting)
        self.text('Çizelge hızı',40,673,w=142)
        speed=self.control(Slider(min_value=.25,max_value=2,value=1,step=.05),184,669,268,32)
        speed.value_changed.connect(lambda value:setattr(self.clip,'speed_scale',value))
        speed.drag_ended.connect(lambda:game.ui.set_focus(None))
        self.text('Işık: Tween  •  Sandık: AnimationPlayer  •  Duman: Particles',485,673,w=545,h=24,size=13)
        self.status=self.text('',40,709,w=1000,h=22,size=13)
    def start_tweens(self):
        motion=self.cool.create_tween().set_loops().set_ease('in_out_sine')
        for point,energy in (((900,500),1.1),((620,500),1.8),((620,210),1.15),((900,210),1.7)):
            motion.tween_property(self.cool,'position',point,1.8)
            motion.parallel().tween_property(self.cool,'energy',energy,1.8)
        tint=self.crate.create_tween().set_loops().set_ease('in_out_sine')
        tint.tween_property(self.crate,'color',Color(112,183,207),3)
        tint.tween_property(self.crate,'color',Color(196,139,80),3)
    def mark_cue(self,message):self.last_cue=message;self.cues+=1
    def burst(self,at_player=True):
        self.game.ui.set_focus(None)
        position=self.player.position if at_player else self.crate.position
        self.sparks.position=position;self.sparks.burst()
        flash=self.game.add(PointLight(position=position,radius=180,color=(255,166,80),energy=2,shadow=True))
        tween=flash.create_tween();tween.tween_property(flash,'energy',0,.45,ease='out_quad');tween.finished.connect(flash.destroy)
        self.mark_cue('Kıvılcım + geçici ışık')
    def pause(self):
        self.game.ui.set_focus(None);self.game.paused=not self.game.paused
        self.pause_button.text='Devam et' if self.game.paused else 'Duraklat'
    def toggle_clip(self):
        if self.clip.playing:self.clip.pause()
        else:self.clip.resume()
        self.clip_button.text='Çizelgeyi durdur' if self.clip.playing else 'Çizelgeyi oynat'
        self.game.ui.set_focus(None)
    def toggle_shadows(self,value):
        for light in self.lights:light.shadow=value
        self.game.ui.set_focus(None)
    def toggle_rain(self,value):self.rain.emitting=value;self.game.ui.set_focus(None)
    def toggle_lighting(self,value):self.game.world.lighting=value;self.game.ui.set_focus(None)
    def update(self,dt):
        if self.input.is_action_just_pressed('pause'):self.pause()
        if self.input.is_action_just_pressed('burst'):self.burst()
        count=self.smoke.alive_count+self.sparks.alive_count+self.rain.alive_count
        self.status.text=f'Parçacık: {count}    Çizelge: {self.clip.playback_position:.2f} / 6 sn    Cue: {self.cues}    {self.last_cue}'


def make_demo():
    game=Game(title='Doku2D | Tween, Animation, Particles & Lights',size=(1080,760))
    game.clear_color=Color(10,17,28)
    demo=game.add(Demo());game.flush_deferred();game.flush_deferred()
    return game,demo


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--frames',type=int,default=None)
    args=parser.parse_args();game,demo=make_demo();game.run(max_frames=args.frames)
