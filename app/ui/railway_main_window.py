"""
地铁轨道病害检测系统 - 主窗口
基于 PySide6 + OpenCV 的 MVC 架构
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QSplitter, QFrame, QGroupBox,
    QComboBox, QSlider, QLineEdit, QProgressBar, QMessageBox, QApplication,
    QDialog
)
from PySide6.QtGui import QPixmap, QImage, QColor, QBrush
from PySide6.QtCore import Qt, Signal, QSettings
import uuid
import cv2
import numpy as np
from datetime import datetime
import os
import sys

from app.core.video_thread import VideoThread
from app.core.image_processor import ImageProcessor
from app.models.database_manager import DatabaseManager
from app.ui.missed_annotation_dialog import MissedAnnotationDialog
from app.ui.admin_panel import AdminPanel
from PySide6.QtGui import QAction


class NumericTableWidgetItem(QTableWidgetItem):
    """支持数值排序的表格项"""
    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return super().__lt__(other)

class RailwayMainWindow(QMainWindow):
    """地铁轨道病害检测系统主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("地铁轨道病害检测系统")
        self.resize(1400, 900)
        
        # 初始化组件
        self.video_thread: VideoThread = None
        self.processor: ImageProcessor = None
        self.db_manager: DatabaseManager = None
        self.current_task_id: str = None
        
        # 当前帧保持
        self.current_frame = None

        # UI 初始化
        self.setup_ui()
        self.setup_connections()
        
        # 初始化数据库
        self.db_manager = DatabaseManager()
        
        # 初始化图像处理器
        self.processor = ImageProcessor()
        
        # 加载用户设置
        self.load_settings()
        
        self.log("系统初始化完成")
    
    def setup_ui(self):
        """设置 UI 布局"""
        # 主容器
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # === 菜单栏 ===
        self.menu_bar = self.menuBar()
        adv_menu = self.menu_bar.addMenu("高级 (Advanced)")
        
        action_lab = QAction("🔬 模型实验室 (Model Lab)", self)
        action_lab.triggered.connect(self._open_admin_panel)
        adv_menu.addAction(action_lab)

        # === 主分割器：上下分割 ===
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # === 上部分割器：左右分割 ===
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- 左侧控制区 ---
        left_panel = self._create_left_panel()
        content_splitter.addWidget(left_panel)
        
        # --- 中间显示区 ---
        center_panel = self._create_center_panel()
        content_splitter.addWidget(center_panel)
        
        # --- 右侧数据区 ---
        right_panel = self._create_right_panel()
        content_splitter.addWidget(right_panel)
        
        # 设置分割比例
        content_splitter.setStretchFactor(0, 1)  # 左侧
        content_splitter.setStretchFactor(1, 3)  # 中间（最大）
        content_splitter.setStretchFactor(2, 2)  # 右侧
        
        # --- 底部状态区 ---
        bottom_panel = self._create_bottom_panel()
        
        # 组装主分割器
        main_splitter.addWidget(content_splitter)
        main_splitter.addWidget(bottom_panel)
        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(main_splitter)
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        
        # === 输入源区域 ===
        source_group = QGroupBox("输入源")
        source_layout = QVBoxLayout()
        
        self.btn_open_image = QPushButton("📷 打开图片")
        self.btn_open_dataset = QPushButton("📂 打开数据集")  # 新增
        self.btn_open_video = QPushButton("🎬 打开视频")
        self.btn_open_camera = QPushButton("📹 打开摄像头")
        
        source_layout.addWidget(self.btn_open_image)
        source_layout.addWidget(self.btn_open_dataset) # 新增
        source_layout.addWidget(self.btn_open_video)
        source_layout.addWidget(self.btn_open_camera)
        source_group.setLayout(source_layout)
        
        # === 参数设置区域 ===
        params_group = QGroupBox("参数设置")
        params_layout = QVBoxLayout()
        
        # 模型配置文件 (YAML)
        config_label = QLabel("模型配置 (YAML):")
        config_layout = QHBoxLayout()
        self.line_config = QLineEdit()
        self.line_config.setPlaceholderText("可选: 仅用于记录或特定加载")
        self.btn_browse_config = QPushButton("📂")
        self.btn_browse_config.setFixedWidth(40)
        config_layout.addWidget(self.line_config)
        config_layout.addWidget(self.btn_browse_config)
        
        params_layout.addWidget(config_label)
        params_layout.addLayout(config_layout)

        # 权重文件
        weight_label = QLabel("权重文件 (.pt):")
        weight_layout = QHBoxLayout()
        self.line_weight = QLineEdit()
        self.line_weight.setPlaceholderText("默认: best.pt")
        self.btn_browse_weight = QPushButton("浏览...")
        weight_layout.addWidget(self.line_weight)
        weight_layout.addWidget(self.btn_browse_weight)
        params_layout.addWidget(weight_label)
        params_layout.addLayout(weight_layout)
        
        # 置信度阈值
        conf_label = QLabel("置信度阈值: 0.50")
        self.slider_conf = QSlider(Qt.Orientation.Horizontal)
        self.slider_conf.setMinimum(0)
        self.slider_conf.setMaximum(100)
        self.slider_conf.setValue(50)
        self.slider_conf.valueChanged.connect(
            lambda v: conf_label.setText(f"置信度阈值: {v/100:.2f}")
        )
        params_layout.addWidget(conf_label)
        params_layout.addWidget(self.slider_conf)
        
        params_group.setLayout(params_layout)
        
        # === 控制按钮区域 ===
        control_group = QGroupBox("控制")
        control_layout = QVBoxLayout()
        
        self.btn_start = QPushButton("▶️ 开始检测")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_pause = QPushButton("⏸️ 暂停")
        self.btn_pause.setEnabled(False)
        self.btn_stop = QPushButton("⏹️ 停止")
        self.btn_stop.setEnabled(False)
        
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_stop)
        control_group.setLayout(control_layout)

        # === 数据反馈区域 ===
        feedback_group = QGroupBox("数据反馈 (Data Feedback)")
        feedback_layout = QVBoxLayout()
        
        # 1. 误报反馈 (FP)
        self.btn_feedback_fp = QPushButton("❌ 误报反馈 (生成负样本)")
        self.btn_feedback_fp.setStyleSheet("color: #ff5555; font-weight: bold;")
        self.btn_feedback_fp.setToolTip("保存当前帧为负样本（无目标）")
        
        # 2. 漏检补录 (Miss)
        self.btn_feedback_miss = QPushButton("✏️ 漏检补录 (手动框选)")
        self.btn_feedback_miss.setStyleSheet("color: #55aaff; font-weight: bold;")
        self.btn_feedback_miss.setToolTip("手动框选漏检目标并保存")
        
        feedback_layout.addWidget(self.btn_feedback_fp)
        feedback_layout.addWidget(self.btn_feedback_miss)
        feedback_group.setLayout(feedback_layout)
        
        # 添加到主布局
        layout.addWidget(source_group)
        layout.addWidget(params_group)
        layout.addWidget(control_group)
        layout.addWidget(feedback_group)
        layout.addStretch()
        
        return panel
    
    def _create_center_panel(self) -> QWidget:
        """创建中间显示面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # 视频显示标签
        self.lbl_video = QLabel("视频预览区")
        self.lbl_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_video.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                color: #888888;
                border: 2px solid #555555;
                border-radius: 5px;
            }
        """)
        self.lbl_video.setMinimumSize(640, 480)
        self.lbl_video.setScaledContents(False)  # 保持比例
        
        layout.addWidget(self.lbl_video)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧数据面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # === 上部：病害列表 ===
        table_group = QGroupBox("病害检测列表")
        table_layout = QVBoxLayout()
        
        # 表格工具栏（清空按钮）
        table_toolbar = QHBoxLayout()
        table_toolbar.addStretch()
        self.btn_clear_table = QPushButton("清空列表")
        self.btn_clear_table.setFixedSize(80, 24)
        self.btn_clear_table.setStyleSheet("font-size: 12px; padding: 2px;")
        table_toolbar.addWidget(self.btn_clear_table)
        table_layout.addLayout(table_toolbar)
        
        self.table_defects = QTableWidget()
        self.table_defects.setColumnCount(5)
        self.table_defects.setHorizontalHeaderLabels(["ID", "帧号", "病害类型", "置信度", "里程位置"])
        self.table_defects.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_defects.setAlternatingRowColors(True)
        self.table_defects.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_defects.setSortingEnabled(True) # 启用排序
        
        # 双击事件
        self.table_defects.itemDoubleClicked.connect(self._on_table_double_clicked)
        # 清空按钮
        self.btn_clear_table.clicked.connect(self._on_clear_table)
        
        table_layout.addWidget(self.table_defects)
        table_group.setLayout(table_layout)
        
        # === 下部：统计图表占位符 ===
        chart_group = QGroupBox("统计图表")
        chart_layout = QVBoxLayout()
        
        self.lbl_chart_placeholder = QLabel("图表区域\n(预留用于饼图等统计图表)")
        self.lbl_chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart_placeholder.setStyleSheet("""
            QLabel {
                background-color: #2e2e2e;
                color: #888888;
                border: 1px dashed #555555;
                border-radius: 5px;
                padding: 20px;
            }
        """)
        self.lbl_chart_placeholder.setMinimumHeight(150)
        
        chart_layout.addWidget(self.lbl_chart_placeholder)
        chart_group.setLayout(chart_layout)
        
        layout.addWidget(table_group, 2)
        layout.addWidget(chart_group, 1)
        
        return panel
    
    def _create_bottom_panel(self) -> QWidget:
        """创建底部状态面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # 进度条
        progress_label = QLabel("处理进度:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        # 日志控制台
        log_label = QLabel("系统日志:")
        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(150)
        self.log_console.setPlaceholderText("系统日志将显示在这里...")
        
        layout.addLayout(progress_layout)
        layout.addWidget(log_label)
        layout.addWidget(self.log_console)
        
        return panel
    
    def setup_connections(self):
        """设置信号连接"""
        # 输入源按钮
        self.btn_open_image.clicked.connect(self._on_open_image)
        self.btn_open_dataset.clicked.connect(self._on_open_dataset) # 新增
        self.btn_open_video.clicked.connect(self._on_open_video)
        self.btn_open_camera.clicked.connect(self._on_open_camera)
        
        # 权重文件浏览
        self.btn_browse_weight.clicked.connect(self._on_browse_weight)
        # 配置文件浏览
        self.btn_browse_config.clicked.connect(self._on_browse_config)
        
        # 控制按钮
        self.btn_start.clicked.connect(self._on_start_detection)
        self.btn_pause.clicked.connect(self._on_pause_detection)
        self.btn_stop.clicked.connect(self._on_stop_detection)

        # 反馈按钮
        self.btn_feedback_fp.clicked.connect(self._on_btn_feedback_fp_clicked)
        self.btn_feedback_miss.clicked.connect(self._on_btn_feedback_miss_clicked)
    
    def _on_open_image(self):
        """打开图片"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.source_type = "image"
            self.source_path = path
            self.log(f"已选择图片: {path}")
            # 预览图片
            pixmap = QPixmap(path)
            self._update_video_display(pixmap.toImage())
            
    def _on_open_dataset(self):
        """打开数据集（文件夹）"""
        path = QFileDialog.getExistingDirectory(
            self, "选择数据集文件夹 (包含图片的文件夹)"
        )
        if path:
            self.source_type = "dataset"
            self.source_path = path
            self.log(f"已选择数据集文件夹: {path}")
            self.log("提示: 点击 [开始检测] 后将逐张检测该文件夹内的图片。")
            # 可以在这里尝试读取第一张图片并显示预览
            import os
            try:
                valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
                first_img = None
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if os.path.splitext(file)[1].lower() in valid_exts:
                            first_img = os.path.join(root, file)
                            break
                    if first_img:
                        break
                
                if first_img:
                    pixmap = QPixmap(first_img)
                    self._update_video_display(pixmap.toImage())
            except Exception:
                pass
    
    def _on_open_video(self):
        """打开视频"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频", "", "Videos (*.mp4 *.avi *.mov *.mkv)"
        )
        if path:
            self.source_type = "video"
            self.source_path = path
            self.log(f"已选择视频: {path}")
    
    def _on_open_camera(self):
        """打开摄像头"""
        self.source_type = "camera"
        self.source_path = "0"  # 默认摄像头
        self.log("已选择摄像头作为输入源")
    
    def load_settings(self):
        """加载用户设置"""
        settings = QSettings("MetroDetection", "VisualTool")
        
        # 加载配置文件路径
        config_path = settings.value("model_config_path", "")
        if config_path:
            self.line_config.setText(config_path)
            
        # 加载权重文件路径
        weight_path = settings.value("model_weight_path", "")
        if weight_path:
            self.line_weight.setText(weight_path)
            
        self.log("已加载用户设置")

    def save_settings(self):
        """保存用户设置"""
        settings = QSettings("MetroDetection", "VisualTool")
        settings.setValue("model_config_path", self.line_config.text())
        settings.setValue("model_weight_path", self.line_weight.text())

    def _on_browse_weight(self):
        """浏览权重文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模型权重文件", "", "Model Files (*.pt *.onnx *.pth)"
        )
        if path:
            self.line_weight.setText(path)
            self.save_settings()  # 保存设置
            self.log(f"已选择权重文件: {path}")
    
    def _on_browse_config(self):
        """浏览配置文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模型配置文件", "", "Config Files (*.yaml *.yml)"
        )
        if path:
            self.line_config.setText(path)
            self.save_settings()  # 保存设置
            self.log(f"已选择配置文件: {path}")

    def _on_start_detection(self):
        """开始检测"""
        if not hasattr(self, 'source_type'):
            QMessageBox.warning(self, "警告", "请先选择输入源（图片/视频/摄像头）")
            return
        
        # 获取参数
        config_path = self.line_config.text().strip()
        weight_path = self.line_weight.text().strip()
        if not weight_path:
            weight_path = "best.pt"
            
        conf_threshold = self.slider_conf.value() / 100.0
        
        # 创建任务ID
        self.current_task_id = str(uuid.uuid4())
        
        # 初始化/加载模型
        # 始终尝试加载模型，确保使用当前选择的权重
        self.log(f"正在加载模型: {weight_path} ...")
        if config_path:
            self.log(f"指定配置: {config_path}")
            
        success = self.processor.load_model(weight_path, config_path=config_path)
        
        if not success:
            QMessageBox.critical(self, "错误", f"模型加载失败: {weight_path}\n请检查文件是否存在，或环境是否包含所需的自定义模块。")
            self.log(f"❌ 模型加载失败: {weight_path}")
            return
            
        # 再次保存设置（防止用户手动输入路径未保存）
        self.save_settings()

        # 创建数据库任务记录
        self.db_manager.create_task(
            task_id=self.current_task_id,
            source_type=self.source_type,
            source_path=getattr(self, 'source_path', None),
            model_name=config_path if config_path else "Standard YOLO",
            model_path=weight_path,
            conf_threshold=conf_threshold
        )
        
        # 创建并启动视频线程
        self.video_thread = VideoThread(
            source_type=self.source_type,
            source_path=getattr(self, 'source_path', None),
            processor=self.processor,
            conf_threshold=conf_threshold
        )
        
        # 连接信号
        self.video_thread.change_pixmap_signal.connect(self._update_video_display)
        self.video_thread.update_table_signal.connect(self._update_defect_table)
        self.video_thread.update_log_signal.connect(self.log)
        self.video_thread.update_progress_signal.connect(self._update_progress)
        self.video_thread.finished_signal.connect(self._on_detection_finished)
        
        # 启动线程
        self.video_thread.start()
        
        # 更新UI状态
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        
        self.log(f"[开始] 检测任务已启动 (任务ID: {self.current_task_id[:8]}...)")
    
    def _on_pause_detection(self):
        """暂停检测"""
        if self.video_thread:
            if self.video_thread.is_paused:
                self.video_thread.resume()
                self.btn_pause.setText("⏸️ 暂停")
            else:
                self.video_thread.pause()
                self.btn_pause.setText("▶️ 继续")
    
    def _on_stop_detection(self):
        """停止检测"""
        if self.video_thread:
            self.video_thread.stop()
            self.log("[停止] 正在停止检测...")
    
    def _on_detection_finished(self):
        """检测完成回调"""
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setText("⏸️ 暂停")
        
        if self.current_task_id:
            self.db_manager.update_task_status(self.current_task_id, "finished")
        
        self.log("[完成] 检测任务已完成")
        QMessageBox.information(self, "完成", "检测任务已完成！")
    
    def _open_admin_panel(self):
        """打开模型实验室"""
        self.admin_panel = AdminPanel()
        self.admin_panel.show()

    def _update_video_display(self, qimage: QImage):
        """更新视频显示"""
        # 保存当前帧
        try:
            # 确保格式正确
            if qimage.format() != QImage.Format.Format_RGB888:
                qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
            
            width = qimage.width()
            height = qimage.height()
            
            ptr = qimage.bits()
            if hasattr(ptr, 'setsize'):
                 ptr.setsize(qimage.sizeInBytes())
            
            # copy=True 确保数据独立
            arr = np.array(ptr).reshape(height, width, 3)
            self.current_frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR).copy()
        except Exception as e:
            print(f"[Error] Frame save failed: {e}")

        # 自适应缩放
        label_size = self.lbl_video.size()
        scaled_image = qimage.scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_video.setPixmap(QPixmap.fromImage(scaled_image))
    
    def _update_defect_table(self, data: dict):
        """更新病害表格"""
        # 暂时关闭排序，避免插入时跳动
        sorting_enabled = self.table_defects.isSortingEnabled()
        self.table_defects.setSortingEnabled(False)
        
        row = self.table_defects.rowCount()
        self.table_defects.insertRow(row)
        
        # ID (使用数值项以支持排序)
        self.table_defects.setItem(row, 0, NumericTableWidgetItem(str(row + 1)))
        # 帧号
        self.table_defects.setItem(row, 1, NumericTableWidgetItem(str(data.get('frame_index', 0))))
        # 病害类型
        self.table_defects.setItem(row, 2, QTableWidgetItem(data.get('defect_type', 'Unknown')))
        
        # 置信度
        confidence = data.get('confidence', 0.0)
        conf_item = NumericTableWidgetItem(f"{confidence:.2f}")
        conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_defects.setItem(row, 3, conf_item)
        
        # 里程位置
        self.table_defects.setItem(row, 4, QTableWidgetItem(data.get('mileage', 'N/A')))
        
        # 颜色区分
        # 高置信度 (>0.85): 红色背景 (浅红)
        # 中置信度 (0.5-0.85): 黄色背景 (浅黄)
        bg_color = None
        if confidence >= 0.85:
            bg_color = QColor(255, 200, 200) # Light Red
        elif confidence >= 0.5:
            bg_color = QColor(255, 255, 200) # Light Yellow
            
        if bg_color:
            for col in range(5):
                item = self.table_defects.item(row, col)
                if item:
                    item.setBackground(QBrush(bg_color))
        
        # 恢复排序状态
        self.table_defects.setSortingEnabled(sorting_enabled)
        
        # 滚动到底部
        self.table_defects.scrollToBottom()
        
        # 保存到数据库
        if self.current_task_id:
            bbox = data.get('bbox')
            self.db_manager.insert_record(
                task_id=self.current_task_id,
                frame_index=data.get('frame_index', 0),
                defect_type=data.get('defect_type', 'Unknown'),
                confidence=confidence,
                mileage=data.get('mileage'),
                bbox=bbox
            )
    
    def _update_progress(self, value: int):
        """更新进度条"""
        self.progress_bar.setValue(value)
    
    def _on_clear_table(self):
        """清空病害列表"""
        reply = QMessageBox.question(
            self, "确认清空", "确定要清空当前的病害检测列表吗？\n注意：这不会删除数据库中的记录。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.table_defects.setRowCount(0)
            self.log("列表已清空")

    def _on_table_double_clicked(self, item: QTableWidgetItem):
        """表格双击事件 - 跳转到指定帧"""
        row = item.row()
        frame_index_item = self.table_defects.item(row, 1)
        if not frame_index_item:
            return
            
        try:
            frame_index = int(frame_index_item.text())
            
            # 情况1：检测任务正在运行或暂停中 -> 使用线程跳转
            if self.video_thread and self.video_thread.isRunning():
                self.log(f"[跳转] 正在跳转到帧: {frame_index}")
                self.video_thread.seek(frame_index)
                if not self.video_thread.is_paused:
                    self._on_pause_detection()
                return

            # 情况2：检测任务已结束或未开始 -> 尝试静态显示
            # 仅支持数据集模式的静态跳转（因为视频需要 VideoCapture，比较麻烦）
            if hasattr(self, 'source_type') and self.source_type == 'dataset' and hasattr(self, 'source_path'):
                self._show_static_dataset_image(frame_index)
            else:
                self.log("[提示] 请先启动检测任务后再跳转，或仅在数据集模式下支持离线查看。")
                
        except ValueError:
            pass

    def _show_static_dataset_image(self, frame_index: int):
        """显示数据集中的指定图片（静态模式）"""
        import os
        import cv2
        import numpy as np
        
        path = self.source_path
        if not path or not os.path.exists(path):
            return

        # 重新扫描文件列表以找到对应索引的图片
        # 注意：这里假设排序逻辑与 VideoThread 一致
        valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
        image_files = []
        try:
            for root, dirs, files in os.walk(path):
                for file in files:
                    if os.path.splitext(file)[1].lower() in valid_exts:
                        image_files.append(os.path.join(root, file))
            image_files.sort()
            
            if 0 <= frame_index < len(image_files):
                img_path = image_files[frame_index]
                self.log(f"[查看] 显示图片: {os.path.basename(img_path)}")
                
                # 读取并显示
                img_array = np.fromfile(img_path, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if frame is not None:
                    # 简单绘制一个标记（可选）
                    cv2.putText(frame, f"Frame: {frame_index} (Static View)", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
                    
                    # 转为 QImage 显示
                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    qimage = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                    self._update_video_display(qimage)
            else:
                self.log(f"[错误] 帧号 {frame_index} 超出范围")
        except Exception as e:
            self.log(f"[错误] 加载图片失败: {e}")
    
    def _ensure_feedback_dirs(self):
        """确保反馈目录存在"""
        save_root = r"D:\地铁项目\VisualTool\feedback_dataset"
        img_dir = os.path.join(save_root, "images")
        lbl_dir = os.path.join(save_root, "labels")
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)
        return img_dir, lbl_dir

    def _on_btn_feedback_fp_clicked(self):
        """误报反馈 (False Positive) - 生成负样本"""
        # 1. 暂停
        if self.video_thread and self.video_thread.isRunning() and not self.video_thread.is_paused:
            self._on_pause_detection()
            
        if self.current_frame is None:
            QMessageBox.warning(self, "警告", "当前无画面！")
            return

        try:
            img_dir, lbl_dir = self._ensure_feedback_dirs()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存图片
            img_name = f"fp_{timestamp}.jpg"
            img_path = os.path.join(img_dir, img_name)
            
            is_success, buffer = cv2.imencode(".jpg", self.current_frame)
            if is_success:
                buffer.tofile(img_path)
            else:
                raise Exception("图片编码失败")
            
            # 保存空标签文件 (负样本)
            txt_name = f"fp_{timestamp}.txt"
            txt_path = os.path.join(lbl_dir, txt_name)
            with open(txt_path, 'w') as f:
                pass # 空文件
                
            self.log(f"✅ 已记录负样本: {img_name}")
            QMessageBox.information(self, "成功", "已保存为负样本（无目标）。")
            
        except Exception as e:
            self.log(f"❌ 保存负样本失败: {e}")
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def _on_btn_feedback_miss_clicked(self):
        """漏检补录 (Missed Detection) - 手动画框"""
        # 1. 暂停
        if self.video_thread and self.video_thread.isRunning() and not self.video_thread.is_paused:
            self._on_pause_detection()
            
        if self.current_frame is None:
            QMessageBox.warning(self, "警告", "当前无画面！")
            return

        # 2. 打开对话框
        dialog = MissedAnnotationDialog(self, self.current_frame)
        if dialog.exec() == QDialog.Accepted:
            try:
                # 3. 获取数据并保存
                yolo_lines = dialog.get_yolo_data()
                
                if not yolo_lines:
                    # 如果未画任何框，视为取消
                    return
                
                img_dir, lbl_dir = self._ensure_feedback_dirs()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # 保存图片
                img_name = f"miss_{timestamp}.jpg"
                img_path = os.path.join(img_dir, img_name)
                
                is_success, buffer = cv2.imencode(".jpg", self.current_frame)
                if is_success:
                    buffer.tofile(img_path)
                else:
                    raise Exception("图片编码失败")
                    
                # 保存标签
                txt_name = f"miss_{timestamp}.txt"
                txt_path = os.path.join(lbl_dir, txt_name)
                with open(txt_path, 'w', encoding='utf-8') as f:
                    for line in yolo_lines:
                        f.write(line + "\n")
                        
                self.log(f"✅ 已保存补录数据: {img_name}")
                QMessageBox.information(self, "成功", f"补录数据已保存。\n包含 {len(yolo_lines)} 个新目标。")
                
            except Exception as e:
                self.log(f"❌ 保存补录数据失败: {e}")
                QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_console.appendPlainText(f"[{timestamp}] {message}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止视频线程
        if self.video_thread and self.video_thread.isRunning():
            self.video_thread.stop()
            # 尝试等待线程结束，如果超时则强行终止
            if not self.video_thread.wait(2000):
                self.video_thread.terminate()
                self.video_thread.wait(500)
        
        # 关闭数据库连接
        if self.db_manager:
            self.db_manager.close()
            
        # 退出前保存设置
        self.save_settings()
        
        event.accept()
        
        # 强制退出应用程序，确保所有线程和子进程都被清理
        # 这解决了关闭窗口后终端仍停留在运行状态的问题
        QApplication.instance().quit()
        # 作为最后的手段，如果上述方法无效，可以取消注释下面这行：
        # os._exit(0)