"""
图像处理类 - 通用 YOLO 模型适配器
支持任意在该环境下训练的 .pt 权重，不针对特定架构硬编码。
"""
import cv2
import numpy as np
import time
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image, ImageDraw, ImageFont


# 通用错误提示（不出现具体模块名）
LOAD_ERROR_MSG = (
    "加载失败：当前环境缺少模型所需的自定义模块定义，"
    "请确保运行环境与训练环境代码一致。"
)


class ImageProcessor:
    """图像处理器 - 通用 YOLO 模型适配器"""

    def __init__(self, model_path: Optional[str] = None, model_type: str = "Loaded Weights"):
        """
        初始化图像处理器

        Args:
            model_path: 模型文件路径（.pt 等）
            model_type: 显示用类型，如 "Loaded Weights" / "Custom Model"，不涉及具体结构名
        """
        self.model_path = model_path
        self.model_type = model_type
        self.model: Any = None
        self.fps_counter: List[float] = []
        self.last_fps_time = time.time()
        self.fps = 0.0

        # 1. 定义中文映射
        self.class_map = {
            0: '掉块',
            1: '暗斑(擦伤)',
            2: '轨道小凹陷',
            3: '横向大裂缝',
            4: '局部凹陷',
            5: '横向巨大凹陷',
            6: '剥离裂纹',
            7: '波磨'
        }
        
        # 2. 定义颜色表 (R, G, B)
        self.colors = [
            (255, 0, 0),    # 0: 红
            (255, 165, 0),  # 1: 橙
            (255, 255, 0),  # 2: 黄
            (0, 255, 0),    # 3: 绿
            (0, 255, 255),  # 4: 青
            (0, 0, 255),    # 5: 蓝
            (128, 0, 128),  # 6: 紫
            (255, 192, 203) # 7: 粉
        ]
        
        # 3. 加载字体
        try:
            # 优先尝试微软雅黑 (Windows)
            self.font = ImageFont.truetype("msyh.ttc", 22)
        except IOError:
            try:
                # 尝试黑体
                self.font = ImageFont.truetype("simhei.ttf", 22)
            except IOError:
                print("⚠️ 未找到中文字体，将使用默认字体 (中文可能乱码)")
                self.font = ImageFont.load_default()

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str, config_path: Optional[str] = None) -> bool:
        """
        通用加载逻辑：使用 YOLO(model_path) 加载任意在该环境下训练的权重。

        Args:
            model_path: 模型文件路径（.pt 等）
            config_path: 可选，模型配置文件路径（.yaml），仅用于记录或特殊加载

        Returns:
            bool: 是否加载成功
        """
        self.model_path = model_path
        self.model = None

        try:
            from ultralytics import YOLO
            
            # 优先加载权重文件
            load_target = model_path
            
            # 如果指定了配置文件，虽然 standard YOLO(pt) 包含了 config，
            # 但这里我们打印出来确认用户意图
            if config_path:
                print(f"ℹ️ 指定了模型配置: {config_path}")
                # 注意：通常 YOLO(pt) 不需要 yaml，除非是在定义新模型。
                # 如果用户意图是用 yaml 构建结构再 load weights (非标准用法)，
                # 这里还是建议直接 load pt，因为 pt 包含了结构。
            
            self.model = YOLO(load_target)
            print(f"✅ 模型加载成功: {load_target}")
            return True
        except (AttributeError, ModuleNotFoundError) as e:
            print(LOAD_ERROR_MSG)
            return False
        except Exception as e:
            print(f"加载失败：{e}")
            return False

    def is_model_loaded(self) -> bool:
        """是否已成功加载可推理的模型"""
        return self.model is not None

    def process_frame(
        self, frame: np.ndarray, conf: float = 0.5
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        通用推理逻辑：单帧推理，返回可视化图像与检测框数据。
        使用 PIL 绘制中文标签。
        """
        if self.model is None:
            return frame.copy(), []

        try:
            results = self.model(frame, conf=conf, verbose=False)
        except Exception as e:
            print(f"推理异常: {e}")
            return frame.copy(), []

        if not results or len(results) == 0:
            return frame.copy(), []

        r0 = results[0]
        detections: List[Dict] = []
        
        # 准备 PIL 绘图
        # OpenCV 是 BGR，PIL 需要 RGB
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            draw = ImageDraw.Draw(pil_img)
        except Exception:
            return frame.copy(), []

        # 仅当存在 boxes 且为检测任务时解析框
        try:
            boxes = getattr(r0, "boxes", None)
            if boxes is not None and hasattr(boxes, "__len__") and len(boxes) > 0:
                
                # 解析 Boxes
                xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy
                conf_vals = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else boxes.conf
                cls_vals = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else boxes.cls
                
                for i in range(len(boxes)):
                    x1, y1, x2, y2 = map(int, xyxy[i])
                    confidence = float(conf_vals[i])
                    class_id = int(cls_vals[i])
                    
                    # 获取中文标签
                    class_name = self.class_map.get(class_id, str(class_id))
                    display_text = f"{class_name} {confidence:.2f}"
                    
                    # 获取颜色
                    color = self.colors[class_id % len(self.colors)]
                    
                    # 1. 画框
                    draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
                    
                    # 2. 画文字背景 (计算文字大小)
                    try:
                        text_bbox = draw.textbbox((x1, y1), display_text, font=self.font)
                        # text_bbox 是 (left, top, right, bottom)，稍微把背景画大一点
                        # 注意：textbbox 返回相对于图片左上角的坐标，但这里传入的 xy 已经是绝对坐标
                        # 如果文字在框上方放不下，就放到框内
                        text_h = text_bbox[3] - text_bbox[1]
                        if y1 - text_h - 4 < 0:
                            # 放在框内左上角
                            text_pos = (x1, y1)
                            bg_box = [text_bbox[0]-2, text_bbox[1]-2, text_bbox[2]+2, text_bbox[3]+2]
                        else:
                            # 放在框上方
                            text_pos = (x1, y1 - text_h - 4)
                            # 重新计算 bbox
                            text_bbox = draw.textbbox(text_pos, display_text, font=self.font)
                            bg_box = [text_bbox[0]-2, text_bbox[1]-2, text_bbox[2]+2, text_bbox[3]+2]

                        draw.rectangle(bg_box, fill=color)
                        draw.text(text_pos, display_text, font=self.font, fill=(255, 255, 255))
                    except AttributeError:
                        # 旧版 Pillow 可能没有 textbbox，使用 textsize
                        # 简单回退处理
                        draw.text((x1, y1), display_text, font=self.font, fill=color)

                    # 3. 收集检测结果
                    w = x2 - x1
                    h = y2 - y1
                    detections.append({
                        "type": class_name, # 使用中文名称
                        "confidence": confidence,
                        "bbox": (float(x1), float(y1), float(w), float(h))
                    })

        except (AttributeError, TypeError, IndexError) as e:
            pass

        # 转回 OpenCV (PIL -> OpenCV)
        vis_image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        
        return vis_image, detections

    def detect_yolo(self, frame: np.ndarray, conf_threshold: float = 0.5) -> List[Dict]:
        """
        兼容旧接口：返回检测列表，格式与原有 draw_detections / 表格一致。
        若已加载模型则走 process_frame；否则返回空列表（不再用随机占位）。
        """
        if self.model is not None:
            _, detections = self.process_frame(frame, conf=conf_threshold)
            return detections
        return []

    def get_processed_frame(
        self, frame: np.ndarray, conf_threshold: float = 0.5
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        一次调用得到「可视化图 + 检测列表」，供 UI 直接使用。
        已加载模型时用 plot() 图；未加载时用原图 + draw_detections(空列表)。
        """
        if self.model is not None:
            return self.process_frame(frame, conf=conf_threshold)
        detections = self.detect_yolo(frame, conf_threshold)
        vis_image = self.draw_detections(frame, detections)
        return vis_image, detections

    def track_optical_flow(
        self, frame: np.ndarray, prev_frame: Optional[np.ndarray] = None
    ) -> Dict:
        """光流法跟踪（占位，保留接口）"""
        return {"flow_magnitude": 0.0, "tracking_points": []}

    def draw_detections(
        self, frame: np.ndarray, detections: List[Dict]
    ) -> np.ndarray:
        """
        在图像上绘制检测结果（未加载模型或需二次绘制时使用）
        """
        result_frame = frame.copy()
        for det in detections:
            bbox = det.get("bbox", (0, 0, 0, 0))
            defect_type = det.get("type", "Unknown")
            confidence = det.get("confidence", 0.0)
            
            if len(bbox) >= 4:
                x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
            else:
                x, y, w, h = 0, 0, 0, 0
                
            x, y, w, h = int(x), int(y), int(w), int(h)
            if w <= 0 or h <= 0:
                continue

            color = (0, 255, 0) if confidence > 0.7 else (0, 165, 255)
            cv2.rectangle(result_frame, (x, y), (x + w, y + h), color, 2)
            
            label = f"{defect_type}: {confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(
                result_frame,
                (x, y - th - 10),
                (x + tw, y),
                color,
                -1,
            )
            cv2.putText(
                result_frame,
                label,
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
        return result_frame

    def calculate_fps(self) -> float:
        """计算并返回当前 FPS"""
        current_time = time.time()
        self.fps_counter.append(current_time)
        # 仅保留最近 1 秒内的帧时间戳
        self.fps_counter = [t for t in self.fps_counter if current_time - t < 1.0]
        
        if len(self.fps_counter) > 1:
            self.fps = len(self.fps_counter) / (self.fps_counter[-1] - self.fps_counter[0])
        else:
            self.fps = 0.0
        return self.fps

    def calculate_mileage(
        self,
        frame_index: int,
        fps: float = 30.0,
        base_mileage: str = "K120+000",
    ) -> str:
        """计算模拟里程位置"""
        # 假设每帧前进 0.1 米（根据实际视频速度调整）
        distance_per_frame = 0.1
        total_distance = frame_index * distance_per_frame
        
        try:
            # 解析 K120+000 格式
            k_part, m_part = base_mileage.split("+")
            k_num = int(k_part[1:])
            m_num = float(m_part)
            
            new_m = m_num + total_distance / 1000.0 # 这里的逻辑有点问题，total_distance如果是米，m_part通常是米
            # 假设格式是 K公里+米
            
            # 修正逻辑：total_distance 是米
            new_total_meters = m_num + total_distance
            
            while new_total_meters >= 1000:
                k_num += 1
                new_total_meters -= 1000
                
            return f"K{k_num}+{int(new_total_meters):03d}"
        except Exception:
            return base_mileage
