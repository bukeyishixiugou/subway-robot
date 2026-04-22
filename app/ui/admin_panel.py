"""
模型实验室 - 管理面板
集成了数据复核清洗与模型微调训练功能。
"""
import os
import shutil
import cv2
import yaml
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QListWidget, 
    QPushButton, QLabel, QSplitter, QMessageBox, QLineEdit, 
    QSpinBox, QDoubleSpinBox, QProgressBar, QTextEdit, QFileDialog, QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal, QRect
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor

from app.ui.annotation_dialog import CanvasLabel, NAME_TO_ID, CLASS_MAP
from app.core.dataset_utils import prepare_finetune_dataset

# -----------------------------------------------------------------------------
# 训练线程
# -----------------------------------------------------------------------------
class TrainingThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(str) # 返回 best.pt 路径
    
    def __init__(self, yaml_path, weight_path, epochs, batch, lr, model_config=None):
        super().__init__()
        self.yaml_path = yaml_path
        self.weight_path = weight_path
        self.model_config = model_config # Optional model structure yaml
        self.epochs = epochs
        self.batch = batch
        self.lr = lr
        self.is_running = False
        
    def run(self):
        self.is_running = True
        try:
            from ultralytics import YOLO
            
            # Load model logic
            if self.model_config and os.path.exists(self.model_config):
                self.log_signal.emit(f"🏗️ 构建模型结构: {self.model_config}")
                self.log_signal.emit(f"📥 加载预训练权重: {self.weight_path}")
                # Load structure then weights
                model = YOLO(self.model_config)
                model.load(self.weight_path)
            else:
                self.log_signal.emit(f"🚀 直接加载模型: {self.weight_path}")
                model = YOLO(self.weight_path)
            
            # 添加回调以捕获进度 (简化版，直接从 stdout 捕获较难，这里模拟或利用简单回调)
            # 为了简单起见，我们只能在结束后发送完成，过程日志通常直接打印到控制台
            # 若要重定向 stdout，需要更复杂的 hack。
            # 这里我们尝试添加一个自定义 callback
            
            def on_train_epoch_end(trainer):
                if not self.is_running:
                    raise InterruptedError("Training stopped by user")
                epoch = trainer.epoch + 1
                total = trainer.epochs
                prog = int(epoch / total * 100)
                self.progress_signal.emit(prog)
                self.log_signal.emit(f"Epoch {epoch}/{total} completed. Box Loss: {trainer.loss_items[0]:.4f}")

            model.add_callback("on_train_epoch_end", on_train_epoch_end)
            
            self.log_signal.emit("🔄 开始训练... (请耐心等待，详细日志请查看终端)")
            
            results = model.train(
                data=self.yaml_path,
                epochs=self.epochs,
                batch=self.batch,
                lr0=self.lr,
                imgsz=640,
                workers=0, # Windows 下必须为 0
                amp=False, # 保持数值稳定
                project="runs/finetune",
                name="finetune_v1",
                exist_ok=True # 允许覆盖
            )
            
            # 获取最佳权重路径
            best_pt = str(results.save_dir / "weights" / "best.pt")
            self.log_signal.emit(f"✅ 训练完成! 最佳权重已保存: {best_pt}")
            self.finished_signal.emit(best_pt)
            
        except Exception as e:
            self.log_signal.emit(f"❌ 训练出错: {str(e)}")
        finally:
            self.is_running = False

    def stop(self):
        self.is_running = False

