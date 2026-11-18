import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from sfml.system import Vector2
from sfml.window import Event
from sfml.graphics import Image,Texture,Color,RenderTexture
from doku2d import (Game,CharacterBody,StaticBody,AnimatableBody,RigidBody,Polygon,Segment,
                    TileMap,TileSet,TiledParser,AnimatedSprite,AutoTile,MapObject,TileCell)


class PlatformPhysicsTests(unittest.TestCase):
    def setUp(self):
        self.game=Game();self.game.physics.gravity=(0,900)
    def tearDown(self):self.game.close()
    def step(self,p,count=1):
        for _ in range(count):p.move_and_slide();self.game.update(1/60)
    def player(self,position=(0,0)):
        return self.game.add(CharacterBody(position=position,size=(20,30),motion_mode='grounded'))
    def floor(self):return self.game.add(StaticBody(position=(0,100),size=(800,20)))

    def test_floor_jump_ceiling_landing_and_wall_classification(self):
        p=self.player();self.floor()
        self.step(p,60)
        self.assertTrue(p.is_on_floor());self.assertFalse(p.is_on_wall())
        self.assertAlmostEqual(p.position.y,75,delta=.3)
        self.game.add(StaticBody(position=(0,0),size=(200,10)))
        self.assertTrue(p.jump(420));self.assertFalse(p.jump(420))
        ceiling=False
        for _ in range(60):
            self.step(p);ceiling=ceiling or p.is_on_ceiling()
        self.assertTrue(ceiling);self.assertTrue(p.is_on_floor())
        self.game.add(StaticBody(position=(80,50),size=(20,100)))
        for _ in range(60):p.velocity=(180,p.velocity.y);self.step(p)
        self.assertTrue(p.is_on_wall());self.assertTrue(p.is_on_floor())
        self.assertLess(p.position.x,61)

    def test_slope_standing_walking_and_max_angle(self):
        self.game.add(StaticBody(shape=Polygon(((-100,150),(100,50),(100,150)))))
        p=self.player((-70,0));self.step(p,60)
        self.assertTrue(p.is_on_floor());self.assertAlmostEqual(p.get_floor_angle(),26.565,delta=.2)
        position=p.position;self.step(p,60)
        self.assertLess(abs(p.position.x-position.x),.5)
        for _ in range(90):p.velocity=(50,p.velocity.y);self.step(p)
        self.assertGreater(p.position.x,position.x+45)
        self.assertLess(p.position.y,position.y-20)
        self.assertTrue(p.is_on_floor())
        p.max_angle=20;self.step(p,3)
        self.assertFalse(p.is_on_floor())

    def test_moving_platform_carry_vertical_motion_and_jump_momentum(self):
        p=self.player((0,50))
        platform=self.game.add(AnimatableBody(position=(0,100),size=(140,20)))
        self.step(p,30);start=p.position
        for _ in range(60):
            platform.move_to(platform.position+(1,-.25));p.velocity=(0,p.velocity.y);self.step(p)
        self.assertAlmostEqual(p.position.x,start.x+60,delta=.3)
        self.assertAlmostEqual(p.position.y,start.y-15,delta=.3)
        self.assertTrue(p.is_on_floor())
        self.assertAlmostEqual(p.get_platform_velocity().x,60,delta=.01)
        p.jump(300);platform.position+=(1,-.25);self.step(p)
        self.assertFalse(p.is_on_floor());self.assertGreater(p.velocity.x,59)

    def test_thin_wall_at_high_speed_and_force_with_substeps(self):
        self.game.physics.gravity=(0,0)
        p=self.game.add(CharacterBody(size=(10,10)))
        self.game.add(StaticBody(position=(50,0),size=(2,200)))
        p.velocity=(2400,0);self.step(p,5)
        self.assertLess(p.position.x,45)
        body=self.game.add(RigidBody(position=(0,300),mass=2))
        body.apply_force((120,0));self.game.update(1/60)
        self.assertAlmostEqual(body.velocity.x,1,places=5)

    def test_floor_snap_across_small_down_step(self):
        self.game.add(StaticBody(position=(-50,100),size=(100,20)))
        self.game.add(StaticBody(position=(50,103),size=(100,20)))
        p=self.player((-30,0));self.step(p,60)
        airborne=0
        for _ in range(60):
            p.velocity=(60,p.velocity.y);self.step(p)
            airborne+=not p.is_on_floor()
        self.assertEqual(airborne,0)
        self.assertAlmostEqual(p.position.y,78,delta=.3)

    def test_constant_slope_speed_and_optional_sliding(self):
        self.game.add(StaticBody(shape=Polygon(((-200,200),(200,0),(200,200)))))
        p=self.player((-100,0));self.step(p,60)
        p.constant_speed=True
        for _ in range(20):p.velocity=(60,p.velocity.y);self.step(p)
        real=p.get_real_velocity()
        self.assertAlmostEqual((real.x*real.x+real.y*real.y)**.5,60,delta=2)
        p.constant_speed=False;p.stop_on_slope=False;p.velocity=(0,0)
        start=p.position.x;self.step(p,30)
        self.assertLess(p.position.x,start-1)

    def test_platform_layer_mask_and_leave_without_momentum(self):
        platform=self.game.add(AnimatableBody(position=(0,100),size=(200,20)))
        p=self.player((0,40));self.step(p,30)
        p.floor_layers=0
        for _ in range(15):platform.position+=(1,0);p.velocity=(0,p.velocity.y);self.step(p)
        self.assertAlmostEqual(p.position.x,0,delta=.1)
        p.floor_layers=1;p.on_leave='none'
        for _ in range(5):platform.position+=(1,0);p.velocity=(0,p.velocity.y);self.step(p)
        self.assertTrue(p.jump(300));platform.position+=(1,0);self.step(p)
        self.assertAlmostEqual(p.velocity.x,0,delta=.1)

    def test_rotating_platform_reports_contact_point_velocity(self):
        platform=self.game.add(AnimatableBody(position=(0,100),size=(200,20)))
        p=self.player((40,40));self.step(p,30)
        for _ in range(8):platform.rotation+=.25;p.velocity=(0,p.velocity.y);self.step(p)
        self.assertTrue(p.is_on_floor())
        self.assertGreater(p.get_platform_velocity().y,5)
        self.assertGreater(p.position.y,75)


    def test_rigid_sleep_and_impulse_wakeup(self):
        self.game.physics.gravity=(0,0)
        body=self.game.add(RigidBody(position=(0,300)))
        body.sleeping=True
        self.game.update(1/60)
        self.assertTrue(body.sleeping)
        body.apply_impulse((100,0));self.game.update(1/60)
        self.assertFalse(body.sleeping)
        self.assertGreater(body.position.x,0)


