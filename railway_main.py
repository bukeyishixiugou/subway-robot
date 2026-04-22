"""
地铁轨道病害检测系统 - 程序入口
"""
import sys
import os
# 设置环境变量（如果需要）
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
# 尝试导入 PySide6
try:
    from PySide6.QtWidgets import QApplication
    PYSIDE6_AVAILABLE = True
except ImportError as e:
    PYSIDE6_AVAILABLE = False
    print("❌ PySide6 导入失败！")
    print(f"错误信息: {e}")
    print("\n🔧 解决方案:")
    print("1. 安装 PySide6: pip install PySide6")
    print("2. 如果仍有 DLL 错误，请安装 Visual C++ Redistributable:")
    print("   https://aka.ms/vs/17/release/vc_redist.x64.exe")
    sys.exit(1)
from app.ui.railway_main_window import RailwayMainWindow
# 尝试导入 qt-material
try:
    from qt_material import apply_stylesheet
    QT_MATERIAL_AVAILABLE = True
except ImportError:
    QT_MATERIAL_AVAILABLE = False
    print("⚠️  未安装 qt-material，使用默认样式")
    print("   可以运行: pip install qt-material")

if __name__ == "__main__":
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("地铁轨道病害检测系统")
    
    # 应用主题
    if QT_MATERIAL_AVAILABLE:
        try:
            apply_stylesheet(app, theme='dark_teal.xml')
            print("[主题] 已应用 dark_teal 主题")
        except Exception as e:
            print(f"⚠️  应用主题失败: {e}，使用默认样式")
    
    # 创建并显示主窗口
    window = RailwayMainWindow()
    window.show()
    
    # 进入事件循环
    sys.exit(app.exec())
