"""
AIpathCut PyInstaller 打包配置

使用方法:
    pyinstaller build/build_spec.py
"""
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 项目根目录
block_cipher = None

# 收集 OpenCV 数据文件
datas = [
    ('resources', 'resources'),  # 资源文件
] + collect_data_files('cv2', include_py_files=False)

# 隐藏导入
hiddenimports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'tkinterdnd2',
    'cv2',
    'numpy',
    'shapely',
    'PIL._tkinter_finder',
]

# 收集 OpenCV 的子模块
hiddenimports += collect_submodules('cv2')

a = Analysis(
    ['main.py'],  # 入口文件
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'scipy',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],  # 不要包含 binaries 和 datas，使用 COLLECT
    exclude_binaries=True,
    name='AIpathCut',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 使用 UPX 压缩
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico' if os.path.exists('resources/icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AIpathCut',
)
