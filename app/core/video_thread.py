"""
视频处理线程类 - 负责视频流读取和处理
"""
import os
import shutil
import tempfile

import cv2
import numpy as np
from PySide6.QtCore import QMutex, QThread, Signal
from PySide6.QtGui import QImage
from typing import Optional
import time
from app.core.image_processor import ImageProcessor


class VideoThread(QThread):
    """视频处理线程 - 使用 QThread 防止界面卡死"""
    
    # 信号定义
    change_pixmap_signal = Signal(QImage)  # 发送处理后的图像
    update_table_signal = Signal(dict)  # 发送检测数据
    update_log_signal = Signal(str)  # 发送日志
    update_progress_signal = Signal(int)  # 发送进度 (0-100)
    finished_signal = Signal()  # 处理完成信号
    
    def __init__(self, source_type: str, source_path: str = None,
                 processor: ImageProcessor = None, conf_threshold: float = 0.5):
        """
        初始化视频线程
        
        Args:
            source_type: 源类型 ("image", "video", "camera")
            source_path: 源路径（图片/视频文件路径，或摄像头ID）
            processor: 图像处理器实例
            conf_threshold: 置信度阈值
        """
        super().__init__()
        self.source_type = source_type
        self.source_path = source_path
        self.processor = processor or ImageProcessor()
        self.conf_threshold = conf_threshold
        
        self.is_running = False
        self.is_paused = False
        self.mutex = QMutex()
        self.target_frame_index: Optional[int] = None # 跳转目标帧
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame_index = 0
        self.total_frames = 0
        self.current_frame: Optional[np.ndarray] = None
        self.prev_frame: Optional[np.ndarray] = None
        self._temp_video_dir: Optional[str] = None
    
    def seek(self, frame_index: int):
        """跳转到指定帧"""
        if self.source_type not in ["video", "dataset"]:
            return
            
        self.mutex.lock()
        self.target_frame_index = max(0, frame_index)
        self.mutex.unlock()
        self.update_log_signal.emit(f"[跳转] 正在跳转到帧: {frame_index}")
        
    def run(self):
        """线程主函数"""
        self.is_running = True
        self.is_paused = False
        
        try:
            if self.source_type == "image":
                self._process_image()
            elif self.source_type == "video":
                self._process_video()
            elif self.source_type == "camera":
                self._process_camera()
            elif self.source_type == "dataset":
                self._process_dataset()
            else:
                self.update_log_signal.emit(f"[错误] 不支持的源类型: {self.source_type}")
        except Exception as e:
            self.update_log_signal.emit(f"[错误] 处理异常: {str(e)}")
        finally:
            self._cleanup()
            self.finished_signal.emit()
    
    def _process_image(self):
        """处理单张图片"""
        if not self.source_path:
            self.update_log_signal.emit("[错误] 图片路径为空")
            return
        
        self.update_log_signal.emit(f"[开始] 处理图片: {self.source_path}")

        # 兼容包含中文路径的图片读取
        try:
            img_array = np.fromfile(self.source_path, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        except Exception as e:
            frame = None
            self.update_log_signal.emit(f"[错误] 读取图片失败: {e}")
        
        if frame is None:
            self.update_log_signal.emit("[错误] 无法读取图片")
            return
        
        # 检测：已加载模型时用通用推理（plot 图 + 检测列表），否则用占位逻辑
        result_frame, detections = self.processor.get_processed_frame(
            frame, self.conf_threshold
        )
        
        # 计算 FPS 和里程
        fps = self.processor.calculate_fps()
        mileage = self.processor.calculate_mileage(0)
        
        # 添加信息叠加
        result_frame = self._add_overlay(result_frame, fps, mileage)
        
        # 转换为 QImage 并发送
        qimage = self._cv2_to_qimage(result_frame)
        self.change_pixmap_signal.emit(qimage)
        
        # 发送检测数据
        for det in detections:
            self.update_table_signal.emit({
                'frame_index': 0,
                'defect_type': det.get('type', 'Unknown'),
                'confidence': det.get('confidence', 0.0),
                'mileage': mileage,
                'bbox': det.get('bbox')
            })
        
        self.update_progress_signal.emit(100)
        self.update_log_signal.emit("[完成] 图片处理完成")
    
    def _process_video(self):
        """处理视频文件"""
        if not self.source_path:
            self.update_log_signal.emit("[错误] 视频路径为空")
            return
        
        open_path = self.source_path
        if not os.path.exists(open_path):
            self.update_log_signal.emit(f"[错误] 视频文件不存在: {open_path}")
            return

        # OpenCV 在某些环境下对包含中文的路径支持不佳，这里做一次临时复制到纯英文路径
        if any(ord(ch) > 127 for ch in open_path):
            try:
                self._temp_video_dir = tempfile.mkdtemp(prefix="rail_video_")
                _, ext = os.path.splitext(open_path)
                temp_path = os.path.join(self._temp_video_dir, f"input{ext or '.mp4'}")
                shutil.copy2(open_path, temp_path)
                self.update_log_signal.emit(f"[提示] 检测到中文路径，已复制视频到临时路径: {temp_path}")
                open_path = temp_path
            except Exception as e:
                self.update_log_signal.emit(f"[错误] 复制视频到临时路径失败: {e}")
                return

        self.cap = cv2.VideoCapture(open_path)
        if not self.cap.isOpened():
            self.update_log_signal.emit(f"[错误] 无法打开视频: {self.source_path}")
            return
        
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_video = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        self.update_log_signal.emit(f"[开始] 处理视频: {self.source_path} (总帧数: {self.total_frames})")
        
        self.frame_index = 0
        while self.is_running:
            # 处理跳转逻辑
            jumped = False
            if self.target_frame_index is not None:
                target = self.target_frame_index
                self.target_frame_index = None
                if target < self.total_frames:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                    self.frame_index = target
                    jumped = True
                else:
                    self.update_log_signal.emit(f"[错误] 跳转帧 {target} 超出范围")

            if self.is_paused and not jumped:
                time.sleep(0.1)
                continue
            
            ret, frame = self.cap.read()
            if not ret:
                break
            
            # 检测：已加载模型时用通用推理（plot 图 + 检测列表）
            result_frame, detections = self.processor.get_processed_frame(
                frame, self.conf_threshold
            )
            
            # 计算 FPS 和里程
            fps = self.processor.calculate_fps()
            mileage = self.processor.calculate_mileage(self.frame_index, fps_video)
            
            # 添加信息叠加
            result_frame = self._add_overlay(result_frame, fps, mileage)
            
            # 转换为 QImage 并发送
            qimage = self._cv2_to_qimage(result_frame)
            self.change_pixmap_signal.emit(qimage)
            
            # 发送检测数据
            for det in detections:
                self.update_table_signal.emit({
                    'frame_index': self.frame_index,
                    'defect_type': det.get('type', 'Unknown'),
                    'confidence': det.get('confidence', 0.0),
                    'mileage': mileage,
                    'bbox': det.get('bbox')
                })
            
            # 更新进度
            if self.total_frames > 0:
                progress = int((self.frame_index + 1) / self.total_frames * 100)
                self.update_progress_signal.emit(progress)
            
            self.frame_index += 1
            
            # 控制播放速度
            time.sleep(1.0 / fps_video)
        
        self.update_log_signal.emit("[完成] 视频处理完成")
    
    def _process_camera(self):
        """处理摄像头流"""
        camera_id = int(self.source_path) if self.source_path and self.source_path.isdigit() else 0
        
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            self.update_log_signal.emit(f"[错误] 无法打开摄像头: {camera_id}")
            return
        
        self.update_log_signal.emit(f"[开始] 处理摄像头流: {camera_id}")
        
        self.frame_index = 0
        while self.is_running:
            if self.is_paused:
                time.sleep(0.1)
                continue
            
            ret, frame = self.cap.read()
            if not ret:
                self.update_log_signal.emit("[警告] 无法读取摄像头帧")
                break
            
            # 检测：已加载模型时用通用推理（plot 图 + 检测列表）
            result_frame, detections = self.processor.get_processed_frame(
                frame, self.conf_threshold
            )
            
            # 计算 FPS 和里程
            fps = self.processor.calculate_fps()
            mileage = self.processor.calculate_mileage(self.frame_index)
            
            # 添加信息叠加
            result_frame = self._add_overlay(result_frame, fps, mileage)
            
            # 转换为 QImage 并发送
            qimage = self._cv2_to_qimage(result_frame)
            self.change_pixmap_signal.emit(qimage)
            
            # 发送检测数据
            for det in detections:
                self.update_table_signal.emit({
                    'frame_index': self.frame_index,
                    'defect_type': det.get('type', 'Unknown'),
                    'confidence': det.get('confidence', 0.0),
                    'mileage': mileage,
                    'bbox': det.get('bbox')
                })
            
            self.frame_index += 1
            
            # 控制帧率
            time.sleep(1.0 / 30.0)  # 假设 30 FPS
    
    def _process_dataset(self):
        """处理数据集文件夹（逐张图片处理）"""
        if not self.source_path or not os.path.exists(self.source_path):
            self.update_log_signal.emit(f"[错误] 数据集路径不存在: {self.source_path}")
            return
            
        # 扫描图片文件
        valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
        image_files = []
        try:
            for root, dirs, files in os.walk(self.source_path):
                for file in files:
                    if os.path.splitext(file)[1].lower() in valid_exts:
                        image_files.append(os.path.join(root, file))
        except Exception as e:
            self.update_log_signal.emit(f"[错误] 扫描数据集失败: {e}")
            return
            
        if not image_files:
            self.update_log_signal.emit("[警告] 数据集中未找到图片文件")
            return
            
        # 简单排序，尝试按文件名排序
        image_files.sort()
        self.total_frames = len(image_files)
        
        self.update_log_signal.emit(f"[开始] 处理数据集: {self.source_path} (共 {self.total_frames} 张图片)")
        
        self.frame_index = 0
        while self.is_running:
             # 处理跳转逻辑
            jumped = False
            if self.target_frame_index is not None:
                target = self.target_frame_index
                self.target_frame_index = None
                if target < len(image_files):
                    self.frame_index = target
                    jumped = True # 标记已跳转
                else:
                    self.update_log_signal.emit(f"[错误] 跳转帧 {target} 超出范围")

            if self.is_paused and not jumped: # 如果有跳转请求，暂不暂停
                time.sleep(0.1)
                continue
            
            # 边界检查
            if self.frame_index >= len(image_files):
                break

            img_path = image_files[self.frame_index]
            
            # 读取图片
            try:
                # 兼容中文路径
                img_array = np.fromfile(img_path, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if frame is None:
                    self.frame_index += 1
                    continue
            except Exception:
                self.frame_index += 1
                continue
                
            # 检测
            result_frame, detections = self.processor.get_processed_frame(
                frame, self.conf_threshold
            )
            
            # 计算 FPS (这里 FPS 意义是处理速度) 和里程
            fps = self.processor.calculate_fps()
            # 假设每张图片代表一帧的时间流逝，或者仅仅是序列
            mileage = self.processor.calculate_mileage(self.frame_index)
            
            # 添加信息叠加
            result_frame = self._add_overlay(result_frame, fps, mileage)
            
            # 转换为 QImage 并发送
            qimage = self._cv2_to_qimage(result_frame)
            self.change_pixmap_signal.emit(qimage)
            
            # 发送检测数据
            for det in detections:
                self.update_table_signal.emit({
                    'frame_index': self.frame_index,
                    'defect_type': det.get('type', 'Unknown'),
                    'confidence': det.get('confidence', 0.0),
                    'mileage': mileage,
                    'bbox': det.get('bbox')
                })
            
            # 更新进度
            if self.total_frames > 0:
                progress = int((self.frame_index + 1) / self.total_frames * 100)
                self.update_progress_signal.emit(progress)
            
            self.frame_index += 1
            
            # 添加微小延时，避免界面刷新过快卡顿，也模拟视频播放感
            # 如果希望最快速度检测，可以去除或减小这个 sleep
            time.sleep(0.01)
            
        self.update_log_signal.emit("[完成] 数据集检测完成")

    def _add_overlay(self, frame: np.ndarray, fps: float, mileage: str) -> np.ndarray:
        """在图像上添加 FPS 和里程信息"""
        overlay = frame.copy()
        
        # 绘制半透明背景
        h, w = overlay.shape[:2]
        overlay_rect = np.zeros((60, w, 3), dtype=np.uint8)
        overlay[0:60, 0:w] = cv2.addWeighted(overlay[0:60, 0:w], 0.7, overlay_rect, 0.3, 0)
        
        # 绘制 FPS
        fps_text = f"FPS: {fps:.1f}"
        cv2.putText(overlay, fps_text, (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # 绘制里程
        mileage_text = f"Mileage: {mileage}"
        cv2.putText(overlay, mileage_text, (10, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return overlay
    
    def _cv2_to_qimage(self, frame: np.ndarray) -> QImage:
        """将 OpenCV 图像转换为 QImage"""
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return qt_image
    
    def pause(self):
        """暂停处理"""
        self.mutex.lock()
        self.is_paused = True
        self.mutex.unlock()
        self.update_log_signal.emit("[暂停] 处理已暂停")
    
    def resume(self):
        """恢复处理"""
        self.mutex.lock()
        self.is_paused = False
        self.mutex.unlock()
        self.update_log_signal.emit("[恢复] 处理已恢复")
    
    def stop(self):
        """停止处理"""
        self.mutex.lock()
        self.is_running = False
        self.is_paused = False
        self.mutex.unlock()
        self.update_log_signal.emit("[停止] 正在停止处理...")
    
    def _cleanup(self):
        """清理资源"""
        if self.cap:
            self.cap.release()
        # 删除临时视频目录
        if self._temp_video_dir and os.path.isdir(self._temp_video_dir):
            try:
                shutil.rmtree(self._temp_video_dir, ignore_errors=True)
            except Exception:
                pass
            self._temp_video_dir = None

        self.is_running = False
        self.is_paused = False
