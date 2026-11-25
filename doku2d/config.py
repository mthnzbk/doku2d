"""Small TOML project configuration, resolved independently of the working directory."""
from dataclasses import dataclass, field
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
    debug:bool=False
    debug_key:str|None="F3"
    persist_preferences:bool=False
    locale:str='en'
    fallback_locale:str='en'
    catalogs:dict=field(default_factory=dict)
    physics_interpolation:bool=False
    vsync:bool=False
    window_icon:Path|None=None
    build_icon:Path|None=None
    @property
    def root(self):return self.file.parent
    @property
    def game_options(self):
        return dict(title=self.title,size=(self.width,self.height),fps_limit=self.fps_limit,
                    physics_fps=self.physics_fps,project_root=self.root,asset_root=self.assets,
                    save_dir=self.save_dir,app_id=self.app_id,window_size=self.window_size,
                    scale_mode=self.scale_mode,theme=self.theme,debug=self.debug,debug_key=self.debug_key,
                    persist_preferences=self.persist_preferences,locale=self.locale,
                    fallback_locale=self.fallback_locale,catalogs=self.catalogs,
                    physics_interpolation=self.physics_interpolation,vsync=self.vsync,
                    window_icon=self.window_icon)
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
        debug=data.get('debug',{})
        debug_enabled=debug.get('enabled',False)
        debug_key=debug.get('key','F3')
        if not isinstance(debug_enabled,bool) or not (debug_key is False or isinstance(debug_key,str)):
            raise ValueError('debug.enabled must be boolean and debug.key must be a key name or false')
        persist_preferences=data.get('preferences',{}).get('persist',False)
        if not isinstance(persist_preferences,bool):
            raise ValueError('preferences.persist must be boolean')
        localization=data.get('localization',{})
        if not isinstance(localization,dict):
            raise ValueError('localization must be a table')
        locale=localization.get('locale','en')
        fallback_locale=localization.get('fallback','en')
        if any(not isinstance(value,str) or not value.strip() for value in (locale,fallback_locale)):
            raise ValueError('localization.locale and localization.fallback must be nonempty strings')
        catalogs={}
        configured_catalogs=localization.get('catalogs',{})
        if not isinstance(configured_catalogs,dict):
            raise ValueError('localization.catalogs must be a table')
        for language,name in configured_catalogs.items():
            if not language.strip() or not isinstance(name,str) or not name:
                raise ValueError('Each localization catalog needs a language and a file path')
            catalog=(assets/name.removeprefix('res://')).resolve()
            if not catalog.is_relative_to(assets) or catalog == assets:
                raise ValueError('Localization catalogs must be inside the asset directory')
            catalogs[language]=catalog
        logical_width=integer(window.get('width',game.get('window_width',960)),'window.width')
        logical_height=integer(window.get('height',game.get('window_height',540)),'window.height')
        scale_mode=window.get('scale_mode','fit')
        if scale_mode not in ('fit','integer','stretch'):
            raise ValueError('window.scale_mode must be fit, integer or stretch')
        window_size=(integer(window.get('initial_width',logical_width),'window.initial_width'),
                     integer(window.get('initial_height',logical_height),'window.initial_height'))
        physics_interpolation=window.get('physics_interpolation',False)
        if not isinstance(physics_interpolation,bool):
            raise ValueError('window.physics_interpolation must be boolean')
        vsync=window.get('vsync',False)
        if not isinstance(vsync,bool):
            raise ValueError('window.vsync must be boolean')
        def icon(section, label):
            value = section.get('icon')
            if value is None:
                return None
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{label} must be a nonempty path')
            return local(value, label)
        window_icon = icon(window, 'window.icon')
        build_icon = icon(build, 'build.icon')
        if build_icon is not None and build_icon.suffix.lower() != '.ico':
            raise ValueError('build.icon must be an ICO file')
        return cls(path,title,app_id,entry,assets,output,
                   logical_width,logical_height,
                   integer(window.get('fps_limit',game.get('fps',60)),'window.fps_limit',0),
                   integer(window.get('physics_fps',60),'window.physics_fps'),
                   local(storage,'storage.directory') if storage else None,window_size,scale_mode,
                   local(theme,'ui.theme') if theme else None,debug_enabled,
                   None if debug_key is False else debug_key,persist_preferences,locale,fallback_locale,catalogs,
                   physics_interpolation,vsync,window_icon,build_icon)
