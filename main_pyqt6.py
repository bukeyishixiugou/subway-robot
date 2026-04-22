"""
使用 PyQt6 作为 PySide6 的替代方案
PyQt6 和 PySide6 API 几乎完全相同，只是导入语句不同
"""
import sys
import os

# 尝试导入 PyQt6，如果失败则尝试 PySide6
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap
    QT_AVAILABLE = True
    QT_TYPE = "PyQt6"
    print("[信息] 使用 PyQt6")
except ImportError:
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPixmap
        QT_AVAILABLE = True
        QT_TYPE = "PySide6"
        print("[信息] 使用 PySide6")
    except ImportError as e:
        QT_AVAILABLE = False
        print("❌ 无法导入 PyQt6 或 PySide6")
        print(f"错误信息: {e}")
        print("\n🔧 解决方案:")
        print("1. 安装 PyQt6: pip install PyQt6")
        print("2. 或安装 PySide6: pip install PySide6")
        print("3. 如果仍有 DLL 错误，请安装 Visual C++ Redistributable:")
        print("   https://aka.ms/vs/17/release/vc_redist.x64.exe")
        sys.exit(1)

# 根据使用的库调整导入
if QT_TYPE == "PyQt6":
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QTableWidget,
        QHeaderView, QPlainTextEdit, QSplitter, QFrame
    )
else:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QTableWidget,
        QHeaderView, QPlainTextEdit, QSplitter, QFrame
    )

from app.ui.main_window import MainWindow

# 尝试导入 qt-material
try:
    if QT_TYPE == "PyQt6":
        # PyQt6 需要使用不同的方式应用主题
        from qt_material import apply_stylesheet
        QT_MATERIAL_AVAILABLE = True
    else:
        from qt_material import apply_stylesheet
        QT_MATERIAL_AVAILABLE = True
except ImportError:
    QT_MATERIAL_AVAILABLE = False
    print("⚠️  未安装 qt-material，使用默认样式")
    print("   可以运行: pip install qt-material")

if __name__ == "__main__":
    # 1. 创建应用
    app = QApplication(sys.argv)
    
    # 2. 应用现代皮肤
    if QT_MATERIAL_AVAILABLE:
        try:
            apply_stylesheet(app, theme='dark_teal.xml')
        except Exception as e:
            print(f"⚠️  应用主题失败: {e}，使用默认样式")

    # 3. 显示窗口
    window = MainWindow()
    window.show()
    
    # 4. 进入事件循环
    sys.exit(app.exec())