class AutotileTests(unittest.TestCase):
    def tiles(self):
        image=Image.create(64,8,Color.RED)
        for x in range(64):
            for y in range(4,8):image[x,y]=Color.BLUE
        return TileSet(Texture.from_image(image),tile_size=(4,4))
    def test_paint_erase_negative_coordinates_and_neighbors(self):
        ts=self.tiles();ts.add_autotile('water',range(16))
        world=TileMap(tile_set=ts);layer=world.add_layer('water')
        layer.paint_terrain([(-1,0),(0,0),(1,0)],'water')
        self.assertEqual([layer.get_cell((x,0)).tile_id for x in (-1,0,1)],[2,10,8])
        layer.erase_cell((0,0))
        self.assertEqual(layer.get_cell((-1,0)).tile_id,0)
        self.assertEqual(layer.get_cell((1,0)).tile_id,0)
        self.assertEqual(len(layer.terrains),2)
    def test_blob_corners_require_both_adjacent_sides(self):
        rule=AutoTile('blob',{0:0,3:1,19:2},mode='blob')
        self.assertEqual(rule.mask(lambda x,y:(x,y)==(1,-1)),0)
        neighbors={(0,-1),(1,0),(1,-1)}
        self.assertEqual(rule.mask(lambda x,y:(x,y) in neighbors),19)
        self.assertEqual(rule.choose(19),2)
        self.assertEqual(rule.choose(255),0)
    def test_animated_autotile_keeps_time_when_neighbor_changes(self):
        ts=self.tiles()
        ts.add_autotile('water',range(16))
        for i in range(16):ts.add_animation(i,[i,i+16],fps=5)
        game=Game(size=(12,4));world=game.add(TileMap(tile_set=ts));layer=world.add_layer('water')
        layer.set_terrain((0,0),'water');game.update(.21)
        layer.set_terrain((1,0),'water')
        target=RenderTexture(12,4);target.clear(Color.BLACK);game.render(target);target.display()
        image=target.texture.to_image()
        self.assertEqual((image[1,1].r,image[1,1].b),(0,255))
        self.assertEqual((image[5,1].r,image[5,1].b),(0,255))
        self.assertEqual(layer.get_cell((0,0)).tile_id,2)
        game.close()
    def test_existing_tiles_connect_and_different_terrain_stays_separate(self):
        ts=self.tiles();ts.add_autotile('water',range(16));ts.add_autotile('lava',range(16,32))
        world=TileMap(tile_set=ts);layer=world.add_layer('ground')
        layer.set_cell((0,0),0);layer.set_terrain((1,0),'water')
        self.assertEqual(layer.get_cell((0,0)).tile_id,2)
        layer.set_terrain((2,0),'lava')
        self.assertEqual(layer.get_cell((1,0)).tile_id,8)
        self.assertEqual(layer.get_cell((2,0)).tile_id,16)
    def test_wang_edge_import_json_and_tmx(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);Image.create(64,4,Color.RED).to_file(str(root/'atlas.png'))
            wang=dict(name='Water',type='edge',colors=[dict(name='blue')])
            wang['wangtiles']=[dict(tileid=i,wangid=[int(bool(i&(1<<(j//2)))) if j%2==0 else 0 for j in range(8)]) for i in range(16)]
            raw=dict(orientation='orthogonal',width=1,height=1,tilewidth=4,tileheight=4,
                     tilesets=[dict(firstgid=1,name='a',tilewidth=4,tileheight=4,image='atlas.png',imagewidth=64,imageheight=4,columns=16,tilecount=16,wangsets=[wang])],
                     layers=[dict(name='ground',type='tilelayer',width=1,height=1,data=[1])])
            path=root/'map.tmj';path.write_text(json.dumps(raw),encoding='utf-8')
            world=TileMap.from_tiled(path)
            self.assertIn('Water',world.tile_set.autotiles)
            world.layers['ground'].set_terrain((1,0),'Water')
            self.assertEqual(world.layers['ground'].get_cell((0,0)).tile_id,2)
            xml='<map orientation="orthogonal" width="1" height="1" tilewidth="4" tileheight="4"><tileset firstgid="1" name="a" tilewidth="4" tileheight="4" columns="16" tilecount="16"><image source="atlas.png" width="64" height="4"/><wangsets><wangset name="Water" type="edge"><wangcolor name="blue"/><wangtile tileid="0" wangid="0,0,0,0,0,0,0,0"/><wangtile tileid="2" wangid="0,0,1,0,0,0,0,0"/></wangset></wangsets></tileset><layer name="a" width="1" height="1"><data encoding="csv">1</data></layer></map>'
            path=root/'map.tmx';path.write_text(xml,encoding='utf-8')
            self.assertIn('Water',TileMap.from_tiled(path).tile_set.autotiles)


class TileCollisionTests(unittest.TestCase):
    def setUp(self):
        self.game=Game();self.game.physics.gravity=(0,900)
        texture=Texture.from_image(Image.create(32,16,Color.WHITE))
        self.ts=TileSet(texture,tile_size=(16,16))
        self.ts._tiles[0]={'properties':{'solid':True}}
    def tearDown(self):self.game.close()
    def test_merged_tiles_landing_edit_disable_and_transform_sync(self):
        world=TileMap(tile_set=self.ts,collisions=True);layer=world.add_layer('Ground')
        layer.collision_enabled=True;layer.fill((0,5,10,1),0)
        self.game.add(world)
        p=self.game.add(CharacterBody(position=(40,0),size=(10,20),motion_mode='grounded'))
        for _ in range(60):p.move_and_slide();self.game.update(1/60)
        self.assertEqual(len(world.colliders),1);self.assertTrue(p.is_on_floor())
        self.assertAlmostEqual(p.position.y,70,delta=.3)
        layer.erase_cell((2,5));self.game.update(1/60)
        self.assertEqual(len(world.colliders),2)
        world.position=(0,40);self.game.update(1/60)
        self.assertIsNone(self.game.physics.raycast((8,70),(8,95)))
        layer.collision_enabled=False;self.game.update(1/60)
        self.assertEqual(world.colliders,())
    def test_authored_polygon_flips_and_object_shapes(self):
        self.ts._tiles[1]={'objectgroup':{'objects':[dict(x=0,y=0,polygon=[dict(x=0,y=16),dict(x=16,y=0),dict(x=16,y=16)])]}}
        world=TileMap(tile_set=self.ts);layer=world.add_layer('Slope');layer.set_cell((0,0),1,flip_h=True)
        world.enable_collisions();self.game.add(world);self.game.update(1/60)
        hit=self.game.physics.raycast((4,-10),(4,20))
        self.assertIsNotNone(hit);self.assertAlmostEqual(hit.point.y,4,delta=.2)
        self.assertGreater(hit.normal.x,0)
        self.game.remove(world);self.game.flush_deferred()
        self.assertEqual(world.colliders,())
    def test_tile_object_uses_scaled_authored_geometry(self):
        self.ts._tiles[1]={'objectgroup':{'objects':[dict(x=0,y=0,polygon=[dict(x=0,y=16),dict(x=16,y=0),dict(x=16,y=16)])]}}
        world=TileMap(tile_set=self.ts);layer=world.add_layer('Objects');layer.kind='objectgroup'
        layer.objects=(MapObject(position=(32,48),size=(32,32),tile=TileCell(1)),)
        world.enable_collisions(layers=['Objects']);self.game.add(world);self.game.update(1/60)
        hit=self.game.physics.raycast((40,0),(40,60))
        self.assertIsNotNone(hit);self.assertAlmostEqual(hit.point.y,40,delta=.1)

    def test_tiled_concave_polygon_polyline_ellipse_and_layer_properties(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            raw=dict(orientation='orthogonal',width=20,height=20,tilewidth=16,tileheight=16,tilesets=[],layers=[
                dict(name='Collision',type='objectgroup',properties=[dict(name='collision_enabled',type='bool',value=True),dict(name='collision_layer',type='int',value=2)],objects=[
                    dict(id=1,x=0,y=0,polygon=[dict(x=0,y=0),dict(x=40,y=0),dict(x=40,y=10),dict(x=10,y=10),dict(x=10,y=40),dict(x=0,y=40)]),
                    dict(id=2,x=100,y=20,polyline=[dict(x=0,y=0),dict(x=30,y=0)]),
                    dict(id=3,x=150,y=20,width=20,height=10,ellipse=True)])])
            path=root/'map.tmj';path.write_text(json.dumps(raw),encoding='utf-8')
            world=self.game.add(TileMap.from_tiled(path));self.game.flush_deferred()
            self.assertGreaterEqual(len(world.colliders),6)
            self.assertTrue(all(body.collision_layer==2 for body in world.colliders))
            self.assertIsNone(self.game.physics.raycast((25,15),(25,35)))
            self.assertIsNotNone(self.game.physics.raycast((105,0),(105,40)))
            self.assertIsNotNone(self.game.physics.raycast((160,0),(160,40)))
    def test_autotile_collision_updates_with_variant(self):
        self.ts.add_autotile('solid',{0:0,2:1,8:1})
        self.ts._tiles[1]={'properties':{'solid':True}}
        world=TileMap(tile_set=self.ts);layer=world.add_layer('ground');world.enable_collisions()
        layer.set_terrain((0,0),'solid');self.game.add(world);self.game.update(1/60)
        self.assertEqual(len(world.colliders),1)
        layer.set_terrain((1,0),'solid');self.game.update(1/60)
        hit=self.game.physics.raycast((24,-10),(24,20));self.assertIsNotNone(hit)
        layer.erase_cell((1,0));self.game.update(1/60)
        self.assertIsNone(self.game.physics.raycast((24,-10),(24,20)))


class MotionTests(unittest.TestCase):
    def test_idle_run_jump_fall_flip_speed_and_no_frame_reset(self):
        game=Game();game.physics.gravity=(0,900)
        p=game.add(CharacterBody(size=(10,20),motion_mode='grounded'))
        game.add(StaticBody(position=(0,80),size=(400,20)))
        sprite=AnimatedSprite(Texture.from_image(Image.create(32,8,Color.WHITE)),frame_size=(8,8))
        for name in ('idle','run','jump','fall'):sprite.add_animation(name,[0,1,2,3],fps=10)
        p.sprite=sprite;sprite.follow_motion(p,run_speed=100)
        states=[];sprite.motion.changed.connect(states.append)
        for _ in range(60):p.move_and_slide();game.update(1/60)
        self.assertEqual(sprite.motion.state,'idle')
        for _ in range(8):p.velocity=(-100,p.velocity.y);p.move_and_slide();game.update(1/60)
        self.assertEqual(sprite.animation,'run');self.assertTrue(sprite.flip_h);self.assertGreater(sprite.frame,0)
        p.jump(300)
        for _ in range(60):p.move_and_slide();game.update(1/60)
        self.assertIn('jump',states);self.assertIn('fall',states)
        self.assertEqual(sprite.motion.state,'run')
        sprite.follow_motion(None);self.assertIsNone(sprite.motion)
        game.close()


class PlatformExampleTests(unittest.TestCase):
    def test_playable_route_and_live_terrain_collisions(self):
        from examples.platform_demo import make_demo
        game,demo=make_demo();demo.jump_sound.volume=0
        try:
            for _ in range(90):game.update(1/60)
            game.input.action_press('move_right')
            first=second=False
            for _ in range(650):
                x=demo.player.position.x
                if demo.player.is_on_floor() and ((not first and x>=470) or (not second and x>=1144) or 1240<x<1480):
                    game.input.action_press('jump')
                    if x<800:first=True
                    else:second=True
                game.update(1/60);game.input.action_release('jump')
                if demo.won:break
            self.assertTrue(demo.won)
            game.input.action_release('move_right')
            self.assertIsNone(game.physics.raycast((1968,500),(1968,610)))
            demo.world.layers['Ground'].set_terrain((61,18),'Ground')
            game.update(1/60)
            self.assertIsNotNone(game.physics.raycast((1968,500),(1968,610)))
            demo.world.layers['Ground'].erase_cell((61,18))
            demo.world.layers['Water'].set_terrain((61,18),'Water')
            game.update(1/60)
            self.assertIsNone(game.physics.raycast((1968,500),(1968,610)))
        finally:game.close()

    def test_mouse_paints_ground_and_animated_water(self):
        from examples.platform_demo import make_demo
        game,demo=make_demo();demo.jump_sound.volume=0
        target=RenderTexture(*game.size)
        game._window=target
        try:
            game.update(1/60)
            point=Vector2(600,300)
            cell=demo.world.world_to_map(target.map_pixel_to_coords(point,game.make_view(game.world)))
            def event(kind,button):return SimpleNamespace(type=kind,position=point,button=button,delta=0)
            game.handle_event(event(Event.MOUSE_BUTTON_PRESSED,0))
            game.handle_event(event(Event.MOUSE_BUTTON_RELEASED,0))
            self.assertIsNotNone(demo.world.layers['Ground'].get_cell(cell))
            game.handle_event(event(Event.MOUSE_BUTTON_PRESSED,1))
            game.handle_event(event(Event.MOUSE_BUTTON_RELEASED,1))
            self.assertIsNone(demo.world.layers['Ground'].get_cell(cell))
            self.assertIsNotNone(demo.world.layers['Water'].get_cell(cell))
            self.assertFalse(game.input.is_action_pressed('paint_water'))
        finally:
            game._window=None
            game.close()


if __name__=='__main__':unittest.main()
