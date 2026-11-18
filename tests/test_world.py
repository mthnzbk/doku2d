import base64
import gzip
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib
from sfml.graphics import Color, Image, RenderTexture, Texture, RectangleShape
from sfml.system import Vector2, seconds
from sfml.audio import Status
from doku2d import (Entity, Game, Canvas, Camera, AudioListener, AudioPlayer,
                    PositionalAudio, TileSet, TileMap, TiledParser, TileCell)


class TiledTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def write(self,name,data):
        path = self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data) if isinstance(data,dict) else data,encoding='utf-8')
        return path
    def raw(self):
        return dict(orientation='orthogonal',width=2,height=1,tilewidth=8,tileheight=8,
                    tilesets=[dict(firstgid=1,name='atlas',tilewidth=8,tileheight=8,
                                   image='atlas.png',imagewidth=16,imageheight=8,columns=2,tilecount=2)],
                    layers=[dict(name='Ground',type='tilelayer',width=2,height=1,data=[1,2])])

    def test_json_external_tileset_groups_objects_and_cpu_only_parse(self):
        raw = self.raw()
        ts = raw['tilesets'][0]
        del ts['firstgid']
        self.write('tiles/atlas.tsj',ts)
        raw['tilesets'] = [dict(firstgid=1,source='tiles/atlas.tsj')]
        raw['layers'] = [dict(name='World',type='group',offsetx=10,offsety=20,opacity=.5,
                              tintcolor='#80ffffff',parallaxx=.5,layers=[
                                  dict(name='Ground',type='tilelayer',width=2,height=1,data=[0x80000001,0x10000002],opacity=.5),
                                  dict(name='Spawns',type='objectgroup',objects=[dict(id=3,name='start',x=4,y=8,
                                       properties=[dict(name='speed',type='float',value=3.5),dict(name='script',type='file',value='spawn.py')])])])]
        raw['properties'] = [dict(name='sky',type='color',value='#80402010')]
        with patch('doku2d.rendering.tilemap.Texture') as gpu:
            gpu.from_file.side_effect = AssertionError('GPU load during parsing')
            data = TiledParser.parse(self.write('map.tmj',raw))
        self.assertEqual(data.tilesets[0].image,self.root/'tiles/atlas.png')
        self.assertEqual(data.layers[0].name,'World/Ground')
        self.assertEqual(data.layers[0].offset,(10,20))
        self.assertEqual(data.layers[0].opacity,.25)
        self.assertEqual(data.layers[0].tint,(255,255,255,128))
        self.assertEqual(data.layers[0].parallax,(.5,1))
        self.assertTrue(data.layers[0].cells[0,0].flip_h)
        self.assertEqual(data.layers[0].cells[1,0].tile_id,1)
        obj = data.layers[1].objects[0]
        self.assertEqual(obj.position,(14,28))
        self.assertEqual(obj.properties['script'],self.root/'spawn.py')
        self.assertEqual(data.properties['sky'],(64,32,16,128))

    def test_tmx_tsx_csv_animation_and_fractional_objects(self):
        self.write('tiles/a.tsx','''<tileset name="atlas" tilewidth="8" tileheight="8" tilecount="2" columns="2">
          <image source="a.png" width="16" height="8"/>
          <tile id="0"><animation><frame tileid="0" duration="100"/><frame tileid="1" duration="200"/></animation>
          <properties><property name="solid" type="bool" value="true"/></properties></tile></tileset>''')
        xml = '''<map orientation="orthogonal" width="2" height="1" tilewidth="8" tileheight="8">
          <tileset firstgid="1" source="tiles/a.tsx"/>
          <layer name="Ground" width="2" height="1"><data encoding="csv">1,2</data></layer>
          <objectgroup name="Objects"><object id="1" name="spawn" x="1.5" y="2.5" width="3.5" height="4.5"><point/>
          <properties><property name="value" type="int" value="7"/></properties></object></objectgroup></map>'''
        data = TiledParser.parse(self.write('map.tmx',xml))
        self.assertEqual(data.layers[0].cells[1,0],TileCell(1))
        self.assertEqual(data.tilesets[0].tiles[0]['animation'],((0,.1),(1,.2)))
        self.assertTrue(data.tilesets[0].tiles[0]['properties']['solid'])
        self.assertEqual(data.layers[1].objects[0].size,(3.5,4.5))
        self.assertEqual(data.layers[1].objects[0].shape,'point')

    def test_base64_compression_and_infinite_negative_chunks(self):
        for compression,compress in ((None,lambda x:x),('zlib',zlib.compress),('gzip',gzip.compress)):
            raw = self.raw()
            layer = raw['layers'][0]
            payload = base64.b64encode(compress(struct.pack('<II',1,0x60000002))).decode()
            layer.update(encoding='base64',compression=compression,data=payload)
            data = TiledParser.parse(self.write('map.tmj',raw))
            self.assertTrue(data.layers[0].cells[1,0].flip_v)
            self.assertTrue(data.layers[0].cells[1,0].transpose)
            raw['infinite'] = True
            layer['chunks'] = [dict(x=-3,y=-2,width=2,height=1,data=payload)]
            data = TiledParser.parse(self.write('map.tmj',raw))
            self.assertIn((-3,-2),data.layers[0].cells)
            compression_attr = f' compression="{compression}"' if compression else ''
            xml = (f'<map orientation="orthogonal" infinite="1" width="0" height="0" tilewidth="8" tileheight="8">'
                   f'<tileset firstgid="1" name="a" tilewidth="8" tileheight="8" columns="2" tilecount="2">'
                   f'<image source="a.png" width="16" height="8"/></tileset>'
                   f'<layer name="a" width="0" height="0"><data encoding="base64"{compression_attr}>'
                   f'<chunk x="-3" y="-2" width="2" height="1">{payload}</chunk></data></layer></map>')
            self.assertEqual(TiledParser.parse(self.write('infinite.tmx',xml)).layers[0].cells[-2,-2].tile_id,1)

        xml = '<map orientation="orthogonal" width="1" height="1" tilewidth="8" tileheight="8"><tileset firstgid="1" source="tiles/a.tsx"/><layer name="a" width="1" height="1"><data><tile gid="1"/></data></layer></map>'
        self.write('tiles/a.tsx','<tileset name="a" tilewidth="8" tileheight="8" columns="1" tilecount="1"><image source="a.png" width="8" height="8"/></tileset>')
        self.assertEqual(TiledParser.parse(self.write('map.tmx',xml)).layers[0].cells[0,0].tile_id,0)

    def test_rejects_invalid_dimensions_gids_orientation_and_compression(self):
        raw = self.raw()
        raw['layers'][0]['data'] = [1]
        with self.assertRaises(ValueError): TiledParser.parse(self.write('map.tmj',raw))
        raw['layers'][0]['data'] = [1,50]
        with self.assertRaises(ValueError): TiledParser.parse(self.write('map.tmj',raw))
        raw['orientation'] = 'isometric'
        with self.assertRaises(NotImplementedError): TiledParser.parse(self.write('map.tmj',raw))


