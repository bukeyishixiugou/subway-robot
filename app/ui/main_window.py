from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTableWidget,
    QHeaderView, QPlainTextEdit, QSplitter, QFrame
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from app.core.worker import ScriptRunnerWorker
from app.core.file_manager import FileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能可视化工控台 (Qt + Python)")
        self.resize(1000, 700)
        
        # 初始化 UI
        self.setup_ui()
        
        # 线程占位符
        self.worker = None

    def setup_ui(self):
        # 主容器
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # --- 1. 顶部控制栏 ---
        control_panel = QFrame()
        control_panel.setFrameShape(QFrame.StyledPanel)
        btn_layout = QHBoxLayout(control_panel)
        
        self.btn_img = QPushButton("🖼️ 加载图片")
        self.btn_folder = QPushButton("📂 读取数据文件夹")
        self.btn_run = QPushButton("▶️ 执行 Python 脚本")
        self.btn_run.setProperty('class', 'success')  # 用于 qt-material 样式
        
        btn_layout.addWidget(self.btn_img)
        btn_layout.addWidget(self.btn_folder)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_run)
        
        # --- 2. 内容区域 (分割器) ---
        splitter_v = QSplitter(Qt.Vertical)  # 上下分割
        splitter_h = QSplitter(Qt.Horizontal)  # 左右分割

        # 左侧：图片显示
        self.lbl_image = QLabel("图片预览区")
        self.lbl_image.setAlignment(Qt.AlignCenter)
        self.lbl_image.setStyleSheet("border: 2px dashed #555;")
        self.lbl_image.setMinimumSize(400, 300)

        # 右侧：数据表格
        self.table_data = QTableWidget()
        self.table_data.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 底部：日志控制台
        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setPlaceholderText("系统日志将显示在这里...")
        self.log_console.setMaximumHeight(200)

        # 组装布局
        splitter_h.addWidget(self.lbl_image)
        splitter_h.addWidget(self.table_data)
        splitter_h.setStretchFactor(0, 1)
        splitter_h.setStretchFactor(1, 2)

        splitter_v.addWidget(splitter_h)
        splitter_v.addWidget(self.log_console)

        main_layout.addWidget(control_panel)
        main_layout.addWidget(splitter_v)

        # --- 信号绑定 ---
        self.btn_img.clicked.connect(self.load_image)
        self.btn_folder.clicked.connect(self.load_folder)
        self.btn_run.clicked.connect(self.run_script)

    def log(self, message):
        """追加日志"""
        self.log_console.appendPlainText(message)

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.bmp)")
        if path:
            pixmap = QPixmap(path)
            scaled_pixmap = pixmap.scaled(
                self.lbl_image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.lbl_image.setPixmap(scaled_pixmap)
            self.log(f"已加载图片: {path}")

    def load_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择数据文件夹")
        if path:
            self.log(f"正在扫描文件夹: {path}")
            df = FileManager.get_folder_data(path)
            if df is not None:
                FileManager.populate_table(self.table_data, df)
                self.log(f"数据加载完成，共 {len(df)} 条记录")
            else:
                self.log("❌ 读取文件夹失败")

    def run_script(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Python 脚本", "", "Python Files (*.py)")
        if path:
            self.btn_run.setEnabled(False)  # 禁用按钮防止重复点击
            self.log(f"准备执行脚本: {path}")
            
            # 实例化线程
            self.worker = ScriptRunnerWorker(path)
            self.worker.log_signal.connect(self.log)
            self.worker.error_signal.connect(self.log)
            self.worker.finished_signal.connect(lambda: self.btn_run.setEnabled(True))
            
            # 启动线程
            self.worker.start()
