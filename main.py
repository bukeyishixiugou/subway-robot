import sys
import os

# 尝试导入 PySide6，如果失败则提供友好的错误提示
try:
    import sys
    # 找到这一行：
    # from PyQt6.QtWidgets import QApplication  <-- 删掉这行
    # 改成下面这行：
    from PySide6.QtWidgets import QApplication 

    # ... (中间代码保持不变) ...

    from app.ui.main_window import MainWindow
    # ...
except ImportError as e:
    PYSIDE6_AVAILABLE = False
    print("❌ PySide6 导入失败！")
    print(f"错误信息: {e}")
    print("\n🔧 解决方案:")
    print("1. 运行修复脚本: python fix_pyside6.py")
    print("2. 或手动重新安装: pip uninstall PySide6 && pip install PySide6")
    print("3. 如果仍有问题，可能需要安装 Visual C++ Redistributable")
    print("   下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe")
    sys.exit(1)

from app.ui.main_window import MainWindow

# 尝试导入 qt-material，如果失败则使用默认样式
try:
    from qt_material import apply_stylesheet
    QT_MATERIAL_AVAILABLE = True
except ImportError:
    QT_MATERIAL_AVAILABLE = False
    print("⚠️  未安装 qt-material，使用默认样式")
    print("   可以运行: pip install qt-material")

if __name__ == "__main__":
    # 1. 创建应用
    app = QApplication(sys.argv)
    
    # 2. 应用现代皮肤 (可选主题: 'dark_teal.xml', 'light_blue.xml' 等)
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
