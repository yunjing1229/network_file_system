import threading
import time
from typing import Dict, Any
from utils.logger import setup_logger

class SynchronizedDict:
    def __init__(self):
        self._data: Dict[Any, Any] = {}
        self._lock = threading.RLock()  # 可重入锁
        self.logger = setup_logger("SyncDict")
    
    def put(self, key: Any, value: Any) -> None:
        """添加键值对"""
        with self._lock:
            self._data[key] = value
            self.logger.debug(f"添加数据: {key} -> {value}")
    
    def get(self, key: Any, default: Any = None) -> Any:
        """获取值"""
        with self._lock:
            return self._data.get(key, default)
    
    def delete(self, key: Any) -> bool:
        """删除键值对"""
        with self._lock:
            if key in self._data:
                del self._data[key]
                self.logger.debug(f"删除数据: {key}")
                return True
            return False
    
    def contains(self, key: Any) -> bool:
        """检查键是否存在"""
        with self._lock:
            return key in self._data
    
    def keys(self):
        """获取所有键"""
        with self._lock:
            return list(self._data.keys())
    
    def values(self):
        """获取所有值"""
        with self._lock:
            return list(self._data.values())
    
    def items(self):
        """获取所有键值对"""
        with self._lock:
            return list(self._data.items())
    
    def clear(self) -> None:
        """清空字典"""
        with self._lock:
            self._data.clear()
            self.logger.debug("字典已清空")
    
    def __len__(self) -> int:
        """获取字典大小"""
        with self._lock:
            return len(self._data)
    
    def __str__(self) -> str:
        """字符串表示"""
        with self._lock:
            return str(self._data)

class RateLimiter:
    """速率限制器 - 演示线程同步"""
    
    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()
        self.logger = setup_logger("RateLimiter")
    
    def acquire(self) -> bool:
        """获取许可"""
        with self.lock:
            now = time.time()
            
            # 移除过期的请求记录
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            else:
                self.logger.warning("速率限制触发")
                return False
    
    def get_remaining_requests(self) -> int:
        """获取剩余请求数"""
        with self.lock:
            now = time.time()
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            return max(0, self.max_requests - len(self.requests))