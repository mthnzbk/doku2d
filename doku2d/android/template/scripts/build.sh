#!/usr/bin/env bash
# This worker runs on Linux. build_android.py selects the host and stages the game.
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
INPUT=$(realpath "$1")
ABI="$2"
DEFAULT_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/doku2d/android"
# Reuse the cache from the original SFML Android prototype when available.
if [[ -d /opt/koraandroid/tools && -w /opt/koraandroid ]]; then
    DEFAULT_CACHE=/opt/koraandroid
fi
BUILD_ROOT=${DOKU2D_ANDROID_CACHE:-"$DEFAULT_CACHE"}
DOWNLOADS="$BUILD_ROOT/downloads"
JOBS=${DOKU2D_ANDROID_JOBS:-4}
case "$ABI" in
    arm64-v8a) HOST=aarch64-linux-android; SUFFIX="" ;;
    x86_64) HOST=x86_64-linux-android; SUFFIX="-x86_64" ;;
    *) echo "Unsupported ABI: $ABI"; exit 1 ;;
esac
SFML_BUILD="$BUILD_ROOT/build-sfml$SUFFIX"
NATIVE_BUILD="$BUILD_ROOT/build-native-doku2d$SUFFIX"
mkdir -p "$BUILD_ROOT" "$DOWNLOADS" "$BUILD_ROOT/sources" "$BUILD_ROOT/tools"
# CPython and SFML share source trees between ABIs.
exec 9>"$BUILD_ROOT/.doku2d-build.lock"
flock 9
exec > >(tee "$BUILD_ROOT/build-doku2d-$ABI.log") 2>&1
trap 'echo "BUILD FAILED at line $LINENO. See the log above."' ERR

for command in python3 gcc g++ make cmake ninja unzip curl java; do
    command -v "$command" >/dev/null || { echo "Missing host tool: $command"; exit 1; }
done
SRC="$BUILD_ROOT/sources"
TOOLS="$BUILD_ROOT/tools"
PY="$SRC/Python-3.13.9"
SF="$SRC/SFML-3.0.2"
PSF="$SRC/PySFML-3.0.2.0"
needed=()
[[ -d "$PY" ]] || needed+=(python.tar.xz)
[[ -d "$SF" ]] || needed+=(sfml.zip)
[[ -d "$PSF" ]] || needed+=(pysfml.zip)
[[ -d "$SRC/pymunk-7.3.1" ]] || needed+=(pymunk-7.3.1.tar.gz)
[[ -d "$SRC/cffi-2.0.0" ]] || needed+=(cffi-2.0.0.tar.gz)
[[ -d "$TOOLS/android-ndk-r28c" ]] || needed+=(ndk-linux.zip)
[[ -d "$TOOLS/gradle-8.11.1" ]] || needed+=(gradle.zip)
[[ -d "$TOOLS/android-sdk/cmdline-tools/latest" ]] || needed+=(sdk-tools-linux.zip)
python3 "$PROJECT/scripts/fetch_sources.py" "$DOWNLOADS" "${needed[@]}"
[[ -d "$PY" ]] || tar -xJf "$DOWNLOADS/python.tar.xz" -C "$SRC"
[[ -d "$SF" ]] || unzip -q "$DOWNLOADS/sfml.zip" -d "$SRC"
[[ -d "$PSF" ]] || unzip -q "$DOWNLOADS/pysfml.zip" -d "$SRC"
[[ -d "$TOOLS/android-ndk-r28c" ]] || unzip -q "$DOWNLOADS/ndk-linux.zip" -d "$TOOLS"
[[ -d "$TOOLS/gradle-8.11.1" ]] || unzip -q "$DOWNLOADS/gradle.zip" -d "$TOOLS"
export ANDROID_HOME="$TOOLS/android-sdk"
export JAVA_HOME=${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
if [[ ! -d "$ANDROID_HOME/cmdline-tools/latest" ]]; then
    mkdir -p "$ANDROID_HOME/cmdline-tools"
    unzip -q "$DOWNLOADS/sdk-tools-linux.zip" -d "$ANDROID_HOME/cmdline-tools"
    mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
fi
NDK="$TOOLS/android-ndk-r28c"
mkdir -p "$ANDROID_HOME/ndk"
[[ -e "$ANDROID_HOME/ndk/28.2.13676358" ]] || ln -s "$NDK" "$ANDROID_HOME/ndk/28.2.13676358"
SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -f "$ANDROID_HOME/platforms/android-35/android.jar" ||
      ! -x "$ANDROID_HOME/build-tools/35.0.0/aapt" ]]; then
    # sdkmanager asks the developer to accept the SDK terms on first install.
    "$SDKMANAGER" --sdk_root="$ANDROID_HOME" "platforms;android-35" "build-tools;35.0.0" "platform-tools"
fi

