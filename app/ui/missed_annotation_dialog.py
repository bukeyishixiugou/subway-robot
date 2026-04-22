"""
漏检补录对话框
用于人工框选漏检的病害目标，并保存为 YOLO 格式。
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

# 颜色表
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

class MissedCanvasLabel(QLabel):
    """自定义画布，用于绘制新框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.img_pixmap = None
        self.scale_factor = 1.0
        
        # 存储新画的框: [{'class_id': int, 'rect': QRect}] (真实坐标)
        self.new_boxes = []
        
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

    def set_current_class(self, class_id):
        self.current_class_id = class_id

    def update_display(self):
        """根据当前控件大小更新显示缩放"""
        if self.img_pixmap:
            # 自适应缩放
            scaled = self.img_pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            super().setPixmap(scaled)
            
            # 计算缩放比例 (真实宽度 / 显示宽度)
            if scaled.width() > 0:
                self.scale_factor = self.img_pixmap.width() / scaled.width()
            else:
                self.scale_factor = 1.0

            # 居中显示的偏移量
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
        """控件坐标 -> 真实图片坐标"""
        x = (widget_pos.x() - self.offset_x) * self.scale_factor
        y = (widget_pos.y() - self.offset_y) * self.scale_factor
        # 边界限制
        if self.img_pixmap:
            x = max(0, min(x, self.img_pixmap.width()))
            y = max(0, min(y, self.img_pixmap.height()))
        return QPoint(int(x), int(y))

    def _map_to_widget(self, image_rect: QRect) -> QRect:
        """真实图片坐标 -> 控件坐标"""
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
            # 右键删除最近一个框（或者点击删除，这里实现点击删除）
            for i in range(len(self.new_boxes) - 1, -1, -1):
                box = self.new_boxes[i]
                if box['rect'].contains(img_pos):
                    self.new_boxes.pop(i)
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
            if self.current_rect.width() > 5 and self.current_rect.height() > 5:
                self.new_boxes.append({
                    'class_id': self.current_class_id,
                    'rect': self.current_rect
                })
            self.current_rect = QRect()
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        
        if not self.img_pixmap:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制已确认的框
        for box in self.new_boxes:
            rect = box['rect']
            cls_id = box['class_id']
            widget_rect = self._map_to_widget(rect)
            
            color_rgb = COLORS[cls_id % len(COLORS)]
            color = QColor(*color_rgb)
            
            pen = QPen(color, 2)
            painter.setPen(pen)
            brush = QBrush(color)
            color.setAlpha(50)
            painter.setBrush(brush)
            painter.drawRect(widget_rect)
            
            # 绘制标签
            label_text = CLASS_MAP.get(cls_id, str(cls_id))
            painter.setPen(Qt.white)
            # 简单绘制在框上方
            painter.drawText(widget_rect.x(), widget_rect.y() - 5, label_text)

        # 绘制正在拖拽的框
        if self.drawing:
            widget_rect = self._map_to_widget(self.current_rect)
            color_rgb = COLORS[self.current_class_id % len(COLORS)]
            color = QColor(*color_rgb)
            pen = QPen(color, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(widget_rect)


class MissedAnnotationDialog(QDialog):
    """漏检补录对话框"""
    def __init__(self, parent, cv_image):
        super().__init__(parent)
        self.setWindowTitle("✏️ 漏检补录 (Missed Detection)")
        self.resize(1000, 700)
        self.cv_image = cv_image
        
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("当前补录类别:"))
        self.combo_class = QComboBox()
        for i in range(8):
            self.combo_class.addItem(f"{i}: {CLASS_MAP[i]}", i)
        self.combo_class.currentIndexChanged.connect(self._on_class_changed)
        toolbar.addWidget(self.combo_class)
        
        toolbar.addStretch()
        toolbar.addWidget(QLabel("提示: 鼠标左键画框，右键删除"))
        
        layout.addLayout(toolbar)
        
        # 画布
        self.canvas = MissedCanvasLabel()
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setStyleSheet("background-color: #2b2b2b;")
        self.canvas.setMinimumSize(640, 480)
        layout.addWidget(self.canvas, 1)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("💾 保存补录数据")
        self.btn_save.clicked.connect(self.accept)
        self.btn_save.setStyleSheet("background-color: #007bff; color: white; padding: 5px 15px;")
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        
        # 初始化
        self.canvas.set_image(self.cv_image)

    def _on_class_changed(self, index):
        class_id = self.combo_class.currentData()
        if class_id is None:
            class_id = 0
        self.canvas.set_current_class(class_id)
        
        # [UX Fix] 如果刚刚画了一个框（new_boxes非空），且用户紧接着修改了类别
        # 很有可能是想修改刚才那个框的类别。
        # 我们简单判断：如果 new_boxes 不为空，更新最后一个框的类别
        if self.canvas.new_boxes:
            self.canvas.new_boxes[-1]['class_id'] = class_id
            self.canvas.update()
        
    def get_yolo_data(self):
        """获取用户新画的框 (YOLO格式)"""
        h_img, w_img = self.cv_image.shape[:2]
        lines = []
        
        for box in self.canvas.new_boxes:
            rect = box['rect']
            cls_id = box['class_id']
            
            x1 = max(0, rect.left())
            y1 = max(0, rect.top())
            x2 = min(w_img, rect.right())
            y2 = min(h_img, rect.bottom())
            
            box_w = x2 - x1
            box_h = y2 - y1
            
            if box_w <= 0 or box_h <= 0:
                continue
            
            x_center = (x1 + box_w / 2.0) / w_img
            y_center = (y1 + box_h / 2.0) / h_img
            w_norm = box_w / w_img
            h_norm = box_h / h_img
            
            line = f"{cls_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}"
            lines.append(line)
            
        return lines
