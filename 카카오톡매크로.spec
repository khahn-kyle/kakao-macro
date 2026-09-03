# -*- mode: python ; coding: utf-8 -*-
# 버전/권한설명을 빌드 시점에 Info.plist에 주입 —
# 빌드 후 PlistBuddy로 고치면 PyInstaller의 서명이 깨지므로 여기서 처리한다.
from version import APP_VERSION


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='카카오톡매크로',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='카카오톡매크로',
)
app = BUNDLE(
    coll,
    name='카카오톡매크로.app',
    icon=None,
    bundle_identifier=None,
    version=APP_VERSION,
    info_plist={
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'NSAccessibilityUsageDescription': '카카오톡 친구 목록 접근을 위해 손쉬운 사용 권한이 필요합니다.',
    },
)