class TileRenderingTests(unittest.TestCase):
    def atlas(self):
        image = Image.create(16,8,Color.BLUE)
        colors = (Color.RED,Color.GREEN,Color.YELLOW,Color.MAGENTA)
        for x in range(8):
            for y in range(8): image[x,y] = colors[(y//4)*2+x//4]
        return TileSet(Texture.from_image(image),tile_size=(8,8))
    def image(self,game):
        target = RenderTexture(*game.size)
        target.clear(Color.BLACK)
        game.flush_deferred()
        game.render(target)
        target.display()
        return target.texture.to_image()
    def rgb(self,image,x,y):
        p=image[x,y]
        return p.r,p.g,p.b

    def test_all_tiled_flip_combinations_and_layer_cache_edits(self):
        game = Game(size=(64,8))
        tilemap = game.add(TileMap(tile_set=self.atlas()))
        layer = tilemap.add_layer('ground')
        for i in range(8): layer.set_cell((i,0),0,flip_h=bool(i&1),flip_v=bool(i&2),transpose=bool(i&4))
        image = self.image(game)
        colors = ((255,0,0),(0,255,0),(255,255,0),(255,0,255))
        for i in range(8):
            u,v = bool(i&1),bool(i&2)
            if i&4: u,v = v,u
            self.assertEqual(self.rgb(image,i*8+1,1),colors[int(v)*2+int(u)])
        cached = layer._meshes.copy()
        layer.set_cell((0,0),1)
        self.assertEqual(self.rgb(self.image(game),1,1),(0,0,255))
        layer.erase_cell((0,0))
        self.assertEqual(self.rgb(self.image(game),1,1),(0,0,0))
        self.assertTrue(cached)
        game.close()
        self.assertIsNone(layer.game)

    def test_layers_interleave_entities_visibility_and_cleanup(self):
        game = Game(size=(8,8))
        tilemap = game.add(TileMap(tile_set=self.atlas()))
        ground = tilemap.add_layer('ground',z_index=0)
        ground.set_cell((0,0),0)
        class Green(Entity):
            def render(self,target,states):
                shape=RectangleShape((8,8));shape.fill_color=Color.GREEN;target.draw(shape,states)
        player=game.add(Green());player.z_index=1
        front = tilemap.add_layer('front',z_index=2)
        front.set_cell((0,0),1)
        self.assertEqual(self.rgb(self.image(game),1,1),(0,0,255))
        front.visible = False
        self.assertEqual(self.rgb(self.image(game),1,1),(0,255,0))
        front.visible = True
        tilemap.visible = False
        self.assertEqual(self.rgb(self.image(game),1,1),(0,255,0))
        game.remove(tilemap)
        game.flush_deferred()
        self.assertNotIn(front,game.objects)
        game.close()

    def test_negative_cells_transforms_bounds_and_chunk_resize(self):
        game = Game(size=(32,16))
        tilemap = game.add(TileMap(tile_set=self.atlas()))
        tilemap.infinite=True
        tilemap.position=(16,0)
        layer=tilemap.add_layer('ground')
        layer.set_cell((-1,0),1)
        layer.set_cell((1,1),1)
        tilemap.chunk=(1,1)
        self.assertEqual(tilemap.bounds,(-8,0,24,16))
        self.assertEqual(tilemap.world_bounds,(8,0,24,16))
        self.assertEqual(tilemap.world_to_map(tilemap.map_to_world((-1,0))),(-1,0))
        self.assertEqual(self.rgb(self.image(game),9,1),(0,0,255))
        layer.clear()
        self.assertEqual(layer.used_rect,(0,0,0,0))
        game.close()

    def test_animation_updates_mesh_and_pauses(self):
        game=Game(size=(8,8))
        tileset=self.atlas()
        tileset._tiles[0]={'animation':((0,.1),(1,.1))}
        tilemap=game.add(TileMap(tile_set=tileset))
        layer=tilemap.add_layer('ground');layer.set_cell((0,0),0)
        self.assertEqual(self.rgb(self.image(game),1,1),(255,0,0))
        game.update(.11)
        self.assertEqual(self.rgb(self.image(game),1,1),(0,0,255))
        game.paused=True;game.update(.11)
        self.assertEqual(self.rgb(self.image(game),1,1),(0,0,255))
        game.close()

    def test_rectangular_diagonal_flip_swaps_dimensions_without_stretching(self):
        image=Image.create(16,8,Color.RED)
        for x in range(8,16):
            for y in range(8): image[x,y]=Color.GREEN
        tileset=TileSet(Texture.from_image(image),tile_size=(16,8))
        game=Game(size=(32,32))
        tilemap=game.add(TileMap(tile_set=tileset,tile_size=(16,16)))
        layer=tilemap.add_layer('ground');layer.set_cell((0,1),0,transpose=True)
        result=self.image(game)
        self.assertEqual(self.rgb(result,1,17),(255,0,0))
        self.assertEqual(self.rgb(result,1,25),(0,255,0))
        self.assertEqual(self.rgb(result,10,25),(0,0,0))
        game.close()

    def test_collection_images_tile_objects_repeating_image_layer_and_tint(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            Image.create(8,8,Color.RED).to_file(str(root/'red.png'))
            raw=dict(orientation='orthogonal',width=4,height=2,tilewidth=8,tileheight=8,
                     tilesets=[dict(firstgid=1,name='collection',tilewidth=8,tileheight=8,columns=0,tilecount=1,
                                    tiles=[dict(id=5,image='red.png',imagewidth=8,imageheight=8)])],
                     layers=[dict(name='background',type='imagelayer',image='red.png',repeatx=True,repeaty=True,tintcolor='#ff00ff00'),
                             dict(name='objects',type='objectgroup',offsetx=8,objects=[dict(id=1,x=0,y=16,width=16,height=16,gid=6)])])
            path=root/'map.tmj';path.write_text(json.dumps(raw),encoding='utf-8')
            game=Game(size=(32,16));tilemap=game.add(TileMap.from_tiled(path))
            image=self.image(game)
            self.assertEqual(self.rgb(image,9,1),(255,0,0))
            self.assertEqual(self.rgb(image,1,1),(0,0,0))
            tilemap.layers['background'].tint=(255,255,255)
            self.assertEqual(self.rgb(self.image(game),31,1),(255,0,0))
            game.close()

    def test_chunks_are_culled_and_persistent_layers_survive_replace(self):
        game=Game(size=(8,8))
        tilemap=game.add(TileMap(tile_set=self.atlas()),persistent=True)
        layer=tilemap.add_layer('ground');layer.fill((0,0,1000,1),1)
        self.image(game)
        self.assertLessEqual(len(layer._meshes),2)
        game.replace(Entity());game.flush_deferred()
        self.assertIs(layer.game,game)
        game.remove(tilemap);game.flush_deferred()
        self.assertIsNone(layer.game)
        game.add(tilemap);game.flush_deferred()
        self.assertIs(layer.game,game)
        game.close()


class CameraTests(unittest.TestCase):
    def test_follow_order_deadzone_smoothing_and_reset(self):
        game=Game(size=(100,100))
        target=Entity();target.position=(200,200)
        camera=game.add(Camera(target=target))
        game.add(target)
        camera.follow(target,smoothing=8,dead_zone=(40,20))
        target.position=(210,205);game.update(.1)
        self.assertEqual(tuple(camera.screen_center),(200,200))
        target.position=(300,200);game.update(.1)
        self.assertGreater(camera.screen_center.x,200)
        self.assertLess(camera.screen_center.x,280)
        camera.reset_smoothing()
        self.assertEqual(tuple(camera.screen_center),(300,200))
        game.close()

    def test_bounds_zoom_rotation_shake_and_screen_space(self):
        game=Game(size=(100,80))
        camera=game.add(Camera());camera.bounds=(0,0,200,100)
        camera.position=(-100,-100)
        self.assertEqual(tuple(camera.screen_center),(50,40))
        camera.zoom=(2,2)
        self.assertEqual(tuple(camera.screen_center),(25,20))
        camera.bounds=(0,0,20,20)
        self.assertEqual(tuple(camera.screen_center),(10,10))
        camera.bounds=(0,0,1000,1000);camera.position=(500,500)
        game.update(0)
        original=tuple(camera.position)
        camera.shake(10,.2);game.update(.05)
        self.assertNotEqual(tuple(camera.screen_center),original)
        self.assertEqual(tuple(camera.position),original)
        screen=Canvas(screen_space=True)
        self.assertEqual(tuple(game.make_view(screen).center),(50,40))
        game.update(.2)
        self.assertEqual(tuple(camera.screen_center),original)
        camera.rotation_smoothing=True;camera.rotation=350;game.update(.1)
        self.assertLess(camera.view_rotation,0)
        game.close()


class FakeVoice:
    def __init__(self,buffer=None):
        self.status=Status.STOPPED
        self.playing_offset=seconds(0)
    def play(self): self.status=Status.PLAYING
    def pause(self): self.status=Status.PAUSED
    def stop(self): self.status=Status.STOPPED


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.sound_patch=patch('doku2d.audio.audio.Sound',FakeVoice);self.sound_patch.start()
        self.buffer_patch=patch('doku2d.core.resource.SoundBuffer');self.load=self.buffer_patch.start().from_file
        self.load.return_value=object()
        self.game=Game(size=(200,100))
    def tearDown(self):
        self.game.close();self.sound_patch.stop();self.buffer_patch.stop()

    def test_play_pause_game_pause_polyphony_stop_and_finished(self):
        player=self.game.add(AudioPlayer('test.wav',autoplay=True))
        self.assertTrue(player.playing)
        first=player._voices[0]
        self.game.paused=True;self.game.update(.01)
        self.assertEqual(first.status,Status.PAUSED)
        self.game.paused=False;self.game.update(.01)
        self.assertEqual(first.status,Status.PLAYING)
        player.pause();self.game.update(.01)
        self.assertEqual(first.status,Status.PAUSED)
        player.resume();player.max_polyphony=2;player.play(.2)
        self.assertEqual(len(player._voices),2)
        self.assertAlmostEqual(player.get_playback_position(),.2)
        player.seek(.5);self.assertEqual(first.playing_offset.seconds,.5)
        player.play();self.assertEqual(first.status,Status.STOPPED)
        calls=[];player.finished.connect(lambda:calls.append(True))
        for voice in player._voices:voice.stop()
        self.game.update(.01);self.game.update(.01)
        self.assertEqual(calls,[True])
        player.play();player.stop();self.game.update(.01)
        self.assertEqual(calls,[True])
        self.assertEqual(self.load.call_count,1)

    def test_positional_distance_pan_listener_target_and_camera_fallback(self):
        target=self.game.add(Entity());target.position=(100,100)
        listener=self.game.add(AudioListener(target=target))
        source=self.game.add(PositionalAudio('test.wav'))
        source.max_distance=100;source.panning_distance=100
        source.position=(150,100);source.play()
        voice=source._voices[0]
        self.assertAlmostEqual(voice.volume,50)
        self.assertAlmostEqual(voice.pan,.5)
        target.position=(200,100);self.game.update(.01)
        self.assertAlmostEqual(voice.volume,50)
        self.assertAlmostEqual(voice.pan,-.5)
        source.position=(200,250);self.game.update(.01)
        self.assertEqual(voice.volume,0)
        self.game.remove(listener)
        camera=self.game.add(Camera());camera.position=(150,100)
        source.position=(150,100);self.game.update(.01)
        self.assertEqual(voice.volume,100)
        self.assertEqual(voice.pan,0)
        self.game.remove(source)
        self.assertEqual(voice.status,Status.STOPPED)

    def test_always_audio_continues_when_paused_and_streaming(self):
        with patch('doku2d.audio.audio.Music') as music:
            load=music.from_file
            load.side_effect=lambda path:FakeVoice()
            player=self.game.add(AudioPlayer('music.ogg',stream=True,loop=True))
            player.process_mode='always';player.play()
            self.assertTrue(player._voices[0].loop)
            self.game.paused=True;self.game.update(.01)
            self.assertEqual(player._voices[0].status,Status.PLAYING)
            self.assertEqual(load.call_count,1)
            player.volume_db=-6
            self.assertAlmostEqual(player._voices[0].volume,50.1187,places=3)


if __name__=='__main__':unittest.main()
