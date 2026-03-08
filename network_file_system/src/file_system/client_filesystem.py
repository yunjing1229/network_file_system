import os
import sys
import time
import signal
from file_system.base_filesystem import*
from typing import Dict, Any

# 添加src目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class ClientFileSystem(NetworkFileSystem):
    def __init__(self, filename=None, command='upload'):
        super().__init__()
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(current_file)
        project_root = os.path.dirname(src_dir)
        
        # 计算data路径（与src同级）
        data_dir = os.path.join(project_root, "data")  # 修改这里
        
        # 初始化组件
        self.filename = filename
        self.command = command
        
        # 协议实例
        self.tcp_client = None
        
        # 打印调试信息
        print(f"🔍 client.py data_dir: {data_dir}")
        print(f"🔍 project_root: {project_root}")

    def initialize_protocols(self) -> bool:
        try:
            # 创建TCP客户端
            server_ip = self.config.get('server_ip', '127.0.0.1')
            tcp_port = self.config.get('tcp_port', 8888)
            self.tcp_client = TCPProtocol(
            server_ip,
            tcp_port
            )
            
            # 注册TCP回调函数
            self.tcp_client.register_callback('status', self.on_status)
            self.tcp_client.register_callback('error', self.on_error)
                    
            self.logger.info("网络协议初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"协议初始化失败: {e}")
            return False

    def send_file(self, file_path: str, protocol: str = 'TCP', target: tuple = None) -> bool:
        """发送文件"""
        if protocol.upper() == 'TCP':
            return self.file_transfer.send_file_tcp(file_path, self.tcp_client, target)
        elif protocol.upper() == 'UDP':
            # UDP文件传输实现类似，但需要处理数据包丢失
            self.logger.warning("UDP文件传输暂未实现")
            return False
        else:
            self.logger.error(f"不支持的协议: {protocol}")
            return False

    def download_file(self, file_path: str, protocol: str = 'TCP', target: tuple = None) -> bool:
        if protocol.upper() == 'TCP':
            return self.file_transfer.download_file_tcp(file_path, self.tcp_client, target)
        else:
            self.logger.error(f"不支持的协议: {protocol}")
            return False
    
    def list_filename_client(self, protocol: str = 'TCP'):
        """智能获取服务器文件列表"""
        if protocol.upper() == 'TCP':
            try:
                # 调用修改后的list_file_tcp_client，它会返回文件列表
                file_list = self.file_transfer.list_file_tcp_client(self.tcp_client)
                  
                # 验证返回的数据类型
                if isinstance(file_list, list):
                    # 如果返回的是列表，直接返回
                    print(f"✅ 成功获取 {len(file_list)} 个文件")
                    return file_list
                elif isinstance(file_list, bool) and file_list:
                    # 如果返回True但实际数据在其他地方
                    return self._get_files_from_alternative_source()
                          
            except Exception as e:
                print(f"❌ 获取文件列表异常: {e}")
        
        return []

    def start(self) -> bool:
        try:
            # 启动TCP客户端
            if not self.tcp_client.connect_to_server():
                return False
            
            self.is_running = True
            self.logger.info("所有客户端启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"启动客户端失败: {e}")
            return False
            
    def stop(self) -> bool:
        self.is_running = False
        
        self.logger.info("正在停止系统...")
        
        # 停止协议
        if self.tcp_client:
            self.tcp_client.stop()
        
        self.logger.info("系统已停止")
        return True
        
    def run(self):
        if not self.initialize_protocols():
            return
        
        if not self.start():
            return

        # 计算项目根目录
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(current_file)  # src目录
        project_root = os.path.dirname(src_dir)  # 项目根目录
         
        if self.command == 'upload':
            # 上传文件：从downloads目录读取
            file_path = os.path.join(project_root, "data", "downloads", self.filename)
            self.logger.info(f"上传文件: {file_path}")
            self.send_file(file_path, 'TCP')
        elif self.command == 'download_request':
            # 下载文件：保存到downloads目录
            file_path = os.path.join(project_root, "data", "uploads", self.filename)
            self.logger.info(f"请求下载文件: {file_path}")
            self.download_file(file_path, 'TCP')
        elif self.command == 'get_filelist':
            self.list_filename_client()
            
        self.logger.info("网络文件传输系统运行中...")
        self.logger.info("按 Ctrl+C 停止系统")
        
        try:
            # 主循环
            while self.is_running:
                time.sleep(1)
                        
        except KeyboardInterrupt:
            self.logger.info("接收到键盘中断")
        finally:
            self.stop()
