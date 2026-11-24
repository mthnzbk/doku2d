"""Interactive engine checks in the example gallery."""
from pathlib import Path

from sfml.graphics import Image, PrimitiveType, Texture, Vertex, VertexArray

from doku2d import (AnimatedSprite, Button, CharacterBody, CheckButton, Color, DragData,
                    Entity, Game, Label, MapData, TileMap, TileMapStream, TileSet, Tree)
from doku2d.gui.theme import box


ASSETS = Path(__file__).with_name('assets')
GRID = 36
ORIGIN = (392, 158)
CELLS = (16, 10)
WALL_X = 8
OPEN_ROWS = (4, 5)


class Floor(Entity):
    def __init__(self, tint):
        super().__init__()
        self.position = ORIGIN
        self.z_index = -10
        self.tiles = VertexArray(PrimitiveType.TRIANGLES)
        colors = Color(*tint), Color(*(channel-7 for channel in tint))
        for y in range(CELLS[1]):
            for x in range(CELLS[0]):
                x0, y0 = GRID*x, GRID*y
                x1, y1 = x0+GRID-1, y0+GRID-1
                for point in ((x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)):
                    self.tiles.append(Vertex(point, colors[(x+y) % 2]))

    def render(self, target, states):
        target.draw(self.tiles, states)


class Column(Entity):
    def __init__(self, row):
        super().__init__()
        self.position = ORIGIN[0]+GRID*(WALL_X+.5), ORIGIN[1]+GRID*(row+.5)
        self.y_sort_offset = 12

    def render(self, target, states):
        box(target, states, (-17, -31, 34, 45), (50, 74, 86), radius=5)
        box(target, states, (-17, -36, 34, 22), (113, 144, 151), radius=5)
        box(target, states, (-11, -7, 22, 10), (67, 96, 106), radius=2)


