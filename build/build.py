"""
AIpathCut 打包脚本

运行此脚本会将项目打包为可执行文件
"""
import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, cwd=None):
    """运行命令并显示输出"""
    print(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"错误: 命令执行失败，退出码 {result.returncode}")
        sys.exit(1)

def build():
    """执行打包"""
    # 确保在项目根目录
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("=" * 50)
    print("AIpathCut 打包工具")
    print("=" * 50)

    # 检查依赖
    print("\n1. 检查依赖...")
    try:
        import PyInstaller
        print(f"   PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("   错误: 未安装 PyInstaller")
        print("   请运行: pip install pyinstaller")
        sys.exit(1)

    # 清理旧的构建
    print("\n2. 清理旧的构建文件...")
    for path in ['build', 'dist']:
        p = Path(path)
        if p.exists():
            import shutil
            shutil.rmtree(p)
            print(f"   已删除: {path}/")

    # 执行打包
    print("\n3. 开始打包...")
    run_command([
        sys.executable, '-m', 'PyInstaller',
        'build/build_spec.py'
    ])

    print("\n" + "=" * 50)
    print("打包完成！")
    print("=" * 50)
    print(f"\n可执行文件位于: dist/AIpathCut/")
    print(f"主程序: dist/AIpathCut/AIpathCut.exe")
    print("\n你可以:")
    print("  1. 直接运行 dist/AIpathCut/AIpathCut.exe 测试")
    print("  2. 将整个 dist/AIpathCut/ 文件夹打包分发")

if __name__ == '__main__':
    build()