echo "=== Building CPython from source ==="
export ANDROID_API_LEVEL=24
# Clearly marked local source adaptation: use the same r28c toolchain everywhere.
sed -i 's/ndk_version=27.3.13750724/ndk_version=28.2.13676358/' "$PY/Android/android-env.sh"
PREFIX="$PY/cross-build/$HOST/prefix"
if [[ ! -f "$PREFIX/lib/libpython3.13.so" ]]; then
    cd "$PY"
    if [[ ! -x cross-build/build/python ]]; then
        python3 Android/android.py configure-build
        python3 Android/android.py make-build
    fi
    python3 Android/android.py configure-host "$HOST"
    python3 Android/android.py make-host "$HOST"
fi

echo "=== Generating PySFML C++ ==="
[[ -x "$BUILD_ROOT/host-venv/bin/python" ]] || python3 -m venv "$BUILD_ROOT/host-venv"
"$BUILD_ROOT/host-venv/bin/pip" install -r "$PROJECT/scripts/requirements-host.txt"
"$BUILD_ROOT/host-venv/bin/python" "$PROJECT/scripts/generate_bindings.py" "$PSF"

echo "=== Building Pymunk and CFFI for Android $ABI ==="
[[ -d "$SRC/pymunk-7.3.1" ]] || tar -xzf "$DOWNLOADS/pymunk-7.3.1.tar.gz" -C "$SRC"
[[ -d "$SRC/cffi-2.0.0" ]] || tar -xzf "$DOWNLOADS/cffi-2.0.0.tar.gz" -C "$SRC"
PHYSICS="$BUILD_ROOT/build-physics$SUFFIX"
"$BUILD_ROOT/host-venv/bin/python" "$PROJECT/scripts/build_physics.py" \
    "$SRC" "$PREFIX" "$NDK" "$HOST" "$PHYSICS"

echo "=== Building SFML for Android $ABI ==="
python3 "$PROJECT/scripts/prepare_sfml.py" "$SF"
cmake -G Ninja -S "$SF" -B "$SFML_BUILD" \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="$ABI" -DANDROID_PLATFORM=android-24 -DANDROID_STL=c++_shared \
    -DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON -DSFML_BUILD_EXAMPLES=OFF -DSFML_BUILD_TEST_SUITE=OFF \
    -DSFML_BUILD_DOC=OFF -DCMAKE_INSTALL_PREFIX="$BUILD_ROOT/sfml-prefix"
cmake --build "$SFML_BUILD" --parallel "$JOBS"
cmake --install "$SFML_BUILD"

echo "=== Building all five PySFML modules and the Android entry point ==="
cmake -G Ninja -S "$PROJECT/native" -B "$NATIVE_BUILD" \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="$ABI" -DANDROID_PLATFORM=android-24 -DANDROID_STL=c++_shared \
    -DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON -DCMAKE_BUILD_TYPE=Release \
    -DSFML_SOURCE="$SF" -DSFML_PREFIX="$NDK/sources/third_party/sfml" \
    -DPYSFML_SOURCE="$PSF" -DPYTHON_PREFIX="$PREFIX"
cmake --build "$NATIVE_BUILD" --parallel "$JOBS"

echo "=== Packaging the Android project ==="
STAGED=$(mktemp -d "$BUILD_ROOT/doku2d-project.XXXXXXXX")
trap 'rm -rf -- "$STAGED"' EXIT
python3 - "$PROJECT" "$INPUT" "$STAGED" <<'PY'
import json
from pathlib import Path
import shutil, sys
source, game, target = map(Path, sys.argv[1:])
for name in ("settings.gradle", "build.gradle", "gradle.properties"):
    shutil.copy2(source / name, target / name)
shutil.copytree(source / "app", target / "app")
# Gradle merges this project's debug manifest and resources over app/src/main.
shutil.copytree(game / "android", target / "app/src/debug")
icon = target / "app/src/main/res/mipmap-xxhdpi/ic_launcher.png"
icon.parent.mkdir(parents=True)
shutil.copy2(game / "icon.png", icon)
with (target / "gradle.properties").open("a", encoding="utf-8") as properties:
    for key, value in json.loads((game / "android.json").read_text()).items():
        # Java properties use escaped Unicode, including surrogate pairs.
        units = str(value).encode("utf-16-be")
        escaped = "".join("\\u" + units[i:i+2].hex() for i in range(0, len(units), 2))
        properties.write(f"\n{key}={escaped}\n")
PY
python3 "$PROJECT/scripts/package_runtime.py" --prefix "$PREFIX" \
    --native "$NATIVE_BUILD" --pysfml "$PSF" --abi "$ABI" \
    --input "$INPUT" --physics "$PHYSICS" \
    --sfml-prefix "$NDK/sources/third_party/sfml" --ndk "$NDK" --project "$STAGED"
python3 "$PROJECT/scripts/collect_notices.py" --sources "$SRC" \
    --sfml-build "$SFML_BUILD" --ndk "$NDK" --project "$STAGED"
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$STAGED/local.properties"
cd "$STAGED"
"$TOOLS/gradle-8.11.1/bin/gradle" --no-daemon "-PtargetAbi=$ABI" assembleDebug
cp app/build/outputs/apk/debug/app-debug.apk "$INPUT/app-debug.apk"
