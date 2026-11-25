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
    for filename in ('icon.png', 'icon.ico'):
        shutil.copyfile(ENGINE/'assets'/filename, root/'assets'/filename)
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
    data_files = {}
    if config.window_icon is not None:
        data_files[config.window_icon] = 'window icon'
    if config.theme is not None:
        theme = Theme.load(config.theme)
        data_files[config.theme] = 'theme'
        if isinstance(theme.font, Path):
            data_files[theme.font.resolve()] = 'theme font'
    for path, kind in data_files.items():
        if not path.is_relative_to(config.root):
            raise ValueError(f'Standalone {kind} must be inside the project: {path}')
        if not path.is_relative_to(config.assets):
            relative = path.relative_to(config.root).as_posix()
            command.append(f'--include-data-files={path}={relative}')
    if os.name == 'nt':
        command.append(f'--windows-icon-from-ico={config.build_icon or ENGINE / "assets" / "icon.ico"}')
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


def build_atlas(directory, output=None, *, max_size=2048, padding=1):
    """Pack a PNG directory into an atlas JSON and its companion image."""
    from ..rendering.atlas import SpriteAtlas

    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    output = Path(output or directory / 'atlas.json').resolve().with_suffix('.json')
    image = output.with_suffix('.png')
    if output.exists() or image.exists():
        if not output.is_file():
            raise FileExistsError(f'Atlas image would overwrite an existing file: {image}')
        previous_data = json.loads(output.read_text(encoding='utf-8'))
        if (not isinstance(previous_data, dict) or previous_data.get('image') != image.name
                or not isinstance(previous_data.get('frames'), dict)):
            raise FileExistsError(f'Output is not a previous atlas: {output}')
    sources = {}
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.suffix.casefold() == '.png' and path.resolve() != image:
            name = path.relative_to(directory).with_suffix('').as_posix()
            if name in sources:
                raise ValueError(f'Duplicate atlas frame name: {name}')
            sources[name] = path
    pixels, frames = SpriteAtlas._pack_image(sources, max_size=max_size, padding=padding)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as directory:
        temporary = Path(directory)
        pixels.to_file(str(temporary / image.name))
        (temporary / output.name).write_text(json.dumps({'image': image.name, 'frames': frames},
                                                       ensure_ascii=False, indent=2), encoding='utf-8')
        previous_image = temporary / 'previous-image'
        if image.is_file():
            shutil.copyfile(image, previous_image)
        (temporary / image.name).replace(image)
        try:
            (temporary / output.name).replace(output)
        except OSError:
            if previous_image.exists():
                previous_image.replace(image)
            else:
                image.unlink()
            raise
    return output


def main(argv=None):
    parser=argparse.ArgumentParser(prog='doku2d', description='Doku2D project tools')
    commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('create',help='Create a playable starter project');create.add_argument('directory')
    run = commands.add_parser('run', help='Run a project on desktop or Android')
    run.add_argument('target', nargs='?', choices=('android',))
    run.add_argument('--project', default='.')
    run.add_argument('--frames', type=int)
    run.add_argument('--device', help='Android device serial')
    build = commands.add_parser('build', help='Build a desktop application or an Android APK')
    build.add_argument('target', nargs='?', choices=('android',))
    build.add_argument('--project', default='.')
    build.add_argument('--abi', choices=('arm64-v8a', 'x86_64'), help='Android processor architecture')
    atlas = commands.add_parser('atlas', help='Pack PNG files into a sprite atlas')
    atlas.add_argument('directory')
    atlas.add_argument('--output')
    atlas.add_argument('--max-size', type=int, default=2048)
    atlas.add_argument('--padding', type=int, default=1)
    args=parser.parse_args(argv)
    try:
        if args.command=='create':print(create_project(args.directory));return 0
        if args.command == 'run':
            if args.target == 'android':
                if args.frames is not None:
                    run.error('--frames is available on desktop')
                from ..android.run_android import run_android
                return run_android(args.project, device=args.device)
            if args.device is not None:
                run.error('--device requires the android target')
            return run_project(args.project, arguments=['--frames', str(args.frames)]
                               if args.frames is not None else [])
        if args.command == 'atlas':
            print(build_atlas(args.directory, args.output, max_size=args.max_size, padding=args.padding))
            return 0
        if args.target == 'android':
            from ..android.build_android import build_android
            print(build_android(args.project, args.abi or 'arm64-v8a'))
            return 0
        if args.abi:
            build.error('--abi requires the android target')
        print(build_project(args.project))
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as error:
        parser.exit(1,f'doku2d: {error}\n')


if __name__=='__main__':raise SystemExit(main())
