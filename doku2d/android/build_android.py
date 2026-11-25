#!/usr/bin/env python3
"""Build an Android debug APK with Python 3.11+ and the bundled template."""

import argparse
from importlib.metadata import PackageNotFoundError, distribution
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from xml.etree import ElementTree


ENGINE = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).with_name("template")
ABIS = ("arm64-v8a", "x86_64")
APPLICATION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")
EXCLUDED = {"venv", "__pycache__",
            ".user-data", "build", "dist", "node_modules"}


def _wsl_prefix():
    if not shutil.which("wsl.exe"):
        raise RuntimeError("Android builds on Windows require Ubuntu 24.04 in WSL2.")
    distro = os.environ.get("DOKU2D_ANDROID_WSL_DISTRO")
    if not distro:
        listing = subprocess.check_output(["wsl.exe", "--list", "--quiet"])
        encoding = "utf-16-le" if b"\0" in listing else "utf-8-sig"
        distros = {line.strip("\ufeff\r ") for line in listing.decode(encoding).splitlines()}
        distro = next((name for name in ("KoraAndroidBuild", "Ubuntu-24.04", "Ubuntu")
                       if name in distros), None)
    return ["wsl.exe", *(["--distribution", distro] if distro else []), "--exec"]


def _run_builder(staging, abi):
    # Windows projects stay on the Windows drive, with native compilation in WSL.
    script = TEMPLATE / "scripts" / "build.sh"
    if sys.platform == "win32":
        wsl = _wsl_prefix()
        paths = [subprocess.check_output([*wsl, "wslpath", "-a", str(path)], text=True).strip()
                 for path in (script, staging)]
        subprocess.run([*wsl, "bash", *paths, abi], check=True)
    elif sys.platform.startswith("linux") and platform.machine() in ("x86_64", "amd64"):
        subprocess.run(["bash", str(script), str(staging), abi], check=True)
    elif sys.platform == "darwin" or sys.platform.startswith("linux"):
        # The pinned NDK and Python cross-build scripts use Linux x86-64 binaries.
        # Docker supplies the same environment on Intel and Apple Silicon Macs.
        if not shutil.which("docker"):
            raise RuntimeError("Install and start Docker to build Android on this host.")
        image = "doku2d-android-builder:ubuntu24.04"
        subprocess.run(["docker", "build", "--platform", "linux/amd64", "-t", image,
                        str(TEMPLATE)], check=True)
        subprocess.run(["docker", "run", "--rm", "-it" if sys.stdin.isatty() else "-i",
                        "--platform", "linux/amd64",
                        "-v", f"{TEMPLATE}:/template:ro", "-v", f"{staging}:/work",
                        "-v", "doku2d-android-cache:/cache",
                        "-e", "DOKU2D_ANDROID_CACHE=/cache",
                        "-e", "GRADLE_USER_HOME=/cache/gradle-home",
                        image, "bash", "/template/scripts/build.sh", "/work", abi], check=True)
    else:
        raise RuntimeError(f"Android builds are unsupported on {sys.platform}.")


def _stage_project(root, staging, entry, build_directory, engine, package_assets):
    def ignore(directory, names):
        directory = Path(directory)
        return [name for name in names if name.startswith(".") or name in EXCLUDED
                or name.endswith((".pyc", ".apk", ".aab", ".whl"))
                or (directory / name).resolve() == build_directory
                or (directory / name).is_symlink()]

    # Stage only game code, configured assets and project data. Game-relative
    # paths remain identical after extraction on the phone.
    game = staging / "game"
    game.mkdir()
    for relative in package_assets:
        source = (root / relative).resolve()
        if source == root or not source.is_relative_to(root):
            raise ValueError(f"Android project paths must stay inside the project: {relative}")
        if not source.exists():
            continue
        target = game / source.relative_to(root)
        if source.is_dir():
            shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    # Support sibling modules/packages without copying whole desktop workspaces.
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [name for name in subdirs if name not in ignore(directory, subdirs)]
        if Path(directory) == root and "android" in subdirs:
            subdirs.remove("android")
        for name in files:
            if not name.endswith(".py") or name in ignore(directory, [name]):
                continue
            path = Path(directory) / name
            target = game / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    for name in ("LICENSE", "LICENSE.txt", "THIRD_PARTY.md"):
        if (root / name).is_file():
            shutil.copy2(root / name, game / name)
    shutil.copytree(engine, staging / "site-packages/doku2d",
                    ignore=shutil.ignore_patterns("android", "__pycache__", "*.pyc"))
    # A checkout and a wheel store Doku2D's license in different places.
    license_file = engine.parent / "LICENSE"
    if not license_file.is_file():
        try:
            installed = distribution("doku2d")
        except PackageNotFoundError:
            installed = None
        if installed:
            license_file = next((installed.locate_file(path) for path in installed.files or ()
                                 if path.as_posix().endswith(".dist-info/licenses/LICENSE")), license_file)
    if license_file.is_file():
        shutil.copy2(license_file, staging / "site-packages/doku2d/LICENSE")

    # The launcher runs the normal Python entry point and gives SaveStore a
    # private directory that survives runtime replacement when an APK updates.
    (game / "_doku2d_android_start.py").write_text(
        "import os, runpy, sys\n"
        "from pathlib import Path\n"
        "root = Path(__file__).resolve().parent\n"
        "os.chdir(root)\n"
        "os.environ['DOKU2D_ANDROID_SAVE_DIR'] = str(root.parent.parent / 'saves')\n"
        f"entry = root / {entry.as_posix()!r}\n"
        "sys.path.insert(0, str(entry.parent))\n"
        "sys.argv = [str(entry)]\n"
        "runpy.run_path(str(entry), run_name='__main__')\n", encoding="utf-8")


