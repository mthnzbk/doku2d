"""Run with python -m examples.example1. WASD/arrows move; P pauses."""
import argparse
from dataclasses import dataclass
from math import sin
from random import Random
from sfml.graphics import CircleShape, Color, RectangleShape, Text
from sfml.system import Vector2
from sfml.window import Event, Keyboard
from doku2d import Camera, Canvas, Entity, Game, Signal


def rectangle(x, y, width, height, color):
    shape = RectangleShape((width, height))
    shape.position = (x, y)
    shape.fill_color = Color(*color)
    return shape


def circle(x, y, radius, color):
    shape = CircleShape(radius, 48)
    shape.position = (x, y)
    shape.fill_color = Color(*color)
    return shape


@dataclass
class Session:
    distance: float = 0.0


class Landscape(Entity):
    def __init__(self, name, shapes):
        super().__init__(name)
        self.shapes = shapes

    def render(self, target, states):
        for shape in self.shapes:
            target.draw(shape, states)


class Explorer(Entity):
    moved = Signal()

    def __init__(self):
        super().__init__("Explorer")
        self.position = (480, 300)
        self.elapsed = 0.0
        self.shapes = [circle(-24, 15, 24, (7, 18, 30, 100)),
                       rectangle(-17, -22, 34, 40, (104, 226, 204)),
                       rectangle(-12, -16, 24, 13, (22, 53, 66)),
                       rectangle(-10, -12, 5, 4, (203, 251, 239)),
                       rectangle(5, -12, 5, 4, (203, 251, 239)),
                       rectangle(-12, 19, 9, 7, (60, 155, 151)),
                       rectangle(4, 19, 9, 7, (60, 155, 151))]

    def update(self, dt):
        self.elapsed += dt
        down = Keyboard.is_key_pressed
        x = int(down(Keyboard.D) or down(Keyboard.RIGHT)) - int(down(Keyboard.A) or down(Keyboard.LEFT))
        y = int(down(Keyboard.S) or down(Keyboard.DOWN)) - int(down(Keyboard.W) or down(Keyboard.UP))
        if x or y:
            length = (x*x+y*y)**0.5
            movement = Vector2(x/length, y/length) * (240 * dt)
            self.position += movement
            session = self.game.services["session"]
            session.distance += 240 * dt
            self.moved.emit(self.position)

    def render(self, target, states):
        for shape in self.shapes:
            target.draw(shape, states)


class FollowCamera(Camera):
    def __init__(self, target):
        super().__init__("FollowCamera")
        self.target = target
        self.position = target.position
        self.process_mode = "always"

    def update(self, dt):
        self.position += (self.target.position - self.position) * min(1, dt * 5)


class Overlay(Entity):
    def __init__(self, explorer):
        super().__init__("Overlay")
        self.explorer = explorer
        self.process_mode = "always"


    def handle_event(self, event):
        if event.type != Event.KEY_PRESSED:
            return False
        if event.code == Keyboard.P:
            self.game.paused = not self.game.paused
        elif event.code == Keyboard.R:
            self.explorer.position = (480, 300)
        elif event.code == Keyboard.ESCAPE:
            self.game.quit()
        else:
            return False
        return True

    def render(self, target, states):
        width, height = self.game.size
        target.draw(rectangle(0, 0, width, 106, (10, 20, 34, 225)), states)
        target.draw(rectangle(32, 31, 4, 45, (104, 226, 204)), states)
        target.draw(rectangle(0, height - 78, width, 78, (10, 20, 34, 235)), states)
        def text(value, x, y, size=16, color=(170, 192, 212)):
            label = Text(self.game.ui.theme.get_font(), value, size)
            label.position = (x, y)
            label.fill_color = Color(*color)
            target.draw(label, states)
        text("Doku2D", 50, 20, 30, (235, 245, 250))
        text("Independent objects. Shared canvases.", 52, 62, 15)
        status = "PAUSED" if self.game.paused else "EXPLORING"
        text(status, width - 180, 29, 16, (104, 226, 204))
        text(f"{len(self.game.objects)} objects / 4 canvases", width - 180, 58, 13)
        text("WASD / ARROWS  Move", 32, height - 60, 16, (230, 239, 246))
        text("P  Pause       R  Reset       ESC  Close", 32, height - 33, 14)
        position = self.explorer.position
        text(f"X {position.x:7.0f}   Y {position.y:7.0f}", width - 270, height - 59, 15)
        distance = self.game.services["session"].distance
        text(f"Travelled {distance:,.0f} px", width - 270, height - 32, 14)


def create_demo():
    game = Game(title="Doku2D | Independent Objects", size=(1100, 700),
                services={"session": Session})
    sky = Canvas("Sky", order=-3, screen_space=True)
    distance = Canvas("Distant", order=-2, parallax=(0.2, 0.2))
    terrain = game.world
    interface = Canvas("Interface", order=10, screen_space=True)
    random = Random(12)
    sky_shapes = [rectangle(0, 0, 4000, 2000, (16, 32, 53)),
                  circle(770, 145, 52, (184, 213, 218)),
                  circle(788, 135, 50, (16, 32, 53))]
    for _ in range(70):
        x, y = random.randrange(20, 1600), random.randrange(120, 600)
        sky_shapes.append(circle(x, y, random.choice([1, 1, 2]), (117, 158, 185, 150)))
    game.add(Landscape("Sky", sky_shapes), canvas=sky)
    hills = []
    for index in range(-12, 18):
        x = index * 170
        hills.append(circle(x, 345 + sin(index*1.3)*55, 160, (28, 57, 76)))
        hills.append(rectangle(x, 485, 180, 1200, (28, 57, 76)))
    game.add(Landscape("Horizon", hills), canvas=distance)
    ground = []
    for x in range(-1600, 2400, 100):
        for y in range(-1000, 1800, 100):
            ground.append(rectangle(x, y, 2, 2, (75, 115, 134, 90)))
    # Landmarks make camera movement and parallax immediately visible.
    for i, (x,y) in enumerate([(200,230),(780,390),(100,650),(920,100),(-250,120),(1100,700)]):
        ground.extend([circle(x-27,y+6,28,(6,22,32,90)),
                       rectangle(x-16,y-52,32,75,(45,89,103)),
                       rectangle(x-22,y-58,44,12,(73,134,144)),
                       rectangle(x-4,y-47,8,20,(102,207,189))])
    game.add(Landscape("Terrain", ground), canvas=terrain)
    explorer = game.add(Explorer())
    game.add(FollowCamera(explorer))
    game.add(Overlay(explorer), canvas=interface)
    return game


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=None)
    args = parser.parse_args()
    create_demo().run(max_frames=args.frames)
