"""A small, complete game: python -m examples.collect_game [--frames 120]."""
import argparse
from math import sin
from sfml.graphics import Color, Image, Texture
from doku2d import (AnimatedSprite, Area, CharacterBody, Entity, Game, Key, RigidBody,
                    StaticBody, Button, Label, LineEdit, Panel, VirtualJoystick)
from doku2d.gui.theme import box, disk


COINS = ((180,180), (470,185), (680,280), (940,190),
         (945,550), (650,500), (350,530), (110,370))


def robot_texture():
    """A tiny code-drawn sprite sheet; no external assets required."""
    image = Image.create(24*4,32*3,Color.TRANSPARENT)
    def rect(frame, row, x, y, width, height, color):
        for px in range(x,x+width):
            for py in range(y,y+height):
                image[frame*24+px,row*32+py] = Color(*color)
    for row in range(3):
        for frame in range(4):
            bob = 1 if frame in (1,3) else 0
            dark, cyan, light = (31,85,94), (100,224,199), (187,255,236)
            rect(frame,row,5,25,5,4 if frame != 1 else 2,dark)
            rect(frame,row,14,25,5,4 if frame != 3 else 2,dark)
            rect(frame,row,4,10-bob,16,17,cyan)
            rect(frame,row,6,7-bob,12,4,light)
            rect(frame,row,2,16-bob,3,7,dark)
            rect(frame,row,19,16-bob,3,7,dark)
            rect(frame,row,7,14-bob,10,6,(16,39,52))
            if row == 0: # front
                rect(frame,row,8,15-bob,2,2,light)
                rect(frame,row,14,15-bob,2,2,light)
            elif row == 1: # side (flipped for left)
                rect(frame,row,14,15-bob,3,2,light)
            else: # back
                rect(frame,row,10,15-bob,4,3,dark)
            rect(frame,row,8,23-bob,8,2,light)
    return Texture.from_image(image)


class Player(CharacterBody):
    def __init__(self):
        super().__init__(position=(108,200),size=(22,22),mass=4)
        self.speed = 220
        self.facing = 'down'
        self.sprite = AnimatedSprite(robot_texture(),frame_size=(24,32))
        self.sprite.scale = (1.5,1.5)
        self.sprite.offset = (0,-4)
        for direction,row in (('down',0),('side',1),('up',2)):
            self.sprite.add_animation('idle_'+direction,[row*4],fps=4)
            self.sprite.add_animation('walk_'+direction,range(row*4,row*4+4),fps=10)
        self.sprite.play('idle_down')
        self.z_index = 10

    def physics_update(self,dt):
        direction = self.input.get_vector()
        self.velocity = direction*self.speed
        self.move_and_slide()
        moving = bool(direction.x or direction.y)
        if moving:
            if abs(direction.x) > abs(direction.y):
                self.facing = 'side'
                self.sprite.flip_h = direction.x < 0
            else:
                self.facing = 'up' if direction.y < 0 else 'down'
                self.sprite.flip_h = False
        self.sprite.play(('walk_' if moving else 'idle_')+self.facing)


class Wall(StaticBody):
    def render(self,target,states):
        w,h = self.shape.size
        box(target,states,(-w/2+3,-h/2+5,w,h),(5,13,21,100),radius=5)
        box(target,states,(-w/2,-h/2,w,h),(42,66,76),(64,99,108),radius=5)
        box(target,states,(-w/2+3,-h/2+3,w-6,3),(91,142,143),radius=1)


class Crate(RigidBody):
    def __init__(self,position):
        super().__init__(position=position,size=(34,34),mass=1.5)
        self.linear_damp = 5
        self.angular_damp = 6
        self.friction = .5
        self.z_index = 5

    def render(self,target,states):
        box(target,states,(-15,-13,34,34),(5,13,21,110),radius=5)
        box(target,states,(-17,-17,34,34),(140,98,54),(218,168,93),2,radius=5)
        box(target,states,(-12,-12,24,24),(117,78,43),radius=3)
        box(target,states,(-3,-12,6,24),(198,144,75),radius=1)


class Spark(Area):
    def __init__(self,position,session):
        super().__init__(position=position,radius=16)
        self.session = session
        self.elapsed = position[0]/100
        self.collision_layer = 2
        self.collision_mask = 1
        self.collected = False
        self.z_index = 3

    def on_ready(self):
        self.body_entered.connect(self.collect)

    def collect(self,body):
        if isinstance(body,Player) and not self.collected:
            self.collected = True
            self.session.collect()
            self.destroy()

    def update(self,dt):
        self.elapsed += dt

    def render(self,target,states):
        y = sin(self.elapsed*3)*3
        disk(target,states,(0,y),16,(243,202,97,20))
        disk(target,states,(0,y),10,(243,202,97,55))
        disk(target,states,(0,y),6,(255,215,112))
        disk(target,states,(-2,y-2),2,(255,250,214))


