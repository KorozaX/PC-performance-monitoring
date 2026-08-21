"""
build_exe.py
Automated Build and Packaging Pipeline for Glassmorphism Hardware Performance HUD.

Packages the application and embedded UI assets into a standalone Windows .exe binary
using PyInstaller with single-file packaging (--onefile) and windowed overlay mode (--noconsole).
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.resolve()
SRC_MAIN = PROJECT_ROOT / "src" / "main.py"
UI_DIR = PROJECT_ROOT / "ui"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
EXE_NAME = "GlassPerformanceHUD"
TARGET_EXE = DIST_DIR / f"{EXE_NAME}.exe"

# Required hidden imports for PyInstaller bundle
HIDDEN_IMPORTS = [
    "psutil",
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "ctypes",
    "winreg",
    "json",
    "platform",
    "time",
    "threading",
    "math",
    "re",
    "argparse",
    "sys",
    "os",
    "pathlib",
    "clr",
    "pythonnet",
    "src",
    "src.telemetry",
    "src.telemetry.engine",
    "src.telemetry.cpu_collector",
    "src.telemetry.gpu_collector",
    "src.telemetry.ram_collector",
    "src.telemetry.storage_collector",
    "src.telemetry.network_collector",
    "src.telemetry.process_collector",
    "src.telemetry.thermals",
    "src.gui",
    "src.gui.window_manager",
    "src.bridge",
    "src.bridge.api",
]


def validate_environment() -> None:
    """Validates that all prerequisites and source files exist before building."""
    print("[*] Validating build environment and prerequisites...")

    if not SRC_MAIN.exists():
        raise FileNotFoundError(f"Entrypoint script not found: {SRC_MAIN}")

    if not UI_DIR.exists() or not (UI_DIR / "index.html").exists():
        raise FileNotFoundError(f"UI assets folder or index.html not found: {UI_DIR}")

    try:
        import PyInstaller  # noqa: F401
        print(f"    - PyInstaller detected: {PyInstaller.__version__}")
    except ImportError:
        raise RuntimeError("PyInstaller is not installed. Please run: pip install pyinstaller")

    try:
        import psutil  # noqa: F401
        print(f"    - psutil detected: {psutil.__version__}")
    except ImportError:
        raise RuntimeError("psutil is not installed.")

    try:
        import webview  # noqa: F401
        print(f"    - pywebview detected: {getattr(webview, '__version__', 'installed')}")
    except ImportError:
        raise RuntimeError("pywebview is not installed.")

    print("    - All core source files and dependencies validated.")


def construct_pyinstaller_args(clean: bool = True, debug: bool = False) -> list[str]:
    """Constructs the PyInstaller command-line argument list."""
    # Data separator on Windows is ';'
    sep = ";" if os.name == "nt" else ":"
    add_data_arg = f"{UI_DIR}{sep}ui"

    args = [
        str(SRC_MAIN),
        f"--name={EXE_NAME}",
        "--onefile",
        "--noconsole",
        f"--add-data={add_data_arg}",
        f"--paths={PROJECT_ROOT}",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={PROJECT_ROOT}",
    ]

    if clean:
        args.append("--clean")

    if debug:
        args.append("--debug=all")

    # Append all hidden imports
    for mod in HIDDEN_IMPORTS:
        args.append(f"--hidden-import={mod}")

    return args


def build_standalone_executable(clean: bool = True, debug: bool = False) -> Path:
    """
    Executes PyInstaller build process to produce dist/GlassPerformanceHUD.exe.
    """
    validate_environment()

    print(f"\n{'='*70}")
    print(f" BUILDING STANDALONE BINARY: {EXE_NAME}.exe")
    print(f"{'='*70}")

    pyinstaller_args = construct_pyinstaller_args(clean=clean, debug=debug)

    print(f"[*] Executing PyInstaller with args:\n    {' '.join(pyinstaller_args)}\n")
    start_time = time.perf_counter()

    try:
        import PyInstaller.__main__

        PyInstaller.__main__.run(pyinstaller_args)
    except Exception as exc:
        print(f"[*] In-process PyInstaller returned ({exc}), attempting subprocess invocation...")
        cmd = [sys.executable, "-m", "PyInstaller"] + pyinstaller_args
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            raise RuntimeError(f"PyInstaller build failed with exit code {result.returncode}")

    duration = time.perf_counter() - start_time

    if not TARGET_EXE.exists():
        raise FileNotFoundError(f"Target executable was not created: {TARGET_EXE}")

    size_bytes = TARGET_EXE.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    print(f"\n{'='*70}")
    print(f" BUILD SUCCESSFUL: {TARGET_EXE}")
    print(f" Binary Size : {size_mb:.2f} MB ({size_bytes:,} bytes)")
    print(f" Build Time  : {duration:.2f} seconds")
    print(f"{'='*70}\n")

    return TARGET_EXE


def verify_executable(exe_path: Path) -> bool:
    """
    Performs standalone binary verification testing:
    1. Version check (--version)
    2. Headless telemetry JSON export (--test-telemetry --format=json)
    3. Benchmark latency run (--benchmark --count=20)
    """
    print(f"\n[*] Starting binary verification suite on: {exe_path}")
    success = True

    # 1. Version check
    print("\n--- Test 1: Binary Version Check (--version) ---")
    res_ver = subprocess.run([str(exe_path), "--version"], capture_output=True, text=True)
    print(f"Output: {res_ver.stdout.strip() or res_ver.stderr.strip()}")
    if res_ver.returncode == 0:
        print("[PASS] Version query successful.")
    else:
        print(f"[FAIL] Version query returned exit code {res_ver.returncode}")
        success = False

    # 2. Telemetry JSON export
    print("\n--- Test 2: Headless Telemetry JSON Export (--test-telemetry --format=json) ---")
    res_tel = subprocess.run(
        [str(exe_path), "--test-telemetry", "--format=json", "--count=1"],
        capture_output=True,
        text=True,
    )
    print(f"Output preview:\n{res_tel.stdout[:400]}...")
    if res_tel.returncode == 0 and ("\"timestamp\"" in res_tel.stdout or "\"cpu\"" in res_tel.stdout):
        print("[PASS] Telemetry JSON query successful.")
    else:
        print(f"[FAIL] Telemetry JSON query returned exit code {res_tel.returncode}")
        success = False

    # 3. Latency Benchmark
    print("\n--- Test 3: Telemetry Latency Benchmark (--benchmark --count=20) ---")
    res_bm = subprocess.run(
        [str(exe_path), "--benchmark", "--count=20"],
        capture_output=True,
        text=True,
    )
    print(f"Output:\n{res_bm.stdout.strip() or res_bm.stderr.strip()}")
    if res_bm.returncode == 0:
        print("[PASS] Benchmark execution successful.")
    else:
        print(f"[FAIL] Benchmark returned exit code {res_bm.returncode}")
        success = False

    return success


def main():
    parser = argparse.ArgumentParser(description="GlassPerformanceHUD PyInstaller Build Pipeline")
    parser.add_argument("--no-clean", action="store_true", help="Skip PyInstaller cache cleaning")
    parser.add_argument("--debug", action="store_true", help="Build with PyInstaller debug mode")
    parser.add_argument("--verify", action="store_true", help="Run verification tests after build")
    parser.add_argument("--verify-only", action="store_true", help="Run verification tests on existing binary without rebuilding")
    args = parser.parse_args()

    if args.verify_only:
        if not TARGET_EXE.exists():
            print(f"[FAIL] Target executable not found: {TARGET_EXE}")
            sys.exit(1)
        passed = verify_executable(TARGET_EXE)
        sys.exit(0 if passed else 1)

    target_exe = build_standalone_executable(clean=not args.no_clean, debug=args.debug)

    if args.verify:
        passed = verify_executable(target_exe)
        if not passed:
            sys.exit(1)


if __name__ == "__main__":
    main()
