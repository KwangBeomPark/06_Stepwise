# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir spec file for Stepwise

import sys
import os

block_cipher = None

# Resolve project root (one level up from installer/ folder)
spec_dir = SPECPATH if 'SPECPATH' in globals() else os.path.abspath('.')
project_root = os.path.abspath(os.path.join(spec_dir, '..'))
if not os.path.exists(os.path.join(project_root, 'src')):
    project_root = os.path.abspath('.')

main_script = os.path.join(project_root, 'src', 'stepwise', '__main__.py')
qss_file = os.path.join(project_root, 'src', 'stepwise', 'ui', 'styles.qss')
icon_ico = os.path.join(project_root, 'assets', 'icons', 'stepwise.ico')
icon_png = os.path.join(project_root, 'assets', 'icons', 'stepwise.png')
ui_ico = os.path.join(project_root, 'src', 'stepwise', 'ui', 'stepwise.ico')
ui_png = os.path.join(project_root, 'src', 'stepwise', 'ui', 'stepwise.png')

added_files = [
    (qss_file, 'stepwise/ui'),
    (icon_ico, 'assets/icons'),
    (icon_png, 'assets/icons'),
    (ui_ico, 'stepwise/ui'),
    (ui_png, 'stepwise/ui'),
]

# Exclude heavy unused Qt modules to keep onedir size compact
excluded_modules = [
    'PySide6.QtNetwork',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtSql',
    'PySide6.QtTest',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtSensors',
    'PySide6.QtSerialPort',
    'PySide6.QtPositioning',
    'tkinter',
    'unittest',
]

a = Analysis(
    [main_script],
    pathex=[os.path.join(project_root, 'src')],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'stepwise',
        'stepwise.app',
        'stepwise.cli',
        'stepwise.core',
        'stepwise.core.models',
        'stepwise.core.schema',
        'stepwise.core.package',
        'stepwise.core.variables',
        'stepwise.core.migration',
        'stepwise.engine',
        'stepwise.engine.runner',
        'stepwise.engine.actions',
        'stepwise.engine.timing',
        'stepwise.engine.errors',
        'stepwise.engine.preflight',
        'stepwise.engine.results',
        'stepwise.services',
        'stepwise.services.input_win',
        'stepwise.services.screen',
        'stepwise.services.clipboard',
        'stepwise.services.matcher',
        'stepwise.services.hotkeys',
        'stepwise.services.data_source',
        'stepwise.services.lock',
        'stepwise.services.power',
        'stepwise.ui',
        'stepwise.ui.strings',
        'stepwise.ui.main_window',
        'stepwise.ui.action_tree',
        'stepwise.ui.properties_panel',
        'stepwise.ui.data_panel',
        'stepwise.ui.macro_library',
        'stepwise.ui.preflight_dialog',
        'stepwise.ui.run_panel',
        'stepwise.ui.run_summary',
        'stepwise.ui.settings_dialog',
        'stepwise.ui.capture_overlay',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Stepwise',
    icon=icon_ico,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Stepwise',
)
