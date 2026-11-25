"""Generate the CFFI wrapper on the host and compile it for Android."""
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import os

sources, prefix, ndk = map(Path, sys.argv[1:4])
triple, output = sys.argv[4], Path(sys.argv[5])
output.mkdir(parents=True, exist_ok=True)
clang = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin" / f"{triple}24-clang"
flags = [
    str(clang), "-O2", "-DNDEBUG", "-shared", "-fPIC",
    "-Wl,-z,max-page-size=16384", f"-I{prefix}/include/python3.13",
]
python_lib = str(prefix / "lib/libpython3.13.so")
cffi = sources / "cffi-2.0.0"
pymunk = sources / "pymunk-7.3.1"

# CPython's Android build already supplies libffi built for this same ABI.
subprocess.run([
    *flags, "-DUSE__THREAD", "-DHAVE_SYNC_SYNCHRONIZE", f"-I{prefix}/include",
    str(cffi / "src/c/_cffi_backend.c"), str(prefix / "lib/libffi.a"), python_lib,
    "-o", str(output / "_cffi_backend.so"),
], check=True)

os.chdir(pymunk)
builder = runpy.run_path("pymunk/pymunk_extension_build.py")["ffibuilder"]
generated = output / "_chipmunk.c"
builder.emit_c_code(str(generated))
shutil.copytree(pymunk / "pymunk", output / "pymunk", dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("tests", "examples", "__pycache__"))
subprocess.run([
    *flags, "-std=c99", "-D_DEFAULT_SOURCE", "-DCP_OVERRIDE_MESSAGE",
    "-IMunk2D/include", str(generated),
    *map(str, sorted(Path("Munk2D/src").glob("*.c"))), "-lm", python_lib,
    "-o", str(output / "pymunk/_chipmunk.so"),
], check=True)
