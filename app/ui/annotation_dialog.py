"""
人工修正标注对话框
支持手动绘制检测框、删除检测框，并保存为 YOLO 格式数据。
"""
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QScrollArea, QMessageBox, QWidget
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QMouseEvent, QBrush
from PySide6.QtCore import Qt, Signal, QPoint, QRect

# 类别映射
CLASS_MAP = {
    0: '掉块',
    1: '暗斑(擦伤)',
    2: '轨道小凹陷',
    3: '横向大裂缝',
    4: '局部凹陷',
    5: '横向巨大凹陷',
    6: '剥离裂纹',
    7: '波磨'
}
# 反向映射：中文 -> ID
NAME_TO_ID = {v: k for k, v in CLASS_MAP.items()}

# 颜色表 (与 ImageProcessor 保持一致)
COLORS = [
    (255, 0, 0),    # 0: 红
    (255, 165, 0),  # 1: 橙
    (255, 255, 0),  # 2: 黄
    (0, 255, 0),    # 3: 绿
    (0, 255, 255),  # 4: 青
    (0, 0, 255),    # 5: 蓝
    (128, 0, 128),  # 6: 紫
    (255, 192, 203) # 7: 粉
]

class CanvasLabel(QLabel):
    """自定义画布标签，支持鼠标绘制和删除框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.img_pixmap = None
        self.scale_factor = 1.0
        
        # 数据存储
        # boxes 结构: [{'class_id': int, 'rect': QRect(x, y, w, h)}, ...] 坐标为真实图片坐标
        self.boxes = []
        
        # 交互状态
        self.current_class_id = 0
        self.drawing = False
        self.start_point = QPoint()
        self.current_rect = QRect() # 绘制过程中的临时框 (真实坐标)

    def set_image(self, cv_image):
        """设置显示的图片"""
        self.cv_image = cv_image
        h, w, ch = cv_image.shape
        bytes_per_line = ch * w
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.img_pixmap = QPixmap.fromImage(qt_image)
        self.update_display()

    def set_boxes(self, boxes):
        """设置初始框"""
        self.boxes = boxes
        self.update()

    def set_current_class(self, class_id):
        self.current_class_id = class_id

    def update_display(self):
        """根据当前控件大小更新显示缩放"""
        if self.img_pixmap:
            # 简单的自适应缩放，保持比例
            scaled = self.img_pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            super().setPixmap(scaled)
            
            # 计算缩放比例
            if scaled.width() > 0:
                self.scale_factor = self.img_pixmap.width() / scaled.width()
            else:
                self.scale_factor = 1.0

            # 居中显示的偏移量 (如果QLabel比图片大)
            self.offset_x = (self.width() - scaled.width()) / 2
            self.offset_y = (self.height() - scaled.height()) / 2
        else:
            self.scale_factor = 1.0
            self.offset_x = 0
            self.offset_y = 0

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)

    def _map_to_image(self, widget_pos: QPoint) -> QPoint:
        """将控件坐标映射回真实图片坐标"""
        x = (widget_pos.x() - self.offset_x) * self.scale_factor
        y = (widget_pos.y() - self.offset_y) * self.scale_factor
        # 边界限制
        if self.img_pixmap:
            x = max(0, min(x, self.img_pixmap.width()))
            y = max(0, min(y, self.img_pixmap.height()))
        return QPoint(int(x), int(y))

    def _map_to_widget(self, image_rect: QRect) -> QRect:
        """将真实图片坐标映射到控件坐标用于绘制"""
        x = image_rect.x() / self.scale_factor + self.offset_x
        y = image_rect.y() / self.scale_factor + self.offset_y
        w = image_rect.width() / self.scale_factor
        h = image_rect.height() / self.scale_factor
        return QRect(int(x), int(y), int(w), int(h))

    def mousePressEvent(self, event: QMouseEvent):
        if not self.img_pixmap:
            return

        img_pos = self._map_to_image(event.pos())

        if event.button() == Qt.MouseButton.LeftButton:
            # 开始绘制
            self.drawing = True
            self.start_point = img_pos
            self.current_rect = QRect(img_pos, img_pos)
            
        elif event.button() == Qt.MouseButton.RightButton:
            # 删除框：查找包含点击点的框，删除最上面的一个
            for i in range(len(self.boxes) - 1, -1, -1):
                box = self.boxes[i]
                if box['rect'].contains(img_pos):
                    self.boxes.pop(i)
                    self.update()
                    break

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing and self.img_pixmap:
            img_pos = self._map_to_image(event.pos())
            self.current_rect = QRect(self.start_point, img_pos).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            # 只有当框有一定大小时才添加
            if self.current_rect.width() > 5 and self.current_rect.height() > 5:
                self.boxes.append({
                    'class_id': self.current_class_id,
                    'rect': self.current_rect
                })
            self.current_rect = QRect()
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event) # 绘制底图 QLabel 的内容
        
        if not self.img_pixmap:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. 绘制已有的框
        for box in self.boxes:
            rect = box['rect']
            cls_id = box['class_id']
            widget_rect = self._map_to_widget(rect)
            
            # 获取颜色
            color_rgb = COLORS[cls_id % len(COLORS)]
            color = QColor(*color_rgb)
            
            pen = QPen(color, 2)
            painter.setPen(pen)
            # 填充半透明颜色
            brush = QBrush(color)
            color.setAlpha(50)
            painter.setBrush(brush)
            
            painter.drawRect(widget_rect)
            
            # 绘制标签背景和文字
            label_text = CLASS_MAP.get(cls_id, str(cls_id))
            
            # 文字背景
            font_metrics = painter.fontMetrics()
            text_width = font_metrics.horizontalAdvance(label_text)
            text_height = font_metrics.height()
            
            text_rect = QRect(widget_rect.x(), widget_rect.y() - text_height, text_width + 4, text_height)
            if text_rect.top() < 0: # 如果超出上边界，显示在框内
                text_rect.moveTop(widget_rect.y())
            
            painter.fillRect(text_rect, color_rgb) # 实心背景
            painter.setPen(Qt.white)
            painter.drawText(text_rect, Qt.AlignCenter, label_text)

        # 2. 绘制正在拖拽的框
        if self.drawing:
            widget_rect = self._map_to_widget(self.current_rect)
            color_rgb = COLORS[self.current_class_id % len(COLORS)]
            color = QColor(*color_rgb)
            pen = QPen(color, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(widget_rect)


class AnnotationDialog(QDialog):
    """人工修正对话框"""
    def __init__(self, parent, cv_image, detections):
        """
        Args:
            cv_image: OpenCV BGR 图像
            detections: 检测结果列表 [{'type': '中文名', 'bbox': (x,y,w,h)}, ...]
        """
        super().__init__(parent)
        self.setWindowTitle("🛠️ 人工修正与反馈")
        self.resize(1000, 700)
        self.cv_image = cv_image
        
        # 布局
        layout = QVBoxLayout(self)
        
        # === 工具栏 ===
        toolbar = QHBoxLayout()
        
        toolbar.addWidget(QLabel("选择当前绘制类别:"))
        self.combo_class = QComboBox()
        for i in range(8):
            self.combo_class.addItem(f"{i}: {CLASS_MAP[i]}", i)
        self.combo_class.currentIndexChanged.connect(self._on_class_changed)
        toolbar.addWidget(self.combo_class)
        
        toolbar.addStretch()
        
        help_label = QLabel("操作提示: 左键拖动绘制 | 右键点击删除 | 滚轮缩放(暂不支持)")
        help_label.setStyleSheet("color: gray;")
        toolbar.addWidget(help_label)
        
        layout.addLayout(toolbar)
        
        # === 显示区域 ===
        # 使用 ScrollArea 包裹 CanvasLabel 以支持大图查看 (这里简化为自适应，如需精细操作可改为固定大小+滚动)
        self.canvas = CanvasLabel()
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
        self.canvas.setMinimumSize(640, 480) # 最小尺寸
        
        layout.addWidget(self.canvas, 1) # 伸缩因子1，占据主要空间
        
        # === 底部按钮 ===
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("💾 保存修正数据")
        self.btn_save.clicked.connect(self.accept) # Dialog accept -> save logic external or internal? Let's do internal returns
        self.btn_save.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 15px;")
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        
        # === 初始化数据 ===
        self.canvas.set_image(self.cv_image)
        self._init_boxes(detections)
        
    def _init_boxes(self, detections):
        """将传入的检测结果转换为编辑器格式"""
        boxes = []
        for det in detections:
            bbox = det.get('bbox') # [x, y, w, h]
            type_name = det.get('type')
            
            if bbox and type_name:
                x, y, w, h = bbox
                # 转换回 class_id
                class_id = NAME_TO_ID.get(type_name, 0) # 默认 0
                
                rect = QRect(int(x), int(y), int(w), int(h))
                boxes.append({
                    'class_id': class_id,
                    'rect': rect
                })
        self.canvas.set_boxes(boxes)

    def _on_class_changed(self, index):
        class_id = self.combo_class.currentData()
        self.canvas.set_current_class(class_id)
        
    def get_yolo_data(self):
        """
        获取 YOLO 格式的标注数据
        Returns:
            list of strings: ["class_id x_center y_center w h", ...]
        """
        h_img, w_img = self.cv_image.shape[:2]
        lines = []
        
        for box in self.canvas.boxes:
            rect = box['rect']
            cls_id = box['class_id']
            
            # 归一化坐标计算
            # 确保在图像范围内
            x1 = max(0, rect.left())
            y1 = max(0, rect.top())
            x2 = min(w_img, rect.right())
            y2 = min(h_img, rect.bottom())
            
            # 计算宽高 (rect.right() 是包含的，所以宽度是 right-left+1? YOLO通常视为连续坐标)
            # 在OpenCV/YOLO中，通常宽是 x2-x1
            box_w = x2 - x1
            box_h = y2 - y1
            
            if box_w <= 0 or box_h <= 0:
                continue
            
            # 中心点
            x_center = (x1 + box_w / 2.0) / w_img
            y_center = (y1 + box_h / 2.0) / h_img
            w_norm = box_w / w_img
            h_norm = box_h / h_img
            
            # 格式化: class x y w h (保留6位小数)
            line = f"{cls_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}"
            lines.append(line)
            
        return lines

    def get_result_image(self):
        """返回当前的图像（不带框，因为是原图）"""
        return self.cv_image