# -----------------------------------------------------------------------------
# 管理面板
# -----------------------------------------------------------------------------
class AdminPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("模型实验室 (Model Lab)")
        self.resize(1200, 800)
        
        self.feedback_dir = r"D:\地铁项目\VisualTool\feedback_dataset"
        self.verified_dir = r"D:\地铁项目\VisualTool\verified_dataset"
        self._ensure_dirs()
        
        self.setup_ui()
        
    def _ensure_dirs(self):
        os.makedirs(os.path.join(self.feedback_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(self.feedback_dir, "labels"), exist_ok=True)
        os.makedirs(os.path.join(self.verified_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(self.verified_dir, "labels"), exist_ok=True)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_review_tab(), "🔍 数据复核 (Data Review)")
        self.tabs.addTab(self._create_train_tab(), "🏋️ 训练中心 (Training Center)")
        
        layout.addWidget(self.tabs)
        
    # --- Tab 1: 数据复核 ---
    def _create_review_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 左侧列表
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("待复核数据:"))
        self.file_list = QListWidget()
        self.file_list.currentItemChanged.connect(self._on_file_selected)
        left_layout.addWidget(self.file_list)
        self.btn_refresh = QPushButton("🔄 刷新列表")
        self.btn_refresh.clicked.connect(self._refresh_file_list)
        left_layout.addWidget(self.btn_refresh)
        
        # 中间画布
        right_layout = QVBoxLayout()
        self.canvas = CanvasLabel()
        self.canvas.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
        self.canvas.setMinimumSize(640, 480)
        self.canvas.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.canvas, 1)
        
        # 底部工具栏
        toolbar = QHBoxLayout()
        self.btn_approve = QPushButton("✅ 通过并入库 (Approve)")
        self.btn_approve.clicked.connect(self._on_approve)
        self.btn_approve.setStyleSheet("background-color: #4CAF50; color: white;")
        
        self.btn_discard = QPushButton("🗑️ 废弃 (Discard)")
        self.btn_discard.clicked.connect(self._on_discard)
        self.btn_discard.setStyleSheet("background-color: #f44336; color: white;")
        
        toolbar.addStretch()
        toolbar.addWidget(self.btn_discard)
        toolbar.addWidget(self.btn_approve)
        right_layout.addLayout(toolbar)
        
        # 分割
        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter)
        
        # 初始化列表
        self._refresh_file_list()
        
        return widget

    def _refresh_file_list(self):
        self.file_list.clear()
        img_dir = os.path.join(self.feedback_dir, "images")
        if os.path.exists(img_dir):
            files = [f for f in os.listdir(img_dir) if f.lower().endswith(('.jpg', '.png'))]
            self.file_list.addItems(sorted(files))

    def _on_file_selected(self, current, previous):
        if not current:
            return
        
        filename = current.text()
        img_path = os.path.join(self.feedback_dir, "images", filename)
        txt_name = os.path.splitext(filename)[0] + ".txt"
        txt_path = os.path.join(self.feedback_dir, "labels", txt_name)
        
        if os.path.exists(img_path):
            # 读取图片
            # 处理中文路径
            img_array = np.fromfile(img_path, dtype=np.uint8)
            cv_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            self.current_cv_img = cv_img
            self.canvas.set_image(cv_img)
            
            # 读取标签
            boxes = []
            if os.path.exists(txt_path):
                with open(txt_path, 'r') as f:
                    lines = f.readlines()
                    h, w = cv_img.shape[:2]
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls_id = int(parts[0])
                            cx, cy, bw, bh = map(float, parts[1:5])
                            
                            # 还原坐标
                            x = int((cx - bw/2) * w)
                            y = int((cy - bh/2) * h)
                            ww = int(bw * w)
                            hh = int(bh * h)
                            
                            boxes.append({
                                'class_id': cls_id,
                                'rect': QRect(x, y, ww, hh)
                            })
            self.canvas.set_boxes(boxes)

    def _on_approve(self):
        item = self.file_list.currentItem()
        if not item: return
        
        filename = item.text()
        src_img = os.path.join(self.feedback_dir, "images", filename)
        
        txt_name = os.path.splitext(filename)[0] + ".txt"
        src_txt = os.path.join(self.feedback_dir, "labels", txt_name)
        
        dst_img = os.path.join(self.verified_dir, "images", filename)
        dst_txt = os.path.join(self.verified_dir, "labels", txt_name)
        
        try:
            shutil.move(src_img, dst_img)
            if os.path.exists(src_txt):
                shutil.move(src_txt, dst_txt)
            else:
                # 如果没有txt (负样本)，创建一个空的
                with open(dst_txt, 'w') as f: pass
                
            self.file_list.takeItem(self.file_list.row(item))
            self.canvas.img_pixmap = None
            self.canvas.update()
            QMessageBox.information(self, "成功", "已入库！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"移动文件失败: {e}")

    def _on_discard(self):
        item = self.file_list.currentItem()
        if not item: return
        
        reply = QMessageBox.question(self, "确认", "确定要永久删除该样本吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return
        
        filename = item.text()
        src_img = os.path.join(self.feedback_dir, "images", filename)
        txt_name = os.path.splitext(filename)[0] + ".txt"
        src_txt = os.path.join(self.feedback_dir, "labels", txt_name)
        
        try:
            os.remove(src_img)
            if os.path.exists(src_txt):
                os.remove(src_txt)
            self.file_list.takeItem(self.file_list.row(item))
            self.canvas.img_pixmap = None
            self.canvas.update()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败: {e}")

    # --- Tab 2: 训练中心 ---
    def _create_train_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 配置区
        config_group = QGroupBox("微调配置")
        form_layout = QVBoxLayout()
        
        # Data YAML
        yaml_layout = QHBoxLayout()
        yaml_layout.addWidget(QLabel("原始数据集 (YAML):"))
        self.line_orig_yaml = QLineEdit()
        self.btn_yaml = QPushButton("浏览")
        self.btn_yaml.clicked.connect(lambda: self._browse_file(self.line_orig_yaml, "*.yaml"))
        yaml_layout.addWidget(self.line_orig_yaml)
        yaml_layout.addWidget(self.btn_yaml)
        form_layout.addLayout(yaml_layout)

        # Model Config YAML (New)
        model_cfg_layout = QHBoxLayout()
        model_cfg_layout.addWidget(QLabel("模型结构 (YAML, 可选):"))
        self.line_model_yaml = QLineEdit()
        self.line_model_yaml.setPlaceholderText("留空则使用权重内嵌结构")
        self.btn_model_yaml = QPushButton("浏览")
        self.btn_model_yaml.clicked.connect(lambda: self._browse_file(self.line_model_yaml, "*.yaml"))
        model_cfg_layout.addWidget(self.line_model_yaml)
        model_cfg_layout.addWidget(self.btn_model_yaml)
        form_layout.addLayout(model_cfg_layout)
        
        # Weights
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(QLabel("基础权重 (.pt):"))
        self.line_base_pt = QLineEdit()
        self.btn_pt = QPushButton("浏览")
        self.btn_pt.clicked.connect(lambda: self._browse_file(self.line_base_pt, "*.pt"))
        weight_layout.addWidget(self.line_base_pt)
        weight_layout.addWidget(self.btn_pt)
        form_layout.addLayout(weight_layout)
        
        # Params
        param_layout = QHBoxLayout()
        
        param_layout.addWidget(QLabel("Epochs:"))
        self.spin_epochs = QSpinBox()
        self.spin_epochs.setRange(1, 1000)
        self.spin_epochs.setValue(100)
        param_layout.addWidget(self.spin_epochs)
        
        param_layout.addWidget(QLabel("Batch:"))
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(1, 128)
        self.spin_batch.setValue(16)
        param_layout.addWidget(self.spin_batch)
        
        param_layout.addWidget(QLabel("LR:"))
        self.spin_lr = QDoubleSpinBox()
        self.spin_lr.setRange(0.0001, 0.1)
        self.spin_lr.setSingleStep(0.001)
        self.spin_lr.setDecimals(4)
        self.spin_lr.setValue(0.005)
        param_layout.addWidget(self.spin_lr)

        # Repeat Count (New)
        param_layout.addWidget(QLabel("Repeat:"))
        self.spin_repeat = QSpinBox()
        self.spin_repeat.setRange(1, 50)
        self.spin_repeat.setValue(5)
        self.spin_repeat.setToolTip("新数据重复加权次数")
        param_layout.addWidget(self.spin_repeat)
        
        form_layout.addLayout(param_layout)
        config_group.setLayout(form_layout)
        
        # 操作区
        action_layout = QVBoxLayout()
        self.btn_start_train = QPushButton("🚀 开始增量训练 (Start Fine-tuning)")
        self.btn_start_train.setMinimumHeight(50)
        self.btn_start_train.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #2196F3; color: white;")
        self.btn_start_train.clicked.connect(self._start_training)
        
        self.progress_train = QProgressBar()
        self.log_train = QTextEdit()
        self.log_train.setReadOnly(True)
        
        action_layout.addWidget(self.btn_start_train)
        action_layout.addWidget(self.progress_train)
        action_layout.addWidget(QLabel("训练日志:"))
        action_layout.addWidget(self.log_train)
        
        layout.addWidget(config_group)
        layout.addLayout(action_layout)
        
        return widget

    def _browse_file(self, line_edit, filter):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filter)
        if path:
            line_edit.setText(path)

    def _start_training(self):
        orig_yaml = self.line_orig_yaml.text()
        weight_path = self.line_base_pt.text()
        model_config = self.line_model_yaml.text().strip() # New
        repeat_count = self.spin_repeat.value() # New
        
        if not os.path.exists(orig_yaml):
            QMessageBox.warning(self, "错误", "请选择有效的原始数据集 YAML 文件")
            return
        if not os.path.exists(weight_path):
            QMessageBox.warning(self, "错误", "请选择有效的基础权重文件")
            return
            
        # 1. 准备数据集
        self.log_train.append(f"🛠️ 正在生成微调数据集配置 (新数据重复 {repeat_count} 次)...")
        try:
            output_dir = os.path.join(os.path.dirname(orig_yaml), "finetune_mix")
            # Pass repeat_count
            new_yaml = prepare_finetune_dataset(orig_yaml, self.verified_dir, output_dir, repeat_count)
            self.log_train.append(f"✅ 数据集准备就绪: {new_yaml}")
        except Exception as e:
            self.log_train.append(f"❌ 数据集准备失败: {e}")
            return
            
        # 2. 启动线程
        self.train_thread = TrainingThread(
            new_yaml, weight_path, 
            self.spin_epochs.value(),
            self.spin_batch.value(),
            self.spin_lr.value(),
            model_config # Pass model config
        )
        self.train_thread.log_signal.connect(self.log_train.append)
        self.train_thread.progress_signal.connect(self.progress_train.setValue)
        self.train_thread.finished_signal.connect(self._on_train_finished)
        
        self.btn_start_train.setEnabled(False)
        self.train_thread.start()

    def _on_train_finished(self, best_pt):
        self.btn_start_train.setEnabled(True)
        QMessageBox.information(self, "训练完成", f"新模型已保存至:\n{best_pt}\n请在主界面加载新模型进行测试。")

import numpy as np # Canvas logic needs numpy
