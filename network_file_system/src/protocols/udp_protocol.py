import socket
import threading
from typing import Tuple, Optional
from .base_protocol import NetworkProtocol

class UDPProtocol(NetworkProtocol):
    def __init__(self, host: str = 'localhost', port: int = 8889):
        super().__init__("UDP", host, port)
        self.clients: set = set()  # 已知客户端集合
        self.clients_lock = threading.Lock()  # 客户端集合锁
    
    def start_server(self) -> bool:
        """启动UDP服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.is_running = True
            
            # 启动接收线程
            self.start_thread(self._receive_loop, "UDP_Receive")
            
            self.logger.info(f"UDP服务器启动在 {self.host}:{self.port}")
            self.trigger_callback('status', "UDP服务器启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"UDP服务器启动失败: {e}")
            self.trigger_callback('error', f"UDP服务器启动失败: {e}")
            return False
    
    def _receive_loop(self) -> None:
        """UDP接收循环"""
        while self.is_running:
            try:
                data, addr = self.socket.recvfrom(4096)
                if data:
                    # 记录新客户端
                    with self.clients_lock:
                        self.clients.add(addr)
                    
                    self.update_stats('bytes_received', len(data))
                    self.update_stats('connections', len(self.clients))
                    self.trigger_callback('data_received', data, addr)
                    
            except socket.error:
                if self.is_running:
                    self.logger.warning("UDP接收数据时发生错误")
                break
            except Exception as e:
                self.logger.error(f"UDP接收异常: {e}")
    
    def send_data(self, data: bytes, target: Optional[Tuple] = None) -> bool:
        """发送UDP数据 - 多态实现"""
        try:
            if target:  # 发送到特定目标
                self.socket.sendto(data, target)
                self.update_stats('bytes_sent', len(data))
                return True
            else:  # 广播到所有已知客户端
                success = True
                with self.clients_lock:
                    for client_addr in self.clients:
                        try:
                            self.socket.sendto(data, client_addr)
                            self.update_stats('bytes_sent', len(data))
                        except Exception as e:
                            self.logger.error(f"发送数据到 {client_addr} 失败: {e}")
                            success = False
                return success
                
        except Exception as e:
            self.logger.error(f"发送UDP数据失败: {e}")
            self.update_stats('errors', 1)
            return False
    
    def start_client(self) -> bool:
        """启动UDP客户端"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.is_running = True
            
            # UDP客户端不需要专门的接收线程，因为是无连接的
            self.logger.info(f"UDP客户端已启动")
            self.trigger_callback('status', "UDP客户端启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"UDP客户端启动失败: {e}")
            self.trigger_callback('error', f"UDP客户端启动失败: {e}")
            return False