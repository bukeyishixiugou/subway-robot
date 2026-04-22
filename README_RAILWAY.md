# 地铁轨道病害检测系统

基于 PySide6 + OpenCV 的 MVC 架构检测系统。

## 功能特性

- 🎬 **多源输入**: 支持图片、视频文件、摄像头实时流
- 🔍 **智能检测**: 基于 YOLO 的病害检测（可扩展）
- 📊 **数据管理**: SQLite 数据库存储检测记录
- 🎨 **现代化 UI**: 使用 qt-material 主题美化
- ⚡ **多线程处理**: 使用 QThread 防止界面卡顿
- 📈 **实时显示**: FPS、里程位置、检测结果实时更新

## 项目结构

```
VisualTool/
├── railway_main.py              # 程序入口
├── app/
│   ├── models/                  # 数据模型层
│   │   └── database_manager.py  # 数据库管理
│   ├── core/                    # 核心逻辑层
│   │   ├── image_processor.py   # 图像处理算法
│   │   └── video_thread.py     # 视频处理线程
│   └── ui/                      # 界面层
│       └── railway_main_window.py  # 主窗口
└── requirements.txt
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行程序

```bash
python railway_main.py
```

## UI 布局说明

### 左侧控制区
- **输入源**: 打开图片/视频/摄像头
- **参数设置**: 
  - 模型类型选择（YOLOv8-Rail, OpticalFlow-Track, Custom）
  - 权重文件路径
  - 置信度阈值滑块（0.0-1.0）
- **控制按钮**: 开始/暂停/停止检测

### 中间显示区
- 视频帧实时显示（支持自适应缩放）
- 叠加显示 FPS 和里程信息

### 右侧数据区
- **上部**: 病害检测列表表格
  - 列：ID, 帧号, 病害类型, 置信度, 里程位置
  - 双击行可跳转（预留功能）
- **下部**: 统计图表占位符（预留饼图等）

### 底部状态区
- 处理进度条
- 系统日志控制台

## 核心类说明

### DatabaseManager
- 管理 SQLite 数据库
- 创建任务和检测记录表
- 提供数据插入和查询接口

### ImageProcessor
- 封装检测算法（YOLO、光流法等）
- 图像绘制和 FPS 计算
- 里程位置模拟计算

### VideoThread (QThread)
- 多线程视频处理
- 信号机制与 UI 通信
- 支持暂停/恢复/停止

### RailwayMainWindow
- 主窗口 UI 布局
- 信号槽连接
- 业务逻辑协调

## 使用流程

1. **选择输入源**: 点击"打开图片/视频/摄像头"
2. **设置参数**: 选择模型类型、权重文件、置信度阈值
3. **开始检测**: 点击"开始检测"按钮
4. **查看结果**: 在右侧表格查看检测到的病害
5. **停止检测**: 点击"停止"按钮结束任务

## 数据库结构

### tasks 表
- task_id: 任务ID
- source_type: 源类型
- source_path: 源路径
- model_name: 模型名称
- model_path: 模型路径
- conf_threshold: 置信度阈值
- status: 任务状态

### detection_records 表
- id: 记录ID
- task_id: 关联任务ID
- frame_index: 帧索引
- defect_type: 病害类型
- confidence: 置信度
- timestamp: 时间戳
- mileage: 里程位置
- bbox_x/y/w/h: 边界框坐标

## 扩展开发

### 集成真实 YOLO 模型

在 `ImageProcessor.detect_yolo()` 方法中：

```python
from ultralytics import YOLO

def detect_yolo(self, frame, conf_threshold=0.5):
    if self.model is None:
        self.model = YOLO(self.model_path)
    
    results = self.model.predict(frame, conf=conf_threshold, verbose=False)
    detections = []
    for result in results:
        boxes = result.boxes
        for box in boxes:
            detections.append({
                'type': self.model.names[int(box.cls)],
                'confidence': float(box.conf),
                'bbox': box.xywh[0].tolist()
            })
    return detections
```

### 添加统计图表

在 `RailwayMainWindow._create_right_panel()` 中集成 matplotlib：

```python
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import matplotlib.pyplot as plt

# 创建饼图
fig, ax = plt.subplots()
# ... 绘制逻辑
canvas = FigureCanvasQTAgg(fig)
chart_layout.addWidget(canvas)
```

## 故障排除

### PySide6 DLL 加载失败
参考 `解决方案.md` 或 `必须安装VC++运行时.txt`

### 摄像头无法打开
- 检查摄像头是否被其他程序占用
- 尝试修改摄像头ID（0, 1, 2...）

### 模型加载失败
- 检查权重文件路径是否正确
- 确认模型格式支持（.pt, .onnx, .pth）

## 许可证

本项目基于 MVC 架构设计，代码结构清晰，易于扩展。
