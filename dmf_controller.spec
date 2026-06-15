# -*- mode: python ; coding: utf-8 -*-
"""
DMF 48通道控制器 — PyInstaller 打包配置
"""

import sys
import os
from pathlib import Path

block_cipher = None

# ---------- 路径 ----------
# 使用当前工作目录（因为 PyInstaller spec 中 __file__ 不可用）
ROOT = Path(os.getcwd())
BUILD_DIR = ROOT / "build"
ICON_PATH = str(BUILD_DIR / "icon.ico")
VERSION_FILE = str(BUILD_DIR / "version_info.txt")

# ---------- 数据文件 ----------
# assets 目录（样式文件等）
ASSETS_DIR = str(ROOT / "assets")

# src 目录（Python 模块）
SRC_DIR = str(ROOT / "src")

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (ASSETS_DIR, 'assets'),   # assets 目录复制到打包目录
    ],
    hiddenimports=[
        # PyQt5 相关隐式导入
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.uic',
        # 项目模块
        'src.global_cfg',
        'src.serial_driver',
        'src.grid_widget',
        'src.path_algorithm',
        'src.splash_screen',
        'src.about_dialog',
        'src.auto_update',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减小体积
        'tkinter',
        'matplotlib',
        'scipy',
        'numpy',
        'pandas',
        'PIL',
        'cv2',
        'notebook',
        'jupyter',
        'IPython',
        'setuptools',
        'pip',
        'distutils',
        'unittest',
        'pydoc',
        'test',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DMF_48Channel_Controller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
    version=VERSION_FILE,
)

# 额外数据：确保 src 模块被打包
a.datas += Tree(SRC_DIR, prefix='src')
