"""
数据库管理类 - 负责 SQLite 数据库操作
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, List


class DatabaseManager:
    """SQLite 数据库管理器"""
    
    def __init__(self, db_path: str = "railway_detection.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.init_database()
    
    def init_database(self):
        """初始化数据库，创建表结构"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
            
            cursor = self.conn.cursor()
            
            # 创建检测记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detection_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    defect_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    mileage TEXT,
                    bbox_x REAL,
                    bbox_y REAL,
                    bbox_w REAL,
                    bbox_h REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    source_type TEXT NOT NULL,
                    source_path TEXT,
                    model_name TEXT,
                    model_path TEXT,
                    conf_threshold REAL,
                    status TEXT DEFAULT 'running',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT
                )
            """)
            
            self.conn.commit()
            print(f"[Database] 数据库初始化成功: {self.db_path}")
            
        except sqlite3.Error as e:
            print(f"[Database] 数据库初始化失败: {e}")
            raise
    
    def create_task(self, task_id: str, source_type: str, source_path: str = None,
                   model_name: str = None, model_path: str = None, conf_threshold: float = 0.5) -> bool:
        """
        创建新任务
        
        Args:
            task_id: 任务ID
            source_type: 源类型 (image/video/camera)
            source_path: 源文件路径
            model_name: 模型名称
            model_path: 模型文件路径
            conf_threshold: 置信度阈值
            
        Returns:
            bool: 是否创建成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (task_id, source_type, source_path, model_name, model_path, conf_threshold)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (task_id, source_type, source_path, model_name, model_path, conf_threshold))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"[Database] 创建任务失败: {e}")
            return False
    
    def insert_record(self, task_id: str, frame_index: int, defect_type: str,
                     confidence: float, mileage: str = None, bbox: tuple = None) -> bool:
        """
        插入检测记录
        
        Args:
            task_id: 任务ID
            frame_index: 帧索引
            defect_type: 病害类型
            confidence: 置信度
            mileage: 里程位置 (例如: "K120+500")
            bbox: 边界框 (x, y, w, h)
            
        Returns:
            bool: 是否插入成功
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bbox_x, bbox_y, bbox_w, bbox_h = bbox if bbox else (None, None, None, None)
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO detection_records 
                (task_id, frame_index, defect_type, confidence, timestamp, mileage, bbox_x, bbox_y, bbox_w, bbox_h)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_id, frame_index, defect_type, confidence, timestamp, mileage,
                  bbox_x, bbox_y, bbox_w, bbox_h))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"[Database] 插入记录失败: {e}")
            return False
    
    def get_records_by_task(self, task_id: str, limit: int = 100) -> List[Dict]:
        """
        获取指定任务的检测记录
        
        Args:
            task_id: 任务ID
            limit: 返回记录数限制
            
        Returns:
            List[Dict]: 记录列表
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM detection_records 
                WHERE task_id = ? 
                ORDER BY frame_index DESC 
                LIMIT ?
            """, (task_id, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"[Database] 查询记录失败: {e}")
            return []
    
    def update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        try:
            cursor = self.conn.cursor()
            finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "finished" else None
            cursor.execute("""
                UPDATE tasks 
                SET status = ?, finished_at = ? 
                WHERE task_id = ?
            """, (status, finished_at, task_id))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"[Database] 更新任务状态失败: {e}")
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("[Database] 数据库连接已关闭")
