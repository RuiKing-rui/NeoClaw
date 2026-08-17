#负责审计
import os
import json
import threading
import queue
import atexit
from datetime import datetime, timezone

# 内存队列 + 守护线程
class JSONLEventLogger:
    # 单例模式
    #一个 Python 进程中，无论创建多少次 JSONLEventLogger()，都返回同一个日志对象。
    _instance = None
    _lock = threading.Lock()

    #__new__负责创建对象，__init__负责初始化对象
    def __new__(cls, log_dir: str = "logs"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)    #创建一个 JSONLEventLogger 实例
                cls._instance._init_logger(log_dir)
            return cls._instance
    #初始化
    def _init_logger(self, log_dir: str):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        # 无界内存队列，用于缓冲日志事件
        self.log_queue = queue.Queue()

        self.worker_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.worker_thread.start()

        # 确保程序被关闭时，队列里的剩下日志能写完
        atexit.register(self.shutdown)

    # 后台线程的死循环：一直盯着队列，有日志就写，没日志就阻塞休眠
    def _write_loop(self):
        while True:
            log_item = self.log_queue.get()

            if log_item is None:
                self.log_queue.task_done()
                break

            try:
                thread_id = log_item.get("thread_id", "system")
                safe_id = "".join(c for c in thread_id if c.isalnum() or c in "-_") or "default"
                file_path = os.path.join(self.log_dir, f"{safe_id}.jsonl")

                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_item, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"[Logger Error] 异步写日志失败: {e}")
            finally:
                self.log_queue.task_done()

    # 前台调用的埋点方法
    def log_event(self, thread_id: str, event: str, **kwargs):
        #生成UTC时间
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        #组装字典
        log_item = {
            "ts": now_utc,
            "thread_id": thread_id,
            "event": event,
            **kwargs
        }
        #将字典传入日志队列
        self.log_queue.put(log_item)

    def shutdown(self):
        self.log_queue.put(None)
        self.log_queue.join()

audit_logger = JSONLEventLogger()

#外部第一次导入from .logger import audit_logger时
#立即创建 JSONLEventLogger，创建 logs/ 目录，创建内存队列，启动后台写日志线程，注册退出清理函数