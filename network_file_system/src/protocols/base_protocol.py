import socket
import threading
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, Optional
from utils.logger import setup_logger

class NetworkProtocol(ABC):
    def __init__(self, name: str, host: str = 'localhost', port: int = 8888):
        self.name = name
        self.host = host
        self.port = port
        self.socket = None
        self.is_running = False
        self.callbacks: Dict[str, Callable] = {}
        self.threads: list = []  # 演示列表使用
        self.logger = setup_logger(f"Protocol_{name}")
        
        # 统计信息字典
        self.stats: Dict[str, Any] = {
            'bytes_sent': 0,
            'bytes_received': 0,
            'connections': 0,
            'errors': 0
        }
    
    @abstractmethod
    def send_data(self, data: bytes, target: tuple = None) -> bool:
        """发送数据 - 抽象方法"""
        pass
    
    @abstractmethod
    def start_server(self) -> bool:
        """启动服务器 - 抽象方法"""
        pass
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """注册回调函数 - 演示函数作为参数"""
        self.callbacks[event] = callback
        self.logger.info(f"注册回调函数: {event}")
    
    def trigger_callback(self, event: str, *args, **kwargs) -> None:
        """触发回调函数"""
        if event in self.callbacks:
            try:
                self.callbacks[event](*args, **kwargs)
            except Exception as e:
                self.logger.error(f"回调函数执行失败 {event}: {e}")
    
    def start_thread(self, target: Callable, name: str, args: tuple = ()) -> threading.Thread:
        """启动线程 - 演示多线程"""
        thread = threading.Thread(target=target, name=name, args=args, daemon=True)
        thread.start()
        self.threads.append(thread)
        self.logger.info(f"启动线程: {name}")
        return thread
    
    def stop(self) -> None:
        """停止协议"""
        self.is_running = False
        if self.socket:
            self.socket.close()
        
        # 等待线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1)
        
        self.logger.info(f"{self.name} 协议已停止")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()
    
    def update_stats(self, key: str, value: Any) -> None:
        """更新统计信息"""
        if key in self.stats:
            if isinstance(self.stats[key], (int, float)):
                self.stats[key] += value
            else:
                self.stats[key] = value
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.name} Protocol - {self.host}:{self.port}"