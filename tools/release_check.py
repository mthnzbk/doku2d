"""Build and install the wheel in a clean virtual environment, then exercise it."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import mkdtemp
from venv import EnvBuilder


ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build'/'release-check')
    parser.add_argument('--native', action='store_true', help='Also build and launch the standalone starter')
    parser.add_argument('--download-tools', action='store_true', help='Allow Nuitka to download required compiler tools')
    parser.add_argument('--tests', action='store_true', help='Run the repository test suite against the installed wheel')
    parser.add_argument('--wheel', type=Path, help='Use an existing wheel instead of building one')
    args = parser.parse_args(argv)
    base = args.output.resolve()
    base.mkdir(parents=True, exist_ok=True)
    run_dir = Path(mkdtemp(prefix='check-', dir=base))
    print(f'Release check directory: {run_dir}', flush=True)

    env = os.environ.copy()
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(name, None)
    env.update(PYTHONNOUSERSITE='1', PIP_DISABLE_PIP_VERSION_CHECK='1')
    if args.download_tools:
        env['DOKU2D_BUILD_DOWNLOAD_TOOLS'] = '1'

    def run(command, cwd=run_dir, timeout=180):
        subprocess.run([str(item) for item in command], cwd=cwd, env=env, check=True, timeout=timeout)

    if args.wheel is None:
        source = run_dir/'source'
        source.mkdir()
        for filename in ('pyproject.toml', 'README.md', 'LICENSE'):
            shutil.copy2(ROOT/filename, source/filename)
        shutil.copytree(ROOT/'doku2d', source/'doku2d', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        wheel_dir = run_dir/'wheels'
        run([sys.executable, '-m', 'pip', 'wheel', source, '--no-deps', '--wheel-dir', wheel_dir], timeout=300)
        wheel, = wheel_dir.glob('doku2d-*.whl')
    else:
        wheel = args.wheel.resolve()

    venv = run_dir/'venv'
    EnvBuilder(with_pip=True).create(venv)
    scripts = venv / ('Scripts' if os.name == 'nt' else 'bin')
    python = scripts / ('python.exe' if os.name == 'nt' else 'python')
    cli = scripts / ('doku2d.exe' if os.name == 'nt' else 'doku2d')
    requirement = f'doku2d[build] @ {wheel.as_uri()}' if args.native else str(wheel)
    run([python, '-m', 'pip', 'install', '--only-binary=sfml,pymunk,cffi', requirement], timeout=300)
    run([python, '-m', 'pip', 'check'])
    run([python, '-I', '-c', '''
from importlib.metadata import version
from pathlib import Path
import sys
import doku2d
assert Path(doku2d.__file__).is_relative_to(Path(sys.prefix)), doku2d.__file__
assert doku2d.__version__ == version('doku2d')
print('Installed engine:', doku2d.__version__, doku2d.__file__)
'''])

    project = run_dir/'release-starter'
    run([cli, 'create', project])
    with (project/'doku2d.toml').open('a', encoding='utf-8') as config:
        config.write('\n[storage]\ndirectory = ".release-saves"\n')
    run([cli, 'run', '--project', project, '--frames', '3'])
    run([python, '-I', ROOT/'tools'/'check_starter.py', project])
    if args.tests:
        ignore = shutil.ignore_patterns('__pycache__', '*.pyc', 'dist', '.user-data')
        shutil.copytree(ROOT/'tests', run_dir/'tests', ignore=ignore)
        shutil.copytree(ROOT/'examples', run_dir/'examples', ignore=ignore)
        run([python, '-I', '-c', '''
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path.cwd()))
suite = unittest.defaultTestLoader.discover('tests')
raise SystemExit(not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful())
'''], timeout=300)
    if args.native:
        run([cli, 'build', '--project', project], timeout=1800)
        suffix = '.exe' if os.name == 'nt' else '.bin'
        binary = project/'dist'/'release-starter.dist'/f'release-starter{suffix}'
        run([binary, '--frames', '3'])
        print(f'Standalone app started from outside its project: {binary}', flush=True)
    print(f'Release checks passed: {wheel}', flush=True)


if __name__ == '__main__':
    main()
