"""Only the canvas/daylight/API/resource/storage/project work added in this change."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest
from sfml.graphics import Color,Image,Texture,RectangleShape,RenderTexture
import doku2d
from doku2d import (Game,Entity,CanvasGroup,AmbientLight,CanvasModulate,DayNightCycle,
                    Resources,Sprite,AnimatedSprite,SaveStore,SaveError,Settings,
                    StaticBody,RayCast,Theme)
from doku2d.cli import create_project,run_project,standalone_command
from doku2d.config import ProjectConfig

WORKSPACE=Path(__file__).resolve().parents[1]


class Square(Entity):
    def __init__(self,position=(0,0),size=(6,6)):
        super().__init__();self.position=position;self.size=size
    def render(self,target,states):
        shape=RectangleShape(self.size);shape.fill_color=Color.WHITE;target.draw(shape,states)


def snapshot(game):
    game.flush_deferred()
    target=RenderTexture(*game.size);target.clear(Color.BLACK);game.render(target);target.display()
    return target.texture.to_image()


class ProjectWorkTests(unittest.TestCase):
    def test_group_alpha_is_applied_once_and_transform_moves_members(self):
        game=Game(size=(20,10))
        try:
            group=game.add(CanvasGroup(opacity=.5));group.position=(2,0)
            first=group.add(Square());group.add(Square(position=(3,0)))
            image=snapshot(game)
            self.assertAlmostEqual(image[3,2].r,128,delta=1)
            self.assertAlmostEqual(image[6,2].r,128,delta=1)
            self.assertEqual(image[0,2].r,0)
            group.visible=False
            self.assertFalse(first.visible)
            self.assertEqual(snapshot(game)[3,2].r,0)
        finally:game.close()

    def test_group_lifecycle_and_nonvisual_guards(self):
        game=Game()
        try:
            group=game.add(CanvasGroup());member=group.add(Square())
            with self.assertRaises(TypeError):group.add(StaticBody())
            game.remove(member);self.assertNotIn(member,group.members)
            member=group.add(Square());game.remove(group);game.flush_deferred()
            self.assertIsNone(member.game)
            self.assertIsNone(group.game)
        finally:game.close()

    def test_groups_support_queued_members_and_cancel_together(self):
        game=Game()
        class Maker(Entity):
            def on_ready(self):
                self.group=game.add(CanvasGroup())
                self.member=game.add(Square())
                self.group.add(self.member)
                self.cancelled=game.add(CanvasGroup())
                self.cancelled_member=game.add(Square())
                self.cancelled.add(self.cancelled_member)
                game.remove(self.cancelled)
        try:
            maker=game.add(Maker());game.flush_deferred()
            self.assertIs(maker.member.game,game)
            self.assertIn(maker.member,maker.group.members)
            self.assertIsNone(maker.cancelled_member.game)
            self.assertIsNone(maker.cancelled_member._pending_game)
        finally:game.close()

    def test_cycle_midnight_pause_and_compatibility_name(self):
        self.assertIs(CanvasModulate,AmbientLight)
        cycle=DayNightCycle(day_length=1,time=12)
        self.assertEqual(cycle.color,Color.WHITE)
        cycle.time=0;self.assertLess(cycle.color.r,60)
        cycle.time=23;days=[];cycle.day_changed.connect(days.append)
        cycle._advance(.25)
        self.assertEqual((cycle.day,cycle.time),(1,5))
        self.assertEqual(days,[1]);cycle.pause();cycle._advance(.25);self.assertEqual(cycle.time,5)
        with self.assertRaises(ValueError):cycle.colors=[(0,Color.BLACK),(24,Color.WHITE)]
        with self.assertRaises(ValueError):DayNightCycle(colors=[])

    def test_ambient_changes_world_and_leaves_hud_canvas_alone(self):
        game=Game(size=(32,10))
        try:
            game.add(Square(size=(16,10)))
            game.add(Square(position=(16,0),size=(16,10)),canvas=game.ui.canvas)
            cycle=game.add(DayNightCycle(time=0,playing=False))
            image=snapshot(game)
            self.assertLess(image[4,4].r,60);self.assertEqual(image[24,4].r,255)
            cycle.time=12;image=snapshot(game);self.assertEqual(image[4,4].r,255)
            cycle.enabled=False;image=snapshot(game);self.assertEqual(image[4,4].r,255)
        finally:game.close()

    def test_assets_share_cache_and_relative_paths_bind_to_game(self):
        with TemporaryDirectory(dir=WORKSPACE,prefix='.project-assets-') as directory:
            root=Path(directory);assets=root/'assets';assets.mkdir()
            Image.create(8,4,Color.RED).to_file(str(assets/'sheet.png'))
            game=Game(project_root=root,asset_root='assets',save_dir='.saves')
            try:
                a=Sprite('res://sheet.png');b=Sprite('sheet.png');game.add(a);game.add(b)
                self.assertIs(a.texture,b.texture)
                anim=game.add(AnimatedSprite('sheet.png',frame_size=(4,4)));anim.add_animation('walk',[0,1])
                self.assertIs(anim.texture,a.texture)
                font=game.ui.theme.get_font()
                packaged_font = Path(doku2d.__file__).parent / 'assets/fonts/NotoSans.ttf'
                self.assertIs(font, game.resources.get_font(packaged_font))
                self.assertEqual(Theme(None,20).font_size,20)
                self.assertEqual(game.resources.cache_info['textures'],1)
                game.resources.unload('sheet.png');self.assertIsNot(game.resources.get_texture('sheet.png'),a.texture)
            finally:game.close()

    def test_map_cache_returns_independent_maps_with_shared_atlas(self):
        with TemporaryDirectory(dir=WORKSPACE,prefix='.project-map-') as directory:
            root=Path(directory);Image.create(8,4,Color.RED).to_file(str(root/'tiles.png'))
            data=dict(orientation='orthogonal',width=2,height=1,tilewidth=4,tileheight=4,
                      tilesets=[dict(firstgid=1,name='a',tilewidth=4,tileheight=4,image='tiles.png',imagewidth=8,imageheight=4,columns=2,tilecount=2)],
                      layers=[dict(name='Ground',type='tilelayer',width=2,height=1,data=[1,2])])
            (root/'map.tmj').write_text(json.dumps(data),encoding='utf-8')
            resources=Resources(root)
            a=resources.load_map('map.tmj');b=resources.load_map('map.tmj')
            self.assertIs(a.tile_set.texture,b.tile_set.texture)
            a.erase_cell('Ground',(0,0));self.assertIsNotNone(b.get_cell('Ground',(0,0)))
            self.assertEqual(resources.cache_info['maps'],1)
            copy=resources.get_map('map.tmj');copy.layers[0].cells.clear()
            self.assertTrue(resources.get_map('map.tmj').layers[0].cells)

    def test_atomic_save_validation_and_nested_settings_flush(self):
        with TemporaryDirectory(dir=WORKSPACE,prefix='.project-save-') as directory:
            store=SaveStore(directory)
            value={'name':'ışık','position':[1,2]};store.save('slot1',value)
            self.assertEqual(store.load('slot1'),value)
            with self.assertRaises(SaveError):store.save('slot1',{'bad':float('nan')})
            self.assertEqual(store.load('slot1'),value)
            with self.assertRaises(ValueError):store.save('../outside',{})
            (Path(directory)/'broken.json').write_text('{bad}',encoding='utf-8')
            with self.assertRaises(SaveError):store.load('broken')
            settings=Settings(store);settings['audio']={'volume':40};settings.flush()
            settings['audio']['volume']=70;settings.flush()
            self.assertEqual(Settings(store)['audio']['volume'],70)
            self.assertFalse(list(Path(directory).glob('*.tmp')))

    def test_supported_api_has_no_public_placeholders_and_ray_queries_work(self):
        for name in ('Shader','Parallax','Line','Path2D','PathFollow','CollisionShape2D','CollisionPolygon2D','RayCast2D'):
            self.assertNotIn(name,doku2d.__all__);self.assertFalse(hasattr(doku2d,name))
        self.assertNotIn('animationplayer',doku2d.__all__)
        game=Game()
        try:
            wall=game.add(StaticBody(position=(50,0),size=(10,30)))
            with self.assertRaises(TypeError):wall.collision_object='invalid'
            ray=game.add(RayCast(target_position=(100,0)))
            self.assertIs(ray.force_update().collider,wall)
            ray.exclude=(wall,);self.assertIsNone(ray.force_update())
        finally:game.close()

    def test_create_and_run_starter(self):
        with TemporaryDirectory(dir=WORKSPACE, prefix='.project-flow-') as directory:
            project = create_project(Path(directory) / 'starter')
            with (project / 'doku2d.toml').open('a', encoding='utf-8') as stream:
                stream.write('\n[storage]\ndirectory=".user-data"\n')
            self.assertEqual(run_project(project, arguments=['--frames', '2']), 0)
            self.assertTrue((project / '.user-data/settings.json').exists())

    def test_project_configuration_validation_and_native_build_plan(self):
        with TemporaryDirectory(dir=WORKSPACE,prefix='.project-config-') as directory:
            project=create_project(Path(directory)/'starter')
            config=ProjectConfig.load(project)
            self.assertEqual(config.assets,project/'assets')
            self.assertEqual(config.game_options['project_root'],project)
            command=standalone_command(config)
            self.assertIn('--standalone',command);self.assertIn('--include-package-data=doku2d',command)
            with self.assertRaises(FileExistsError):create_project(project)
            path=project/'doku2d.toml';path.write_text(path.read_text(encoding='utf-8').replace('entry = "main.py"','entry = "../outside.py"'),encoding='utf-8')
            with self.assertRaises(ValueError):ProjectConfig.load(project)


if __name__=='__main__':unittest.main()
