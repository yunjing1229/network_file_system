from abc import ABC, abstractmethod
import os
import sys
import time
import signal
from typing import Dict, Any

# 添加src目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

current_file = os.path.abspath(__file__)
# 获取当前文件所在目录
current_dir = os.path.dirname(current_file)
# 获取父目录（上一级目录）
parent_dir = os.path.dirname(current_dir)

# 将父目录添加到 Python 搜索路径
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from utils.config import ConfigManager
from utils.logger import setup_logger
from protocols.tcp_protocol import TCPProtocol
from protocols.udp_protocol import UDPProtocol
from file_manager.file_transfer import FileTransferManager
from thread.thread_pool import ThreadPool
from thread.sync_utils import SynchronizedDict

class NetworkFileSystem(ABC):
    def __init__(self):
        self.config = ConfigManager()
        self.logger = setup_logger("MainSystem")

        self.file_transfer = FileTransferManager(self.config)
        self.shared_data = SynchronizedDict()
        
        # 运行状态
        self.is_running = False
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        self.logger.info(f"接收到信号 {signum}，正在关闭系统...")
        self.stop()
       
    @abstractmethod
    def initialize_protocols(self) -> bool:
        pass
      
    @abstractmethod 
    def start(self) -> bool:
        pass
      
    def on_status(self, message: str):
        self.logger.info(f"状态: {message}")
        
    def on_error(self, message: str):
        self.logger.error(f"错误: {message}")

    def handle_file_list_request(self, client_addr, request_data):
        """处理文件列表请求"""
        try:
            message = json.loads(request_data.decode('utf-8'))
            
            # 获取请求的目录
            request_dir = message.get('directory', 'uploads')
            recursive = message.get('recursive', False)

            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 构建安全路径
            src_dir = os.path.dirname(current_dir)  # 去掉 file_system
            base_dir = os.path.join(src_dir, "data")
            
            # 防止目录遍历攻击
            safe_dir = os.path.normpath(request_dir)
            if '..' in safe_dir or safe_dir.startswith('/'):
                safe_dir = "uploads"
            
            target_dir = os.path.join(base_dir, safe_dir)
            
            # 发送文件列表
            if recursive:
                self.tcp_server.send_directory_structure(client_addr, target_dir)
            else:
                self.tcp_server.send_file_list(client_addr, target_dir)
                
        except Exception as e:
            self.logger.error(f"处理文件列表请求失败: {e}")
    @abstractmethod 
    def stop(self):
      pass
    @abstractmethod 
    def run(self):
        pass








