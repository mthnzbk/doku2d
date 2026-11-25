"""Stage CPython, all five PySFML extensions and the Python game into the app."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

p = argparse.ArgumentParser()
p.add_argument("--prefix", type=Path, required=True)
p.add_argument("--native", type=Path, required=True)
p.add_argument("--pysfml", type=Path, required=True)
p.add_argument("--sfml-prefix", type=Path, required=True)
p.add_argument("--ndk", type=Path, required=True)
p.add_argument("--project", type=Path, required=True)
p.add_argument("--input", type=Path, required=True)
p.add_argument("--physics", type=Path, required=True)
p.add_argument("--abi", choices=["arm64-v8a", "x86_64"], default="arm64-v8a")
a = p.parse_args()
assets = a.project / "app/src/main/assets"
jni = a.project / "app/src/main/jniLibs" / a.abi
assets.mkdir(parents=True, exist_ok=True)
jni.mkdir(parents=True, exist_ok=True)
for path in a.prefix.joinpath("lib").glob("*.so"):
    shutil.copy2(path, jni / path.name)
for path in a.native.rglob("libsfml-*.so"):
    shutil.copy2(path, jni / path.name)
for path in (a.sfml_prefix / "lib" / a.abi).glob("libsfml-*.so"):
    shutil.copy2(path, jni / path.name)
entry = next(a.native.rglob("libpysfml-app.so"))
shutil.copy2(entry, jni / entry.name)
triple = "aarch64-linux-android" if a.abi == "arm64-v8a" else "x86_64-linux-android"
cpp = a.ndk / "toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib" / triple / "libc++_shared.so"
shutil.copy2(cpp, jni / cpp.name)
runtime = assets / "runtime.zip"
with zipfile.ZipFile(runtime, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    lib = a.prefix / "lib/python3.13"
    for path in sorted(lib.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(lib)
        if any(part in {"__pycache__", "test", "tests", "site-packages", "idlelib", "tkinter", "ensurepip"} for part in relative.parts):
            continue
        if path.suffix in {".a", ".pyc"}:
            continue
        archive.write(path, "lib/python3.13/" + relative.as_posix())
    for path in (a.pysfml / "src/sfml").glob("*.py"):
        archive.write(path, "site-packages/sfml/" + path.name)
    modules = a.native / "python_modules/sfml"
    for name in ("system", "window", "graphics", "audio", "network"):
        archive.write(modules / f"{name}.so", f"site-packages/sfml/{name}.so")
    for tree in ("game", "site-packages"):
        root = a.input / tree
        for path in root.rglob("*"):
            if path.is_file():
                archive.write(path, f"{tree}/" + path.relative_to(root).as_posix())
    archive.write(a.physics / "_cffi_backend.so", "site-packages/_cffi_backend.so")
    for path in (a.physics / "pymunk").rglob("*"):
        if path.is_file():
            archive.write(path, "site-packages/" + path.relative_to(a.physics).as_posix())
digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
(assets / "runtime.sha256").write_text(digest + "\n")
print(f"Runtime: {runtime.stat().st_size:,} bytes; {digest}")
