# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Koroza\\Documents\\Antigravity\\Performance Stats\\src\\main.py'],
    pathex=['C:\\Users\\Koroza\\Documents\\Antigravity\\Performance Stats'],
    binaries=[],
    datas=[('C:\\Users\\Koroza\\Documents\\Antigravity\\Performance Stats\\ui', 'ui')],
    hiddenimports=['psutil', 'webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium', 'ctypes', 'winreg', 'json', 'platform', 'time', 'threading', 'math', 're', 'argparse', 'sys', 'os', 'pathlib', 'clr', 'pythonnet', 'src', 'src.telemetry', 'src.telemetry.engine', 'src.telemetry.cpu_collector', 'src.telemetry.gpu_collector', 'src.telemetry.ram_collector', 'src.telemetry.storage_collector', 'src.telemetry.network_collector', 'src.telemetry.process_collector', 'src.telemetry.thermals', 'src.gui', 'src.gui.window_manager', 'src.bridge', 'src.bridge.api'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GlassPerformanceHUD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
