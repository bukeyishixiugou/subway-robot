"""
诊断 PySide6 DLL 加载问题
"""
import sys
import os
import platform

print("=" * 60)
print("PySide6 诊断工具")
print("=" * 60)

# 1. 检查 Python 版本
print("\n[1] Python 版本信息:")
print(f"   版本: {sys.version}")
print(f"   可执行文件: {sys.executable}")
print(f"   平台: {platform.platform()}")

# 2. 检查 PySide6 安装
print("\n[2] PySide6 安装信息:")
try:
    import PySide6
    print(f"   安装路径: {PySide6.__file__}")
    print(f"   版本: {PySide6.__version__}")
except ImportError as e:
    print(f"   [错误] PySide6 未安装: {e}")
    sys.exit(1)

# 3. 检查 DLL 文件
print("\n[3] 检查关键 DLL 文件:")
pyside6_path = os.path.dirname(PySide6.__file__)
dll_files = [
    "Qt6Core.dll",
    "Qt6Gui.dll", 
    "Qt6Widgets.dll"
]

for dll in dll_files:
    dll_path = os.path.join(pyside6_path, dll)
    if os.path.exists(dll_path):
        print(f"   [OK] {dll}")
    else:
        print(f"   [缺失] {dll}")

# 4. 尝试导入
print("\n[4] 测试导入:")
modules_to_test = [
    ("PySide6.QtCore", "QtCore"),
    ("PySide6.QtGui", "QtGui"),
    ("PySide6.QtWidgets", "QtWidgets"),
]

for module_name, display_name in modules_to_test:
    try:
        __import__(module_name)
        print(f"   [成功] {display_name}")
    except ImportError as e:
        print(f"   [失败] {display_name}: {e}")

# 5. 检查 Visual C++ 运行时
print("\n[5] 系统信息:")
print(f"   Windows 版本: {platform.system()} {platform.release()}")
print(f"   架构: {platform.machine()}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
print("\n如果 QtWidgets 导入失败，请尝试以下解决方案:")
print("\n方案 1: 安装 Visual C++ Redistributable")
print("  下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe")
print("  安装后重启终端和程序")
print("\n方案 2: 使用 PyQt6 替代 (功能相同)")
print("  pip uninstall PySide6")
print("  pip install PyQt6")
print("\n方案 3: 检查 Python 版本兼容性")
print("  推荐使用 Python 3.8-3.11")
print(f"  当前版本: {sys.version_info.major}.{sys.version_info.minor}")
