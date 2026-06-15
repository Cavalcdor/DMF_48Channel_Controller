"""
DMF 48通道控制器 — 一键构建脚本

用法：
    python build_app.py             完整构建（图标 + PyInstaller + 安装包）
    python build_app.py --exe-only  仅打包 exe，不生成安装包
    python build_app.py --clean     清理构建产物

依赖：
    pip install pyinstaller
    (安装 Inno Setup: https://jrsoftware.org/isdl.php)
"""

import sys
import shutil
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
SPEC_FILE = ROOT / "dmf_controller.spec"
ICON_FILE = BUILD_DIR / "icon.ico"
VERSION_FILE = BUILD_DIR / "version_info.txt"
DIST_EXE_DIR = DIST_DIR / "DMF_48Channel_Controller"
DIST_EXE_FILE = DIST_DIR / "DMF_48Channel_Controller.exe"  # 单文件模式
ISS_FILE = BUILD_DIR / "setup_installer.iss"


def print_step(msg):
    """打印带格式的步骤信息。"""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def check_dependencies():
    """检查构建所需的依赖是否安装。"""
    missing = []

    # 检查 PyInstaller
    try:
        import PyInstaller  # noqa
        print("✓ PyInstaller 已安装")
    except ImportError:
        missing.append("PyInstaller")

    # 检查 Inno Setup (用于生成安装包)
    iscc = (
        shutil.which("iscc")
        or shutil.which(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
        or shutil.which(r"C:\Program Files\Inno Setup 6\ISCC.exe")
    )
    if iscc:
        print(f"✓ Inno Setup 已找到: {iscc}")
    else:
        print("⚠ Inno Setup 未找到（如需生成安装包请安装：https://jrsoftware.org/isdl.php）")
        print("  仍可执行 --exe-only 模式仅生成 exe 文件")

    if missing:
        print(f"\n❌ 缺少依赖: {', '.join(missing)}")
        print(f"   请运行: pip install pyinstaller")
        sys.exit(1)


def step_generate_icon():
    """步骤1: 生成应用图标。"""
    if ICON_FILE.exists():
        print(f"✓ 图标已存在: {ICON_FILE}")
        return

    print_step("步骤1/4: 生成应用图标")
    print("  正在使用 PyQt5 绘制芯片风格图标...")

    result = subprocess.run(
        [sys.executable, str(BUILD_DIR / "generate_icon.py")],
        cwd=str(BUILD_DIR),
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"  ❌ 图标生成失败: {result.stderr}")
        sys.exit(1)

    print(f"  ✓ {result.stdout.strip()}")


def step_pyinstaller():
    """步骤2: 使用 PyInstaller 打包 exe。"""
    print_step("步骤2/4: PyInstaller 打包中")
    print("  这可能需要 1~3 分钟，请稍候...\n")

    # 清理旧的打包产物
    if DIST_EXE_DIR.exists():
        shutil.rmtree(DIST_EXE_DIR)

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC_FILE)],
        cwd=str(ROOT),
        capture_output=True, text=True
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:500])

    if result.returncode != 0:
        print(f"  ❌ PyInstaller 打包失败")
        sys.exit(1)

    exe_path = DIST_EXE_FILE if DIST_EXE_FILE.exists() else DIST_EXE_DIR / "DMF_48Channel_Controller.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n  ✓ 打包成功！")
        print(f"  📦 可执行文件: {exe_path}")
        print(f"  📏 文件大小: {size_mb:.1f} MB")
    else:
        print(f"  ❌ 未找到输出文件: {DIST_EXE_FILE} 或 {DIST_EXE_DIR / 'DMF_48Channel_Controller.exe'}")
        sys.exit(1)


