"""Small TOML project configuration, resolved independently of the working directory."""
from dataclasses import dataclass
from pathlib import Path
import re
import tomllib


@dataclass(frozen=True)
class ProjectConfig:
    file:Path
    title:str
    app_id:str
    entry:Path
    assets:Path
    output:Path
    width:int=960
    height:int=540
    fps_limit:int=60
    physics_fps:int=60
    save_dir:Path|None=None
    window_size:tuple[int,int]|None=None
    scale_mode:str="fit"
    theme:Path|None=None
    persist_preferences:bool=False
    @property
    def root(self):return self.file.parent
    @property
    def game_options(self):
        return dict(title=self.title,size=(self.width,self.height),fps_limit=self.fps_limit,
                    physics_fps=self.physics_fps,project_root=self.root,asset_root=self.assets,
                    save_dir=self.save_dir,app_id=self.app_id,window_size=self.window_size,
                    scale_mode=self.scale_mode,theme=self.theme,
                    persist_preferences=self.persist_preferences)
    @classmethod
    def load(cls,path='doku2d.toml'):
        path=Path(path).resolve()
        if path.is_dir():
            current=path/'doku2d.toml'
            path=current if current.exists() else path/'project_settings.toml'
        with path.open('rb') as stream:data=tomllib.load(stream)
        game=data.get('game',{});window=data.get('window',{});build=data.get('build',{})
        root=path.parent
        title=game.get('name',game.get('project_name',root.name))
        if not isinstance(title,str) or not title:raise ValueError('game.name must be nonempty')
        app_id=game.get('app_id',re.sub(r'[^A-Za-z0-9_.-]+','-',root.name).strip('.-') or 'doku2d-game')
        if not isinstance(app_id,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',app_id) or app_id in ('.','..'):
            raise ValueError('game.app_id must be a simple identifier')
        def local(value,label):
            result=(root/value).resolve()
            if result==root or not result.is_relative_to(root):raise ValueError(f'{label} must name a path inside the project')
            return result
        entry=local(game.get('entry','main.py'),'game.entry')
        if entry.suffix!='.py':raise ValueError('game.entry must be a Python file')
        assets=local(data.get('assets',{}).get('directory',game.get('assets_folder','assets')),'assets.directory')
        output=local(build.get('directory','dist'),'build.directory')
        if assets==output or output.is_relative_to(assets) or assets.is_relative_to(output):raise ValueError('Asset and build directories must be separate')
        def integer(value,label,minimum=1):
            if not isinstance(value,int) or isinstance(value,bool) or value<minimum:raise ValueError(f'{label} must be an integer >= {minimum}')
            return value
        storage=data.get('storage',{}).get('directory')
        theme=data.get('ui',{}).get('theme')
        persist_preferences=data.get('preferences',{}).get('persist',False)
        if not isinstance(persist_preferences,bool):
            raise ValueError('preferences.persist must be boolean')
        logical_width=integer(window.get('width',game.get('window_width',960)),'window.width')
        logical_height=integer(window.get('height',game.get('window_height',540)),'window.height')
        scale_mode=window.get('scale_mode','fit')
        if scale_mode not in ('fit','integer','stretch'):
            raise ValueError('window.scale_mode must be fit, integer or stretch')
        window_size=(integer(window.get('initial_width',logical_width),'window.initial_width'),
                     integer(window.get('initial_height',logical_height),'window.initial_height'))
        return cls(path,title,app_id,entry,assets,output,
                   logical_width,logical_height,
                   integer(window.get('fps_limit',game.get('fps',60)),'window.fps_limit',0),
                   integer(window.get('physics_fps',60),'window.physics_fps'),
                   local(storage,'storage.directory') if storage else None,window_size,scale_mode,
                   local(theme,'ui.theme') if theme else None,persist_preferences)
