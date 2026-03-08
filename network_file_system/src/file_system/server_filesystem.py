import sys
import os
import json
import socket

# 获取当前文件所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 将当前目录添加到 Python 路径中
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
from base_filesystem import *

class ServerFileSystem(NetworkFileSystem):
    def __init__(self):
        super().__init__()
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(current_file)  # src目录
        project_root = os.path.dirname(src_dir)  # 项目根目录
        data_dir = os.path.join(os.path.dirname(project_root), "data")
    
        self.file_transfer = FileTransferManager(
            self.config, 
            base_dir=data_dir  # 传递正确的路径
        )
        
        # 初始化组件
        self.thread_pool = ThreadPool(
            self.config.get('thread_pool_size', 5)
        )

        self.shared_data = SynchronizedDict()
        
        # 协议实例
        self.tcp_server = None
        self.udp_server = None
        
        # 运行状态
        self.upload_dir = None

    def initialize_protocols(self) -> bool:
        try:
            # 创建TCP服务器
            self.tcp_server = TCPProtocol(
                '0.0.0.0',
                self.config.get('tcp_port', 8888)
            )
            
            # 注册TCP回调函数
            self.tcp_server.register_callback('status', self.on_status)
            self.tcp_server.register_callback('error', self.on_error)
            self.tcp_server.register_callback('data_received', self.on_tcp_data_received)
            self.tcp_server.register_callback('client_connected', self.on_client_connected)
            self.tcp_server.register_callback('client_disconnected', self.on_client_disconnected)
            self._init_upload_directory()
            return True
            
        except Exception as e:
            self.logger.error(f"协议初始化失败: {e}")
            return False

    def _init_upload_directory(self):
        """初始化上传目录"""
        try:
            # 使用 FileTransferManager 中的路径
            if hasattr(self, 'file_transfer') and self.file_transfer:
                data_dir = self.file_transfer.file_ops.get_data_directory()
                self.upload_dir = os.path.join(data_dir, "uploads")
            else:
                # 备用方案：手动计算路径
                current_file = os.path.abspath(__file__)
                src_dir = os.path.dirname(current_file)
                project_root = os.path.dirname(src_dir)
                data_dir = os.path.join(project_root, "data")
                self.upload_dir = os.path.join(data_dir, "uploads")
            
            # 确保目录存在
            os.makedirs(self.upload_dir, exist_ok=True)
            
            self.logger.info(f"上传目录已初始化: {self.upload_dir}")
            
            # 检查目录内容
            if os.path.exists(self.upload_dir):
                files = os.listdir(self.upload_dir)
                self.logger.info(f"上传目录包含 {len(files)} 个文件")
                
        except Exception as e:
            self.logger.error(f"初始化上传目录失败: {e}")
            self.upload_dir = None
    
    def on_tcp_data_received(self, data, client_addr):
        """处理TCP数据"""
        try:
            # 1. 先尝试判断是否是文件传输数据（快速检查）
            # 文件传输数据通常很大，且包含分隔符
            if len(data) > 1000:  # 假设文件数据都比较大
                # 直接传递给 FileTransfer 处理
                self.thread_pool.submit_task(
                    self.file_transfer.receive_file_tcp,
                    data, client_addr, self.tcp_server
                )
                return
            
            # 2. 对于小数据，尝试解析JSON（用于控制消息）
            try:
                # 尝试解码为UTF-8
                data_str = data.decode('utf-8')
                
                # 尝试解析JSON
                try:
                    message = json.loads(data_str)
                    message_type = message.get('type')
                    
                    if message_type == 'get_filelist':
                        # 处理文件列表请求
                        self.logger.info(f"客户端 {client_addr} 请求文件列表")
                        
                        self.thread_pool.submit_task(
                            self.file_transfer.list_file_tcp_server,
                            data,  # 传递原始数据
                            client_addr,
                            self.tcp_server
                        )
                    
                    elif message_type == 'download_request':
                        # 处理下载请求
                        self.logger.info(f"客户端 {client_addr} 请求下载文件")
                        
                        self.thread_pool.submit_task(
                            self.file_transfer.handle_download_request,
                            data,  # 传递原始数据
                            client_addr,
                            self.tcp_server
                        )
                    
                    else:
                        # 其他消息类型，交给 FileTransfer
                        self.thread_pool.submit_task(
                            self.file_transfer.receive_file_tcp,
                            data, client_addr, self.tcp_server
                        )
                        
                except json.JSONDecodeError:
                    # 不是JSON，交给 FileTransfer
                    self.thread_pool.submit_task(
                        self.file_transfer.receive_file_tcp,
                        data, client_addr, self.tcp_server
                    )
                    
            except UnicodeDecodeError:
                # 不是UTF-8，直接交给 FileTransfer
                self.thread_pool.submit_task(
                    self.file_transfer.receive_file_tcp,
                    data, client_addr, self.tcp_server
                )
                    
        except Exception as e:
            self.logger.error(f"处理TCP数据失败: {e}")
        
    def on_tcp_show_filelist(self, data: bytes, client_addr: tuple):
        self.logger.info(f"所有可下载文件")
        self.thread_pool.submit_task(
            self.file_transfer.list_file_tcp_server,
            data, client_addr, self.tcp_server
        )
    
    def on_client_connected(self, client_addr: tuple):
        """客户端连接回调"""
        self.logger.info(f"客户端连接: {client_addr}")
        self.shared_data.put(f"client_{client_addr}", {
            'address': client_addr,
            'connect_time': time.time(),
            'protocol': 'TCP'
        })
    
    def on_client_disconnected(self, client_addr: tuple):
        """客户端断开回调"""
        self.logger.info(f"客户端断开: {client_addr}")
        self.shared_data.delete(f"client_{client_addr}")
          
    def start(self) -> bool:
        try:
            # 启动线程池
            self.thread_pool.start()
            
            # 启动TCP服务器
            if not self.tcp_server.start_server():
                return False

            
            self.is_running = True
            self.logger.info("所有服务器启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"启动服务器失败: {e}")
            return False
    def stop(self) -> bool:
        self.is_running = False
        
        self.logger.info("正在停止系统...")
        self.tcp_server.stop()
        if self.udp_server:
             self.udp_server.stop()
            
            # 停止线程池
        self.thread_pool.stop()
            
        self.logger.info("系统已停止")
        
    def signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.info(f"接收到信号 {signum}")
        self.stop()
    
    def run(self):
        if not self.initialize_protocols():
            return
        
        if not self.start():
            return
        
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

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        tcp_stats = self.tcp_client.get_stats() if self.tcp_client else {}
        transfer_stats = {
            'active_transfers': len(self.file_transfer.transfers),
            'completed_transfers': len(self.file_transfer.completed_transfers)
        }
        
        return {
            'tcp_stats': tcp_stats,
            'file_transfer_stats': transfer_stats,
            'shared_data_count': len(self.shared_data)
        }