class Floor(Entity):
    def __init__(self):
        super().__init__()
        self.z_index = -10
    def render(self,target,states):
        box(target,states,(32,120,1016,472),(17,33,43),radius=16)
        for x in range(48,1040,32):
            for y in range(136,584,32):
                box(target,states,(x,y,2,2),(31,51,62))
        box(target,states,(70,156,76,84),(25,58,63),radius=12)


class Session(Entity):
    """Plain Python coordinator; it owns references, not a scene hierarchy."""
    def __init__(self):
        super().__init__()
        self.process_mode = 'always'
        self.score = 0
        self.player = None
        self.menu = []

    def control(self,item,x,y,w,h,*,menu=False):
        item.position, item.size = (x,y),(w,h)
        item.process_mode = 'always'
        if menu:
            item.z_index = 101
            item.visible = False
            self.menu.append(item)
        self.game.add(item,persistent=True)
        return item

    def text(self,value,x,y,w=500,h=26,size=16,*,menu=False):
        label = Label(text=value)
        label.font_size = size
        return self.control(label,x,y,w,h,menu=menu)

    def on_ready(self):
        self.text('SPARK RUN',32,20,440,38,28)
        self.text('Sekiz ışığı topla. Sandıkları it, duvarların arasından geç.',34,67,760,26,15)
        self.score_label = self.text('',774,22,150,40,22)
        pause = self.control(Button(text='Duraklat'),932,24,116,40)
        pause.pressed.connect(self.toggle_pause)
        self.text('WASD / Oklar / Gamepad',32,610,320,26,16)
        self.text('ESC veya P: duraklat    •    R: yeniden başlat',32,644,450,26,14)
        self.text('Metin alanında yazarken karakter hareket etmez.',32,678,480,24,13)
        self.entry = self.control(LineEdit(),520,638,330,40)
        self.entry.placeholder = 'Bir şey yazmayı dene...'
        self.entry.text_submitted.connect(lambda value:self.game.ui.set_focus(None))
        self.game.input.bind('restart',Key.R)
        self.stick = self.control(VirtualJoystick(),930,610,100,100)
        self.text('Sürükle',934,710,100,20,12)
        panel = self.control(Panel(),340,218,400,294,menu=True)
        panel.z_index = 100
        self.menu_title = self.text('Duraklatıldı',376,244,330,40,26,menu=True)
        self.menu_hint = self.text('Bir nefes ver. Işıklar seni bekler.',376,290,330,30,14,menu=True)
        resume = self.control(Button(text='Devam et'),376,342,328,40,menu=True)
        resume.pressed.connect(self.resume)
        restart = self.control(Button(text='Yeniden başlat'),376,394,328,40,menu=True)
        restart.pressed.connect(self.restart)
        quit_button = self.control(Button(text='Çıkış'),376,446,328,40,menu=True)
        quit_button.pressed.connect(self.game.quit)
        self.restart()

    def restart(self):
        self.resume()
        self.score = 0
        self.score_label.text = f'0 / {len(COINS)} ışık'
        self.player = Player()
        objects = [Floor(), self.player]
        walls = ((540,124,1000,8),(540,588,1000,8),
                 (36,356,8,464),(1044,356,8,464),
                 (330,270,22,210),(570,390,270,22),
                 (820,240,22,140),(180,460,160,22),(960,480,130,22))
        objects += [Wall(position=(x,y),size=(w,h)) for x,y,w,h in walls]
        objects += [Crate(point) for point in ((420,290),(740,480),(910,330))]
        objects += [Spark(point,self) for point in COINS]
        self.game.replace(*objects)

    def collect(self):
        self.score += 1
        self.score_label.text = f'{self.score} / {len(COINS)} ışık'
        if self.score == len(COINS):
            self.set_paused(True,won=True)

    def set_paused(self,paused,*,won=False):
        self.game.ui.set_focus(None)
        self.game.paused = paused
        self.entry.disabled = paused
        self.stick.disabled = paused
        for control in self.menu:
            control.visible = paused
        self.menu_title.text = 'Hepsini topladın!' if won else 'Duraklatıldı'
        self.menu_hint.text = 'Yeni bir tur için yeniden başlat.' if won else 'Bir nefes ver. Işıklar seni bekler.'

    def toggle_pause(self):
        self.set_paused(not self.game.paused)

    def resume(self):
        self.set_paused(False)

    def update(self,dt):
        if self.input.is_action_just_pressed('pause'):
            self.toggle_pause()
        if self.input.is_action_just_pressed('restart'):
            self.restart()


def make_game():
    game = Game(title='Doku2D | Spark Run',size=(1080,748))
    game.clear_color = Color(12,22,32)
    session = game.add(Session(),persistent=True)
    game.flush_deferred()
    return game,session


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames',type=int,default=None)
    args = parser.parse_args()
    game,session = make_game()
    game.run(max_frames=args.frames)
