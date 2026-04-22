import subprocess
import sys
from PySide6.QtCore import QThread, Signal


class ScriptRunnerWorker(QThread):
    # 定义信号：向 UI 发送实时日志、结束信号、错误信号
    log_signal = Signal(str)
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, script_path):
        super().__init__()
        self.script_path = script_path

    def run(self):
        """线程入口函数"""
        self.log_signal.emit(f"🚀 开始执行脚本: {self.script_path}...")
        try:
            # 使用 subprocess 调用外部 python，实时捕获输出
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(
                ['python', '-u', self.script_path],  # -u 禁用缓冲，实时输出
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                creationflags=creation_flags
            )

            # 实时读取标准输出
            for line in process.stdout:
                self.log_signal.emit(f"[Output] {line.strip()}")
            
            # 读取错误输出
            stderr = process.communicate()[1]
            if stderr:
                self.error_signal.emit(f"[Error] {stderr}")

            self.log_signal.emit("✅ 脚本执行完毕。")
            self.finished_signal.emit()

        except Exception as e:
            self.error_signal.emit(f"❌ 执行异常: {str(e)}")
