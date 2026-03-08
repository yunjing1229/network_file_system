import os
import sys
import time
import signal
from typing import Dict, Any

# 添加src目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.config import ConfigManager
from utils.logger import setup_logger
from protocols.tcp_protocol import TCPProtocol
from file_manager.file_transfer import FileTransferManager
from thread.thread_pool import ThreadPool
from thread.sync_utils import SynchronizedDict
from file_system.server_filesystem import ServerFileSystem

def main():
    """主函数"""
    print("=" * 60)
    print("网络文件传输系统")
    print("演示知识点: 函数, 类继承, 多态, 列表, 字典, 字符串处理")
    print("            TCP/UDP, 文件处理, 多线程同步")
    print("=" * 60)
    
    # 创建并运行系统
    system = ServerFileSystem()
    system.run()

if __name__ == "__main__":
    main()

