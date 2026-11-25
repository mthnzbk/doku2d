from pathlib import Path
import argparse
import shutil

p = argparse.ArgumentParser()
p.add_argument("--sources", type=Path, required=True)
p.add_argument("--sfml-build", type=Path, required=True)
p.add_argument("--ndk", type=Path, required=True)
p.add_argument("--project", type=Path, required=True)
a = p.parse_args()
destination = a.project / "app/src/main/assets/notices"
destination.mkdir(parents=True, exist_ok=True)
sources = {
    "CPython.txt": a.sources / "Python-3.13.9/LICENSE",
    "SFML.txt": a.sources / "SFML-3.0.2/license.md",
    "PySFML.txt": a.sources / "PySFML-3.0.2.0/LICENSE.txt",
    "Pymunk.txt": a.sources / "pymunk-7.3.1/LICENSE.txt",
    "Munk2D.txt": a.sources / "pymunk-7.3.1/Munk2D/LICENSE.txt",
    "CFFI.txt": a.sources / "cffi-2.0.0/LICENSE",
    "FreeType.txt": a.sfml_build / "_deps/freetype-src/docs/FTL.TXT",
    "FLAC-Xiph.txt": a.sfml_build / "_deps/flac-src/COPYING.Xiph",
    "FLAC-LGPL.txt": a.sfml_build / "_deps/flac-src/COPYING.LGPL",
    "Ogg.txt": a.sfml_build / "_deps/ogg-src/COPYING",
    "Vorbis.txt": a.sfml_build / "_deps/vorbis-src/COPYING",
    "libcxx.txt": a.ndk / "toolchains/llvm/prebuilt/linux-x86_64/NOTICE",
}
for name, source in sources.items():
    if source.is_file():
        shutil.copy2(source, destination / name)
headers = a.sources / "SFML-3.0.2/extlibs/headers"
for subdir in ("miniaudio", "minimp3", "stb_image", "glad"):
    # These are bundled header sources; retaining them retains their notices.
    folder = headers / subdir
    for source in folder.glob("*.h"):
        shutil.copy2(source, destination / f"{subdir}-{source.name}.txt")
template = Path(__file__).resolve().parents[1]
shutil.copy2(template / "THIRD_PARTY.md", destination / "THIRD_PARTY.md")
print("Third-party source notices staged")
