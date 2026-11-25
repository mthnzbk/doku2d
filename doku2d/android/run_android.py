"""Build, install and launch a project on an Android development device."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

from .build_android import ABIS, _wsl_prefix, build_android


def _adb_commands():
    sdk_roots = [os.environ.get(name) for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT")]
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        sdk_roots.append(Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk")
    elif sys.platform == "darwin":
        sdk_roots.append(Path.home() / "Library/Android/sdk")
    elif sys.platform.startswith("linux"):
        sdk_roots.extend([
            Path.home() / "Android/Sdk",
            Path(os.environ.get("DOKU2D_ANDROID_CACHE",
                                Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) /
                                "doku2d/android")) / "tools/android-sdk",
            Path("/opt/koraandroid/tools/android-sdk"),
        ])
    adb = shutil.which("adb")
    if adb:
        yield [adb], []
    for root in filter(None, sdk_roots):
        candidate = Path(root) / "platform-tools" / ("adb.exe" if sys.platform == "win32" else "adb")
        if candidate.is_file() and str(candidate) != adb:
            yield [str(candidate)], []
            break
    if sys.platform == "win32":
        wsl = _wsl_prefix()
        location = subprocess.run([*wsl, "sh", "-c", '''
            command -v adb ||
            for sdk in "${ANDROID_HOME:-/nonexistent}" /opt/koraandroid/tools/android-sdk \
                "${DOKU2D_ANDROID_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/doku2d/android}/tools/android-sdk"; do
                if [ -x "$sdk/platform-tools/adb" ]; then
                    printf '%s\n' "$sdk/platform-tools/adb"
                    break
                fi
            done
        '''], capture_output=True, text=True, check=True).stdout.strip()
        if location:
            yield [*wsl, location], wsl


def _select_device(serial):
    available = {}
    observed = {}
    found_adb = False
    for adb, wsl in _adb_commands():
        found_adb = True
        listing = subprocess.check_output([*adb, "devices"], text=True)
        for line in listing.splitlines():
            fields = line.split()
            if len(fields) < 2 or fields[0] == "List" or line.startswith("*"):
                continue
            identifier, state = fields[:2]
            observed[identifier] = state
            if state == "device":
                available.setdefault(identifier, (adb, wsl))
        if serial in available:
            return serial, *available[serial]
    if not found_adb:
        raise RuntimeError("ADB is missing. Install Android SDK Platform-Tools or add adb to PATH.")
    choices = list(available)
    if serial or not choices:
        states = ", ".join(f"{name} ({state})" for name, state in observed.items()) or "none"
        raise RuntimeError(f"No matching authorized Android device. Detected: {states}. "
                           "Connect a device with USB debugging enabled or start an emulator.")
    if len(choices) == 1:
        serial = choices[0]
    else:
        listing = "\n".join(f"{i}. {name}" for i, name in enumerate(choices, 1))
        if not sys.stdin.isatty():
            raise RuntimeError(f"Choose an Android device with --device SERIAL:\n{listing}")
        print(listing)
        try:
            index = int(input("Android device number: "))
        except (EOFError, ValueError):
            raise ValueError("Select a device number or pass --device SERIAL.") from None
        if not 1 <= index <= len(choices):
            raise ValueError("Android device number is out of range.")
        serial = choices[index - 1]
    return serial, *available[serial]


def run_android(project=".", *, device=None):
    serial, adb, wsl = _select_device(device)
    command = [*adb, "-s", serial]
    supported = subprocess.check_output(
        [*command, "shell", "getprop", "ro.product.cpu.abilist"], text=True).strip().split(",")
    abi = next((value for value in supported if value in ABIS), None)
    if abi is None:
        raise RuntimeError(f"{serial} has no supported 64-bit Android ABI: {', '.join(supported)}")
    print(f"Building for {serial} ({abi})", flush=True)
    apk = build_android(project, abi)
    apk_arg = str(apk)
    if wsl:
        apk_arg = subprocess.check_output([*wsl, "wslpath", "-a", apk_arg], text=True).strip()
    app_id = apk.name.removesuffix(f"-{abi}-debug.apk")
    subprocess.run([*command, "install", "-r", apk_arg], check=True)
    launcher = subprocess.check_output([
        *command, "shell", "cmd", "package", "resolve-activity", "--brief",
        "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", "-p", app_id,
    ], text=True)
    component = next((line.strip() for line in launcher.splitlines()
                      if line.strip().startswith(f"{app_id}/")), None)
    if component is None:
        raise RuntimeError(f"Android could not find the launcher for {app_id}.")
    result = subprocess.run([*command, "shell", "am", "start", "-W", "-n", component],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout.strip(), flush=True)
    if result.returncode or "Error:" in result.stdout or "Exception" in result.stdout:
        raise RuntimeError(f"Android could not launch {app_id}.")

    process = subprocess.run([*command, "shell", "pidof", "-s", app_id],
                             text=True, capture_output=True)
    pid = process.stdout.strip()
    if not pid.isdecimal():
        subprocess.run([*command, "logcat", "-d", "-t", "100", "-s", "PySFML", "AndroidRuntime"],
                       check=False)
        raise RuntimeError(f"{app_id} did not stay running after launch.")
    print("Showing Android logs. Press Ctrl+C to stop following them.", flush=True)
    try:
        subprocess.run([*command, "logcat", f"--pid={pid}", "PySFML:V", "*:E"], check=True)
    except KeyboardInterrupt:
        pass
    return 0
