import os
import time
import pandas as pd
from PySide6.QtWidgets import QTableWidgetItem


class FileManager:
    @staticmethod
    def get_folder_data(folder_path):
        """读取文件夹并返回 DataFrame 格式的数据"""
        data = []
        try:
            for entry in os.scandir(folder_path):
                if entry.is_file():
                    stat = entry.stat()
                    data.append({
                        "文件名": entry.name,
                        "类型": os.path.splitext(entry.name)[1],
                        "大小 (KB)": round(stat.st_size / 1024, 2),
                        "修改时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                    })
            return pd.DataFrame(data)
        except Exception as e:
            return None

    @staticmethod
    def populate_table(table_widget, df):
        """将 DataFrame 数据填充到 QTableWidget"""
        if df is None or df.empty:
            table_widget.setRowCount(0)
            return

        headers = df.columns.tolist()
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        table_widget.setRowCount(len(df))

        for row_idx, row_data in df.iterrows():
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                table_widget.setItem(row_idx, col_idx, item)
