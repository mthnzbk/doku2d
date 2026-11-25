# Third-party components

This template embeds CPython, SFML, PySFML and Doku2D's physics dependencies.

| Component | Version/source | Notices |
|---|---|---|
| CPython | 3.13.9, python.org | Python Software Foundation License and included notices |
| SFML | 3.0.2, SFML/SFML | zlib license |
| PySFML | 3.0.2.0, intjelic/python-sfml | zlib license |
| Pymunk and Munk2D | 7.3.1 and bundled source | MIT licenses |
| CFFI | 2.0.0 | MIT license |
| FreeType | SFML-pinned source | FreeType license, see included FTL.TXT |
| FLAC, Ogg, Vorbis | SFML-pinned sources | Upstream COPYING notices |
| miniaudio, minimp3, stb, glad | SFML bundled headers | Notices retained from their source headers |
| OpenSSL, SQLite, libffi, bzip2, xz | CPython Android source-dependency releases | See CPython's Android build sources and upstream component licences |
| Android NDK libc++ | r28c | LLVM third-party notices |

Original source archive URLs and SHA-256 hashes are in `sources.lock.json`.
CPython's `Android/android.py` also lists the exact native dependency releases.
The only CPython source adjustment made by this template is selecting NDK r28c
instead of r27d in `Android/android-env.sh`.
The Android SFML build is adapted by `scripts/prepare_sfml.py` to open
absolute paths in private storage and supply the missing EGL pbuffer
constructor used by the offscreen rendering fallback.

The build stages available source notices into the application's `assets/notices`.
Keep those notices when redistributing or extending this demo.
