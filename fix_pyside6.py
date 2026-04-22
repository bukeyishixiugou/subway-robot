"""
修复 PySide6 DLL 加载问题的脚本
"""
import subprocess
import sys
import os

# 设置控制台编码为 UTF-8（Windows）
if sys.platform == "win32":
    try:
        os.system("chcp 65001 >nul")
    except:
        pass

def fix_pyside6():
    """尝试修复 PySide6 安装问题"""
    print("[修复] 开始修复 PySide6...")
    
    # 1. 卸载旧版本
    print("[1/4] 卸载旧版本 PySide6...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "PySide6"], 
                      check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass
    
    # 2. 清理缓存
    print("[2/4] 清理 pip 缓存...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "cache", "purge"], 
                      check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass
    
    # 3. 重新安装 PySide6
    print("[3/4] 重新安装 PySide6...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "PySide6"], 
                               check=True, capture_output=True, text=True)
        print("[成功] PySide6 安装成功！")
    except subprocess.CalledProcessError as e:
        print("[失败] PySide6 安装失败")
        print("错误信息:", e.stderr if hasattr(e, 'stderr') else str(e))
        print("\n建议:")
        print("  1. 检查网络连接")
        print("  2. 尝试使用国内镜像源:")
        print("     pip install PySide6 -i https://pypi.tuna.tsinghua.edu.cn/simple")
        return False
    
    # 4. 测试导入
    print("[4/4] 测试 PySide6 导入...")
    try:
        from PySide6.QtWidgets import QApplication
        print("[成功] PySide6 导入测试成功！")
        return True
    except ImportError as e:
        print(f"[失败] PySide6 导入失败: {e}")
        print("\n可能的解决方案:")
        print("  1. 安装 Visual C++ Redistributable:")
        print("     下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        print("  2. 检查 Python 版本是否兼容 (推荐 Python 3.8-3.11)")
        print("  3. 尝试使用 PyQt6 作为替代方案")
        return False

if __name__ == "__main__":
    success = fix_pyside6()
    if success:
        print("\n[完成] 修复完成！现在可以运行 python main.py")
    else:
        print("\n[警告] 修复未完全成功，请按照提示操作")
