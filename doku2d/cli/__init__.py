"""Create, run and package real Doku2D projects."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from ..config import ProjectConfig
from ..gui.theme import Theme

ENGINE=Path(__file__).resolve().parents[1]
TEMPLATE=Path(__file__).parent/'template'


def create_project(destination):
    root=Path(destination).resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):raise FileExistsError(f'Project directory must be empty: {root}')
    name=root.name;app_id=re.sub(r'[^A-Za-z0-9]+','-',name).strip('-').lower() or 'my-game'
    root.mkdir(parents=True,exist_ok=True)
    for source in TEMPLATE.rglob('*'):
        if not source.is_file() or source.suffix=='.pyc' or '__pycache__' in source.parts:continue
        relative=source.relative_to(TEMPLATE)
        if relative.name in ('build.py','project_settings.toml'):continue
        target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if source.suffix in ('.py','.toml','.md','.txt') or source.name=='.gitignore':
            text=source.read_text(encoding='utf-8').replace('__PROJECT_TITLE__',json.dumps(name,ensure_ascii=False)).replace('__APP_ID__',app_id)
            target.write_text(text,encoding='utf-8')
        else:shutil.copyfile(source,target)
    (root/'assets').mkdir(exist_ok=True)
    (root/'assets'/'.gitkeep').touch()
    return root


def run_project(project='.',*,arguments=()):
    config=ProjectConfig.load(project)
    if not config.entry.is_file():raise FileNotFoundError(f'Game entry does not exist: {config.entry}')
    env=os.environ.copy();env['PYTHONPATH']=str(config.root)+os.pathsep+str(ENGINE.parent)+os.pathsep+env.get('PYTHONPATH','')
    return subprocess.run([sys.executable,'-B',str(config.entry),*arguments],cwd=config.root,env=env).returncode


def _build_environment(config):
    env = os.environ.copy()
    env.setdefault('NUITKA_UPDATE_CHECK', 'never')
    paths = [str(config.root), str(config.entry.parent), str(ENGINE.parent)]
    if env.get('PYTHONPATH'):
        paths.append(env['PYTHONPATH'])
    env['PYTHONPATH'] = os.pathsep.join(paths)
    return env


def _executable_name(config):
    return config.app_id + ('.exe' if os.name == 'nt' else '.bin')


def standalone_command(config, *, output_dir=None):
    command = [sys.executable, '-m', 'nuitka', '--standalone',
               '--include-package=doku2d', '--include-package-data=doku2d', '--include-package-data=sfml',
               f'--output-dir={output_dir or config.output}',
               f'--output-filename={_executable_name(config)}',
               f'--include-data-files={config.file}={config.file.name}']
    if config.assets.is_dir():
        relative = config.assets.relative_to(config.root).as_posix()
        command.append(f'--include-data-dir={config.assets}={relative}')
    if config.theme is not None:
        theme = Theme.load(config.theme)
        data_files = [config.theme]
        if isinstance(theme.font, Path):
            data_files.append(theme.font.resolve())
        for path in data_files:
            if not path.is_relative_to(config.root):
                raise ValueError(f'Standalone theme data must be inside the project: {path}')
            if not path.is_relative_to(config.assets):
                relative = path.relative_to(config.root).as_posix()
                command.append(f'--include-data-files={path}={relative}')
    if os.environ.get('DOKU2D_BUILD_DOWNLOAD_TOOLS') == '1':
        command.append('--assume-yes-for-downloads')
    command.append(str(config.entry))
    return command


def build_project(project='.'):
    """Compile a project with Nuitka and publish its standalone application."""
    config = ProjectConfig.load(project)
    if not config.entry.is_file():
        raise FileNotFoundError(f'Missing game entry: {config.entry}')
    output = config.output / f'{config.app_id}.dist'
    binary = output / _executable_name(config)

    def check_destination():
        if output.exists() and (output.is_symlink() or not binary.is_file()):
            raise FileExistsError(f'Output directory is not a previous application build: {output}')

    check_destination()
    if importlib.util.find_spec('nuitka') is None:
        raise RuntimeError('Build needs Nuitka and a C compiler. Install doku2d[build] first.')
    config.output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=config.output, prefix='.nuitka-') as work:
        stage = Path(work)
        command = standalone_command(config, output_dir=stage)
        subprocess.run(command, cwd=config.root, env=_build_environment(config), check=True)
        packages = [folder for folder in stage.glob('*.dist') if (folder / binary.name).is_file()]
        if len(packages) != 1:
            raise RuntimeError(f'Nuitka did not produce the expected executable {binary.name}')
        previous = stage / 'previous'
        check_destination()
        if output.exists():
            output.rename(previous)
        try:
            packages[0].rename(output)
        except OSError:
            if previous.exists():
                previous.rename(output)
            raise
    return binary


def main(argv=None):
    parser=argparse.ArgumentParser(description='Doku2D project tools')
    commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('create',help='Create a playable starter project');create.add_argument('directory')
    run=commands.add_parser('run',help='Run a project');run.add_argument('--project',default='.');run.add_argument('--frames',type=int)
    build = commands.add_parser('build', help='Compile a standalone application with Nuitka')
    build.add_argument('--project', default='.')
    args=parser.parse_args(argv)
    try:
        if args.command=='create':print(create_project(args.directory));return 0
        if args.command=='run':return run_project(args.project,arguments=['--frames',str(args.frames)] if args.frames is not None else [])
        print(build_project(args.project))
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as error:
        parser.exit(1,f'doku2d: {error}\n')


if __name__=='__main__':raise SystemExit(main())
