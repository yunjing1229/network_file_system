import socket
import json
import time
import threading
from typing import List, Tuple, Optional
from .base_protocol import NetworkProtocol

class TCPProtocol(NetworkProtocol):
    def __init__(self, host: str = 'localhost', port: int = 8888, mode: str = 'server'):
        super().__init__("TCP", host, port)
        self.clients: List[socket.socket] = []  # 客户端连接列表
        self.client_lock = threading.Lock()  # 客户端列表锁
        self.mode = mode

        self.file_transfers = {}
        self.receive_buffers = {}

        self.file_received_callback = None
        self.transfer_progress_callback = None
        self.is_connected = True
    
    def start_server(self) -> bool:
        """启动TCP服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(10)
            self.is_running = True
            
            # 启动接受连接线程
            self.start_thread(self._accept_connections, "TCP_Accept")
            
            self.logger.info(f"TCP服务器启动在 {self.host}:{self.port}")
            self.trigger_callback('status', f"TCP服务器启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"TCP服务器启动失败: {e}")
            self.trigger_callback('error', f"TCP服务器启动失败: {e}")
            return False
    
    def _accept_connections(self) -> None:
        """接受客户端连接"""
        while self.is_running:
            try:
                client_socket, client_addr = self.socket.accept()
                
                with self.client_lock:  # 线程同步
                    self.clients.append(client_socket)
                
                self.update_stats('connections', 1)
                
                # 为每个客户端启动处理线程
                self.start_thread(
                    self._handle_client, 
                    f"TCP_Client_{client_addr}", 
                    (client_socket, client_addr)
                )
                
                self.logger.info(f"客户端连接: {client_addr}")
                self.trigger_callback('client_connected', client_addr)
                
            except socket.error:
                if self.is_running:
                    self.logger.warning("接受连接时发生错误")
                break
    
    def _handle_client(self, client_socket: socket.socket, client_addr: Tuple[str, int]) -> None:
        """处理客户端连接"""
        try:
            
            while self.is_running:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                
                    self.update_stats('bytes_received', len(data))
                    self.trigger_callback('data_received', data, client_addr)
                    
                except socket.timeout:
                    # 超时不是错误，继续等待
                    continue
                except (ConnectionResetError, ConnectionAbortedError):
                    self.logger.info(f"客户端 {client_addr} 连接被重置")
                    break
                except Exception as e:
                    self.logger.error(f"接收数据时出错: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"处理客户端 {client_addr} 时出错: {e}")
        finally:
            client_socket.close()
            with self.client_lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
            
            self.logger.info(f"客户端断开: {client_addr}")
            self.trigger_callback('client_disconnected', client_addr)
    
    def send_data(self, data: bytes, target: Optional[Tuple] = None) -> bool:
        """发送TCP数据 - 多态实现"""
        try:
            if target:  # 发送到特定客户端
                with self.client_lock:
                    for client in self.clients:
                        if client.getpeername() == target:
                            client.sendall(data)
                            self.update_stats('bytes_sent', len(data))
                            return True
                return False
            else:  # 广播到所有客户端
                success = True
                with self.client_lock:
                    for client in self.clients:
                        try:
                            client.sendall(data)
                            self.update_stats('bytes_sent', len(data))
                        except Exception as e:
                            self.logger.error(f"发送数据失败: {e}")
                            success = False
                return success
                
        except Exception as e:
            self.logger.error(f"发送数据失败: {e}")
            self.update_stats('errors', 1)
            return False
        
    def sendall(self, data):
        try:
            self.socket.sendall(data)
            return True
        
        except Exception as e:
            self.logger.error(f"发送数据失败: {e}")
            self.update_stats('errors', 1)
            return False
            
    
    def connect_to_server(self) -> bool:
        """连接到TCP服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.is_running = True
            
            # 启动接收线程
            #self.start_thread(self._send_file, "TCP_Receive")
            
            self.logger.info(f"已连接到TCP服务器 {self.host}:{self.port}")
            self.trigger_callback('status', "连接到服务器成功")
            return True
            
        except Exception as e:
            self.logger.error(f"连接TCP服务器失败: {e}")
            self.trigger_callback('error', f"连接失败: {e}")
            return False
        
    def _send_file(self) -> bool:
        with open("123.txt", 'rb') as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                self.socket.sendall(chunk)

    
    def _receive_loop(self) -> None:
        """客户端接收循环"""
        while self.is_running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                
                self.update_stats('bytes_received', len(data))
                self.trigger_callback('data_received', data, (self.host, self.port))
                    
            except Exception as e:
                if self.is_running:
                    self.logger.error(f"接收数据失败: {e}")
                break


    def is_client_connected(self, client_addr: tuple) -> bool:
        """检查客户端是否仍然连接"""
        with self.client_lock:
            for client in self.clients:
                try:
                    if client.getpeername() == client_addr:
                        # 尝试发送一个空数据包测试连接
                        client.send(b'')
                        return True
                except:
                    continue
        return False

    def get_client_socket(self, client_addr: tuple) -> Optional[socket.socket]:
        """安全地获取客户端socket"""
        with self.client_lock:
            for client in self.clients:
                try:
                    if client.getpeername() == client_addr:
                        return client
                except:
                    continue
        return None