class EngineDemo(Entity):
    def on_ready(self):
        self.room = 0
        self.steps = 0
        self.follower = None
        self.game.world.y_sort = True
        self.wall_tiles = TileSet(Texture.from_image(Image.from_size(GRID, GRID, Color.TRANSPARENT)),
                                  tile_size=(GRID, GRID))
        self.wall_tiles.set_solid(0)

        def place(control, x, y, width, height):
            control.position, control.size = (x, y), (width, height)
            return self.game.add(control)

        place(Label(text='Motor özellikleri'), 24, 10, 520, 34).font_size = 24
        place(Label(text='Görevleri klasörler arasında sürükle'), 24, 83, 337, 33)
        self.tree = place(Tree(), 24, 123, 337, 271)
        pending = self.tree.add_item('Bekleyenler')
        done = self.tree.add_item('Tamamlananlar')
        for text in ('Haritayı aç', 'Feneri yak', 'Kayıt noktasına dön'):
            self.tree.add_item(text, parent=pending, data='task')

        def drag(point):
            item = self.tree.item_at(point)
            if item is not None and item.data == 'task':
                return DragData(item, item.text)

        self.tree.drag_source = drag
        self.tree.drop_filter = lambda point, item: self.tree.item_at(point) in (pending, done)
        self.tree.dropped.connect(self.drop_task)
        self.task_status = place(Label(), 24, 400, 337, 32)
        sort = place(CheckButton(text='Y sıralaması'), 24, 455, 337, 42)
        sort.button_pressed = True
        sort.toggled.connect(self.set_y_sort)

        self.title = place(Label(), 392, 81, 576, 34)
        place(Label(text='NPC bir sonraki bölgeye taş sütunların arasından geçer.'), 392, 116, 576, 25)
        for text, x, cell in (('Sola git', 392, (1, 2)), ('Sağa git', 533, (14, 7))):
            place(Button(text=text), x, 537, 129, 40).pressed.connect(lambda cell=cell: self.navigate(cell))
        self.transition_button = place(Button(text='Bölümü değiştir'), 674, 537, 172, 40)
        self.transition_button.pressed.connect(self.change_room)
        self.status = place(Label(), 392, 597, 576, 26)
        self.status.font_size = 14

        self.room_scope = self.game.create_scope()
        self.build_room(self.room_scope, 0)

    def set_y_sort(self, enabled):
        self.game.world.y_sort = enabled

    def drop_task(self, item, point):
        folder = self.tree.item_at(point)
        self.tree.move_item(item, parent=folder)
        self.tree.set_expanded(folder, True)
        self.task_status.text = f'{item.text}, {folder.text} klasörüne taşındı.'

    def load_chunk(self, origin, size):
        tilemap = TileMap(MapData(size=size, tile_size=(GRID, GRID)))
        tilemap.add_tileset(self.wall_tiles)
        walls = tilemap.add_layer('Walls')
        if origin[0] <= WALL_X < origin[0]+size[0]:
            for y in range(size[1]):
                if origin[1]+y not in OPEN_ROWS:
                    walls.set_cell((WALL_X-origin[0], y), 0)
        tilemap.enable_collisions('Walls')
        return tilemap

    def build_room(self, scope, room):
        self.room = room
        self.steps = 0
        self.follower = None
        scope.add(Floor(((55, 83, 73), (87, 77, 68))[room]))
        for row in range(CELLS[1]):
            if row not in OPEN_ROWS:
                scope.add(Column(row))

        start = ORIGIN[0]+GRID*1.5, ORIGIN[1]+GRID*2.5
        self.actor = scope.add(CharacterBody(position=start, radius=9))
        self.actor.y_sort_offset = 12
        self.stream = scope.add(TileMapStream(self.load_chunk, size=CELLS, target=self.actor,
                                              position=ORIGIN, chunk_size=(4, 5), tile_size=(GRID, GRID), radius=0))
        sprite = self.actor.sprite = AnimatedSprite(ASSETS / 'platform/hero.png', frame_size=(24, 32))
        sprite.scale = (1.45, 1.45)
        sprite.offset = (0, -4)
        sprite.add_animation('idle', range(4), fps=4)
        sprite.add_animation('run', range(4, 8), fps=8, markers={1: 'adım', 3: 'adım'})
        self.motion = sprite.follow_motion(self.actor, directions=8, run_speed=125)
        sprite.marker_reached.connect(self.count_step)
        self.title.text = ('Bölüm 1 · Yeşil avlu', 'Bölüm 2 · Taş avlu')[room]

    def count_step(self, marker, animation, frame):
        self.steps += 1

    def navigate(self, cell):
        self.follower = self.actor.navigate_to(self.stream, self.stream.map_to_world(cell),
                                               speed=125, diagonal=True)

    def change_room(self):
        self.transition_button.disabled = True
        room = 1-self.room
        transition = self.game.transition(self.build_room, old_scope=self.room_scope,
                                          preload=('platform/hero.png', 'world/beacon.wav'),
                                          prepare=lambda: room, fade_out=.35, fade_in=.35,
                                          loading_text='Bölüm yükleniyor')
        transition.finished.connect(self.room_changed)
        transition.failed.connect(self.transition_failed)

    def room_changed(self, scope):
        self.room_scope = scope
        self.transition_button.disabled = False

    def transition_failed(self, error):
        self.transition_button.disabled = False
        self.task_status.text = f'Bölüm yüklenemedi: {error}'

    def update(self, dt):
        state = self.follower.state if self.follower is not None else 'waiting'
        state = {'waiting': 'hazır', 'moving': 'yürüyor', 'arrived': 'ulaştı', 'stopped': 'durdu'}[state]
        self.status.text = (f'NPC {state}   ·   Yön {self.motion.facing}   ·   '
                            f'Adım işareti {self.steps}   ·   Yüklü parça {len(self.stream.loaded_chunks)}')


def make_demo():
    game = Game(title='Doku2D | Motor Özellikleri', size=(1000, 680), asset_root=ASSETS, debug=True)
    game.clear_color = Color(20, 28, 41)
    demo = game.add(EngineDemo())
    game.flush_deferred()
    return game, demo
