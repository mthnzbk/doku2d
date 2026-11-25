"""Generate C++ and exported C-API headers on the host, then cross-compile."""
from pathlib import Path
import sys
from Cython.Build import cythonize
from setuptools import Extension

source = Path(sys.argv[1]).resolve()
extensions = [Extension(
    f"sfml.{name}", [str(source / "src/sfml" / name / f"{name}.pyx")],
    language="c++",
) for name in ("system", "window", "graphics", "audio", "network")]
cythonize(extensions, include_path=[str(source / "include/Includes")],
          compiler_directives={"language_level": "3", "embedsignature": True})