def _stage_android_overrides(root, staging):
    # Treat the generated files as project sources. Seed each one only if it
    # is missing, including when the project already has its own manifest.
    project_android = root / "android"
    defaults = TEMPLATE / "project"
    for relative in ("AndroidManifest.xml", "res/values/strings.xml"):
        destination = project_android / relative
        if destination.exists():
            continue
        content = (defaults / relative).read_bytes()
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            pass
        else:
            print(f"Created {destination}", flush=True)

    manifest = project_android / "AndroidManifest.xml"
    try:
        if ElementTree.parse(manifest).getroot().tag != "manifest":
            raise ValueError(f"{manifest} must have a <manifest> root element.")
    except ElementTree.ParseError as error:
        raise ValueError(f"Invalid XML in {manifest}: {error}") from error

    # Snapshot the project's files so Gradle can use them from WSL or Docker.
    overrides = staging / "android"
    shutil.copytree(project_android / "res", overrides / "res")
    shutil.copy2(manifest, overrides / manifest.name)


def build_android(project=".", abi="arm64-v8a"):
    if abi not in ABIS:
        raise ValueError(f"Unsupported Android ABI: {abi}")
    candidate = Path(project).resolve()
    config = candidate / "doku2d.toml" if candidate.is_dir() else candidate
    if candidate.is_dir() and not config.is_file():
        config = candidate / "project_settings.toml"
    root = config.parent
    with config.open("rb") as stream:
        settings = tomllib.load(stream)
    game = settings.get("game", {})
    android = settings.get("android", {})
    entry = (root / game.get("entry", "main.py")).resolve()
    if not entry.is_relative_to(root) or entry.suffix != ".py" or not entry.is_file():
        raise ValueError(f"Expected an entry file inside the project: {entry}")
    app_id = android.get("application_id", game.get("app_id", root.name))
    if not isinstance(app_id, str) or not app_id:
        raise ValueError("Android application ID must be a nonempty string.")
    if "application_id" not in android and not APPLICATION_ID.fullmatch(app_id):
        segment = re.sub(r"[^a-z0-9_]", "_", app_id.lower())
        app_id = f"org.doku2d.game_{segment}"
    if not APPLICATION_ID.fullmatch(app_id):
        raise ValueError(f"Invalid Android application ID: {app_id}")
    orientation = android.get("orientation", "landscape")
    if orientation not in {"landscape", "portrait", "sensor", "unspecified"}:
        raise ValueError(f"Invalid Android orientation: {orientation}")
    version_code = android.get("version_code", 1)
    if type(version_code) is not int or not 1 <= version_code <= 2_100_000_000:
        raise ValueError("Android version_code must be an integer from 1 to 2100000000.")
    build_directory = (root / settings.get("build", {}).get("directory", "dist")).resolve()
    if build_directory == root or not build_directory.is_relative_to(root):
        raise ValueError("Android build output must be a subdirectory of the project.")
    output = build_directory / "android"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="doku2d-", dir=output) as temporary:
        staging = Path(temporary)
        _stage_android_overrides(root, staging)
        # Localization catalog paths are relative to the packaged asset directory.
        assets = settings.get("assets", {}).get("directory", game.get("assets_folder", "assets"))
        resources = [config.name, entry.relative_to(root), assets, *android.get("include", [])]
        theme = settings.get("ui", {}).get("theme")
        if theme:
            resources.append(theme)
        _stage_project(root, staging, entry.relative_to(root), build_directory, ENGINE, resources)
        icon = (root / settings.get("window", {}).get("icon", "assets/icon.png")).resolve()
        if not icon.is_file() or icon.suffix.lower() != ".png":
            icon = ENGINE / "assets" / "icon.png"
        if not icon.is_relative_to(root) and icon != ENGINE / "assets" / "icon.png":
            raise ValueError(f"Android icon must stay inside the project: {icon}")
        shutil.copy2(icon, staging / "icon.png")
        (staging / "android.json").write_text(json.dumps({
            "appId": app_id, "appLabel": game.get("name", game.get("project_name", root.name)),
            "screenOrientation": orientation, "appVersionCode": version_code,
            "appVersionName": android.get("version_name", "0.1.0"),
        }), encoding="utf-8")
        _run_builder(staging, abi)
        # A failed build leaves any previous APK in place.
        apk = output / f"{app_id}-{abi}-debug.apk"
        (staging / "app-debug.apk").replace(apk)
    return apk


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project folder or doku2d.toml")
    parser.add_argument("--abi", choices=ABIS, default=ABIS[0])
    args = parser.parse_args(argv)
    try:
        print(build_android(args.project, args.abi))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Android build failed: {error}\n")


if __name__ == "__main__":
    main()