def step_build_installer():
    """步骤3: 使用 Inno Setup 生成安装包。"""
    print_step("步骤3/4: 生成安装包")

    # 查找 ISCC
    iscc = (
        shutil.which("iscc")
        or shutil.which(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
        or shutil.which(r"C:\Program Files\Inno Setup 6\ISCC.exe")
    )

    if not iscc:
        print("  ⚠ Inno Setup 未安装，跳过安装包生成。")
        print("  可执行文件已生成在: dist/DMF_48Channel_Controller/")
        print("  如需生成安装包，请安装 Inno Setup: https://jrsoftware.org/isdl.php")
        print("  然后运行: iscc build/setup_installer.iss")
        return

    print(f"  使用 Inno Setup: {iscc}")

    result = subprocess.run(
        [iscc, str(ISS_FILE)],
        cwd=str(BUILD_DIR),
        capture_output=True, text=True
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode != 0:
        print(f"  ⚠ 安装包生成可能有问题，请检查输出。")
    else:
        # 查找生成的安装包
        setup_files = list(BUILD_DIR.glob("DMF_48Channel_Controller_Setup_*.exe"))
        if setup_files:
            for f in setup_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"\n  ✓ 安装包生成成功！")
                print(f"  📦 安装包: {f}")
                print(f"  📏 文件大小: {size_mb:.1f} MB")
                print(f"  👤 作者: Charles WENG")
                print(f"  📅 构建日期: 2026-06-15")


def step_summary():
    """步骤4: 构建总结。"""
    print_step("步骤4/4: 构建总结")

    exe_path = DIST_EXE_FILE if DIST_EXE_FILE.exists() else DIST_EXE_DIR / "DMF_48Channel_Controller.exe"
    setup_files = list(BUILD_DIR.glob("DMF_48Channel_Controller_Setup_*.exe"))

    print("  📂 输出目录结构：")
    print(f"     {ROOT}/")
    print(f"     ├── dist/")
    if exe_path.exists():
        print(f"     │   └── DMF_48Channel_Controller.exe  ({exe_path.stat().st_size // 1024 // 1024} MB)")

    print(f"     └── build/")
    for f in sorted(BUILD_DIR.glob("DMF_48Channel_Controller_Setup_*.exe")):
        print(f"         └── {f.name}  ({f.stat().st_size // 1024 // 1024} MB)")

    if setup_files:
        print(f"\n  ✅ 全部完成！安装包位于: {setup_files[0]}")
    elif exe_path.exists():
        print(f"\n  ✅ Exe 打包完成！位于: {exe_path}")
    else:
        print(f"\n  ❌ 构建似乎未成功，请检查上面的错误信息。")
    print(f"  👤 作者: Charles WENG")
    print(f"  📅 构建日期: 2026-06-15")


def clean():
    """清理所有构建产物。"""
    print_step("清理构建产物")

    dirs_to_clean = [
        ROOT / "build" / "icon.ico",
        ROOT / "build" / "icon_preview.png",
        ROOT / "build" / "DMF_48Channel_Controller_Setup_*.exe",
        ROOT / "__pycache__",
        ROOT / "build" / "__pycache__",
        ROOT / "dist",
    ]

    for p in ROOT.glob("DMF_48Channel_Controller_Setup_*.exe"):
        print(f"  🗑 删除: {p}")
        p.unlink()

    for p in ROOT.glob("*.spec"):
        if p.name != "dmf_controller.spec":
            print(f"  🗑 删除: {p}")
            p.unlink()

    for item in dirs_to_clean:
        p = Path(item)
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
                print(f"  🗑 删除目录: {p}")
            else:
                # Handle wildcards
                if "*" in str(p):
                    for f in ROOT.glob(str(p.relative_to(ROOT))):
                        f.unlink()
                        print(f"  🗑 删除: {f}")
                else:
                    p.unlink()
                    print(f"  🗑 删除: {p}")

    # 清理 PyInstaller 临时文件
    for p in ROOT.glob("**/__pycache__"):
        if p.is_dir():
            shutil.rmtree(p)
    for p in ROOT.glob("*.pyc"):
        p.unlink()

    print(f"\n  ✓ 清理完成！")


def main():
    parser = argparse.ArgumentParser(description="DMF 48通道控制器 — 一键构建工具")
    parser.add_argument("--exe-only", action="store_true", help="仅打包 exe，不生成安装包")
    parser.add_argument("--clean", action="store_true", help="清理构建产物")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    print(f"{'='*60}")
    print(f"  DMF 48通道控制器 — 构建工具")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"{'='*60}")

    check_dependencies()
    step_generate_icon()
    step_pyinstaller()

    if not args.exe_only:
        step_build_installer()

    step_summary()


if __name__ == "__main__":
    main()
