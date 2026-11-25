"""Adapt SFML 3.0.2 file loading and offscreen drawing for Android."""
from pathlib import Path
import sys


def replace(path, original, adapted):
    source = path.read_text(encoding="utf-8")
    if adapted in source:
        return
    if original not in source:
        raise RuntimeError(f"Expected SFML 3.0.2 source in {path}")
    path.write_text(source.replace(original, adapted, 1), encoding="utf-8")


root = Path(sys.argv[1]) / "src/SFML"
# Relative names still work through AssetManager. Python's resource cache
# resolves private storage paths to absolute paths before passing them to SFML.
file_stream = root / "System/FileInputStream.cpp"
replace(file_stream, "    if (priv::getActivityStatesPtr() != nullptr)\n",
        "    m_androidFile.reset();\n"
        "    m_file.reset();\n"
        "    if (!filename.is_absolute() && priv::getActivityStatesPtr() != nullptr)\n")
for method, arguments in (("read", "data, size"), ("seek", "position"),
                          ("tell", ""), ("getSize", "")):
    replace(file_stream,
            "    if (priv::getActivityStatesPtr() != nullptr)\n"
            "    {\n"
            "        if (!m_androidFile)\n"
            "            return std::nullopt;\n"
            f"        return m_androidFile->{method}({arguments});\n"
            "    }\n",
            f"    if (m_androidFile)\n        return m_androidFile->{method}({arguments});\n")
replace(root / "Graphics/Image.cpp",
        "    if (priv::getActivityStatesPtr() != nullptr)\n",
        "    if (!filename.is_absolute() && priv::getActivityStatesPtr() != nullptr)\n")
replace(root / "Graphics/Font.cpp",
        '#ifndef SFML_SYSTEM_ANDROID\n'
        '    const auto stream = std::make_shared<FileInputStream>();\n'
        '    const auto type   = "file"sv;\n'
        '#else\n'
        '    const auto stream = std::make_shared<priv::ResourceStream>();\n'
        '    const auto type   = "Android resource stream"sv;\n'
        '#endif\n',
        '    // FileInputStream chooses the APK or private storage on Android.\n'
        '    const auto stream = std::make_shared<FileInputStream>();\n'
        '    const auto type   = "file"sv;\n')

# SFML's fallback RenderTexture needs a sized EGL pbuffer. The stock sized
# constructor is a stub, so frames disappear on drivers without OES FBOs.
egl = root / "Window/EglContext.cpp"
replace(egl,
        "EglContext::EglContext(EglContext* /*shared*/, const ContextSettings& /*settings*/, Vector2u /*size*/)\n"
        "{\n"
        "    EglContextImpl::ensureInit();\n\n"
        '    sf::err() << "Warning: context has not been initialized. The constructor EglContext(shared, settings, size) is "\n'
        '                 "currently not implemented."\n'
        "              << std::endl;\n"
        "}\n",
        "EglContext::EglContext(EglContext* shared, const ContextSettings& settings, Vector2u size)\n"
        "{\n"
        "    EglContextImpl::ensureInit();\n"
        "    m_display = EglContextImpl::getInitializedDisplay();\n"
        "    m_config = getBestConfig(m_display, 32, settings, EGL_PBUFFER_BIT);\n"
        "    updateSettings();\n"
        "    const std::array attributes = {EGL_WIDTH, static_cast<EGLint>(size.x),\n"
        "                                   EGL_HEIGHT, static_cast<EGLint>(size.y), EGL_NONE};\n"
        "    m_surface = eglCheck(eglCreatePbufferSurface(m_display, m_config, attributes.data()));\n"
        "    createContext(shared);\n"
        "}\n")
replace(root / "Window/EglContext.hpp",
        "getBestConfig(EGLDisplay display, unsigned int bitsPerPixel, const ContextSettings& settings);",
        "getBestConfig(EGLDisplay display, unsigned int bitsPerPixel, const ContextSettings& settings,\n"
        "                                   EGLint surfaceMask = EGL_WINDOW_BIT | EGL_PBUFFER_BIT);")
replace(egl, "EGLConfig EglContext::getBestConfig(EGLDisplay display, unsigned int bitsPerPixel, const ContextSettings& settings)",
        "EGLConfig EglContext::getBestConfig(EGLDisplay display, unsigned int bitsPerPixel,\n"
        "                                     const ContextSettings& settings, EGLint surfaceMask)")
replace(egl, "!(surfaceType & (EGL_WINDOW_BIT | EGL_PBUFFER_BIT))",
        "!(surfaceType & surfaceMask)")
replace(egl, "getBestConfig(m_display, VideoMode::getDesktopMode().bitsPerPixel, ContextSettings());",
        "getBestConfig(m_display, VideoMode::getDesktopMode().bitsPerPixel, ContextSettings(), EGL_PBUFFER_BIT);")
replace(egl, "getBestConfig(m_display, bitsPerPixel, settings);",
        "getBestConfig(m_display, bitsPerPixel, settings, EGL_WINDOW_BIT);")
