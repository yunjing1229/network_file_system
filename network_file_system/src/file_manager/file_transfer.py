import os
import socket
import json
import random
import time
import base64
import zmq
import zmq.asyncio
import asyncio
import time 

from typing import Dict, List, Optional
from protocols.tcp_protocol import TCPProtocol
from protocols.udp_protocol import UDPProtocol
from .file_operations import FileOperations
from utils.logger import setup_logger

class FileTransferManager:
    def __init__(self, config, base_dir: str = None):
        self.config = config
        self.file_ops = FileOperations(base_dir=base_dir)
        self.logger = setup_logger("FileTransfer")
        
        # 传输状态字典
        self.transfers: Dict[str, Dict] = {}
        self.completed_transfers: List[Dict] = []
    
    def prepare_file_transfer(self, file_path: str, protocol: str) -> Optional[Dict]:
        """准备文件传输"""
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"文件不存在: {file_path}")
                return None
            
            file_info = self.file_ops.get_file_info(file_path)
            if not file_info:
                return None
            
            transfer_id = f"{file_info['hash']}"
            
            transfer_info = {
                'id': transfer_id,
                'file_path': file_path,
                'file_info': file_info,
                'protocol': protocol,
                'status': 'prepared',
                'start_time': None,
                'end_time': None,
                'bytes_transferred': 0,
                'total_bytes': file_info['size']
            }
            
            self.transfers[transfer_id] = transfer_info
            self.logger.info(f"准备文件传输: {file_path} via {protocol}")
            
            return transfer_info
            
        except Exception as e:
            self.logger.error(f"准备文件传输失败: {e}")
            return None

    def _display_server_files(self, response):
        """显示服务器返回的文件列表"""
        try:
            if response.get('type') == 'get_filelist':
                files = response.get('files', [])
                file_count = response.get('count', 0)
            
                if not files:
                    print("\n服务器 uploads 目录为空")
                    return True
            
                print("\n" + "=" * 60)
                print(f"服务器文件列表 (共 {file_count} 个文件)")
                print("=" * 60)
            
                for i, filename in enumerate(files, 1):
                    print(f"{i:3}. {filename}")
            
                print("=" * 60)
                return True
            
            elif response.get('type') == 'error':
                print(f"\n错误: {response.get('message', '未知错误')}")
                return False
            
            else:
                print(f"\n未知的响应类型: {response}")
                return False
            
        except Exception as e:
            self.logger.error(f"显示文件列表失败: {e}")
            return False

    def _send_file_data(self, client_socket: socket.socket, file_path: str, file_size: int,  tcp_protocol: TCPProtocol):
        """发送文件给客户端"""
        try:
            self.logger.info(f"开始发送文件: {file_path} ({self._format_size(file_size)})")
            
            # 检查socket是否有效
            if client_socket is None:
                self.logger.error("客户端socket为空")
                return
                
            # 添加错误处理
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                
                while bytes_sent < file_size:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    
                    try:
                        # 发送数据块
                        client_socket.send(chunk)
                        bytes_sent += len(chunk)
                        
                        # 每发送1MB记录一次进度
                        if bytes_sent % (1024 * 1024) < 8192:  # 约每1MB
                            progress = (bytes_sent / file_size) * 100
                            self.logger.info(f"发送进度: {progress:.1f}%")
                            
                    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                        self.logger.error(f"连接断开: {e}")
                        break
                    except socket.error as e:
                        self.logger.error(f"socket错误: {e}")
                        break
            
            self.logger.info(f"文件发送完成: {file_path}, 发送了 {bytes_sent} 字节")
                
        except Exception as e:
            self.logger.error(f"发送文件失败: {e}")
            import traceback
            traceback.print_exc()
            
    def list_file_tcp_client(self, tcp_protocol: TCPProtocol) -> list:
        """向服务器请求文件列表，返回文件列表"""
        try:
            # 生成唯一的请求ID
            transfer_id = f"get_filelist_{int(time.time())}_{random.randint(1000, 9999)}"
            
            # 构建请求头
            header = {
                'type': 'get_filelist',
                'transfer_id': transfer_id,
                'client_id': getattr(self, 'client_id', 'unknown'),
                'timestamp': time.time()
            }
            
            self.logger.info(f"正在请求文件列表...")
            
            # 发送请求
            if not tcp_protocol.sendall(json.dumps(header).encode('utf-8')):
                self.logger.error("发送文件列表请求失败")
                return []  # 返回空列表而不是False
            
            self.logger.info("已发送文件列表请求，等待服务器响应...")
            
            # 接收响应
            response_data = b''
            
            # 设置超时
            import socket
            original_timeout = tcp_protocol.socket.gettimeout()
            tcp_protocol.socket.settimeout(10.0)  # 10秒超时
            
            try:
                # 尝试接收数据
                while True:
                    chunk = tcp_protocol.socket.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                    
                    # 尝试解析，如果已经是完整的JSON则停止
                    try:
                        response_str = response_data.decode('utf-8')
                        json.loads(response_str)
                        break  # 完整的JSON，停止接收
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # 可能数据不完整，继续接收
                        continue
                        
            except socket.timeout:
                self.logger.warning("接收响应超时")
                return []  # 返回空列表
            finally:
                tcp_protocol.socket.settimeout(original_timeout)
            
            if not response_data:
                self.logger.error("未收到服务器响应")
                return []  # 返回空列表
            
            try:
                response_str = response_data.decode('utf-8')
                response = json.loads(response_str)
                
                self.logger.info(f"收到服务器响应: {response.get('type')}")
                
                # 检查响应类型
                if response.get('type') == 'error':
                    self.logger.error(f"服务器返回错误: {response.get('message')}")
                    return []  # 返回空列表
                
                if response.get('type') == 'get_filelist':
                    # 获取文件列表
                    files = response.get('files', [])
                    simple_files = response.get('simple_files', [])
                    count = response.get('count', 0)
                    
                    self.logger.info(f"成功获取 {count} 个文件")
                    
                    # 转换格式为GUI需要的格式
                    formatted_files = []
                    
                    # 优先使用详细信息
                    if files:
                        for file_info in files:
                            formatted_files.append({
                                'filename': f"data/uploads/{file_info.get('name', '')}",
                                'size': file_info.get('size', 0),
                                'modified': file_info.get('modified', time.time()),
                                'created': file_info.get('created', time.time()),
                                'type': 'file',  # 服务器返回的是文件列表，都是文件
                                'full_path': file_info.get('full_path', '')
                            })
                    # 如果没有详细信息，使用简单文件名列表
                    elif simple_files:
                        for filename in simple_files:
                            formatted_files.append({
                                'filename': f"data/uploads/{filename}",
                                'size': 0,
                                'modified': time.time() - 86400,  # 默认1天前
                                'created': time.time() - 86400,
                                'type': 'file',
                                'full_path': ''
                            })
                    
                    # 返回格式化后的文件列表
                    return formatted_files
                else:
                    self.logger.warning(f"未知的响应类型: {response.get('type')}")
                    return []  # 返回空列表
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"解析服务器响应失败: {e}")
                print(f"\n❌ 服务器响应格式错误: {response_data[:200]}...")
                return []  # 返回空列表
            except UnicodeDecodeError as e:
                self.logger.error(f"解码服务器响应失败: {e}")
                return []  # 返回空列表
                
        except Exception as e:
            self.logger.error(f"请求文件列表失败: {e}")
            print(f"\n❌ 请求文件列表失败: {str(e)}")
            return []  # 返回空列表
            
    def list_file_tcp_server(self, data: bytes, client_addr: tuple, tcp_protocol: TCPProtocol):
        """处理客户端获取文件列表的请求"""
        try:
            message = json.loads(data.decode('utf-8'))
            msg_type = message.get('type')

            if msg_type == 'get_filelist':
                
                data_dir = self.file_ops.get_data_directory()
                upload_dir = os.path.join(data_dir, "uploads")
                
                self.logger.info(f"正在扫描目录: {upload_dir}")
                
                # 确保目录存在
                if not os.path.exists(data_dir):
                    os.makedirs(data_dir)
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                    self.logger.info(f"创建了 uploads 目录: {upload_dir}")
                
                # 获取所有文件名
                filenames = []
                file_details = []
                
                if os.path.exists(upload_dir):
                    for item in os.listdir(upload_dir):
                        item_path = os.path.join(upload_dir, item)
                        if os.path.isfile(item_path):
                            filenames.append(item)
                            
                            # 获取文件详细信息
                            try:
                                stat = os.stat(item_path)
                                file_details.append({
                                    'name': item,
                                    'size': stat.st_size,
                                    'modified': stat.st_mtime,
                                    'created': stat.st_ctime,
                                    'permissions': stat.st_mode,
                                    'full_path': item_path
                                })
                            except Exception as e:
                                self.logger.warning(f"无法获取文件 {item} 的详细信息: {e}")
                                file_details.append({
                                    'name': item,
                                    'size': 0,
                                    'modified': 0,
                                    'created': 0,
                                    'permissions': 0
                                })
                
                # 构建响应
                response = {
                    'type': 'get_filelist',
                    'files': file_details,  # 发送详细信息
                    'simple_files': filenames,  # 兼容旧版本
                    'count': len(filenames),
                    'directory': upload_dir,
                    'total_size': sum(f.get('size', 0) for f in file_details),
                    'timestamp': time.time()
                }
                
                # 发送响应
                response_bytes = json.dumps(response, ensure_ascii=False).encode('utf-8')
                
                # 根据你的 TCPProtocol 实现发送数据
                # 方式1: 如果 tcp_protocol 有 send_to_client 方法
                if hasattr(tcp_protocol, 'send_to_client'):
                    # 需要 client_id，这里假设可以通过 client_addr 获取
                    client_id = f"{client_addr[0]}:{client_addr[1]}"
                    success = tcp_protocol.send_to_client(client_id, response_bytes)
                # 方式2: 如果 tcp_protocol 有 send_data 方法
                elif hasattr(tcp_protocol, 'send_data'):
                    success = tcp_protocol.send_data(response_bytes, target=client_addr)
                # 方式3: 直接使用 socket
                else:
                    # 查找客户端 socket
                    success = False
                    for client_id, client_info in tcp_protocol.clients.items():
                        if client_info.get('address') == client_addr:
                            client_info['socket'].send(response_bytes)
                            success = True
                            break
                
                if success:
                    self.logger.info(f"成功发送 {len(filenames)} 个文件列表给客户端 {client_addr}")
                    self.logger.info(f"目录: {upload_dir}")
                else:
                    self.logger.error(f"发送文件列表失败给客户端 {client_addr}")
                
            else:
                self.logger.warning(f"未知的消息类型: {msg_type}")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"解析客户端消息失败: {e}")
            # 发送错误响应
            error_response = json.dumps({
                'type': 'error',
                'message': f"无效的请求格式: {str(e)}",
                'timestamp': time.time()
            }).encode('utf-8')
            tcp_protocol.send_data(error_response, target=client_addr)
            
        except Exception as e:
            self.logger.error(f"处理文件列表请求失败: {e}")
            # 发送错误响应
            error_response = json.dumps({
                'type': 'error',
                'message': str(e),
                'timestamp': time.time()
            }).encode('utf-8')
            tcp_protocol.send_data(error_response, target=client_addr)


    def _display_server_files(self, response):
        """显示服务器返回的文件列表"""
        try:
            if response.get('type') == 'get_filelist':
                files = response.get('files', [])
                file_count = response.get('count', 0)
            
                if not files:
                    print("\n服务器 uploads 目录为空")
                    return True
            
                print("\n" + "=" * 60)
                print(f"服务器文件列表 (共 {file_count} 个文件)")
                print("=" * 60)
            
                for i, file_info in enumerate(files, 1):
                    if isinstance(file_info, dict):
                        # 显示详细信息
                        name = file_info.get('name', '未知')
                        size = file_info.get('size', 0)
                        size_str = self._format_size(size)
                        print(f"{i:3}. {name:<30} 大小: {size_str}")
                    else:
                        # 显示简单文件名
                        print(f"{i:3}. {file_info}")
            
                print("=" * 60)
                         
            elif response.get('type') == 'error':
                print(f"\n错误: {response.get('message', '未知错误')}")
                return False
            
            else:
                print(f"\n未知的响应类型: {response}")
                return False
            
        except Exception as e:
            self.logger.error(f"显示文件列表失败: {e}")
            return False

    def _receive_file_data(self, tcp_protocol: TCPProtocol, filename: str, header_response: dict) -> bool:
        """接收TCP文件数据"""
        try:
            # 获取文件信息
            file_size = header_response.get('file_size', 0)
            
            self.logger.info(f"准备接收文件: {filename}, 大小: {file_size} 字节")
            
            if file_size <= 0:
                self.logger.error(f"无效的文件大小: {file_size}")
                return False
            
            data_dir = self.file_ops.get_data_directory()  # 新增
            download_dir = os.path.join(data_dir, "downloads")  # ✅ 改为 uploads

            # 确保目录存在
            os.makedirs(download_dir, exist_ok=True)
        
            # 构建保存路径
            save_path = os.path.join(download_dir, filename)
        
            self.logger.info(f"下载目录: {download_dir}")
            self.logger.info(f"保存路径: {save_path}")

            # 确保父目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
            self.logger.info(f"开始接收文件: {filename} ({self._format_size(file_size)})")
            
            # 设置socket超时
            original_timeout = tcp_protocol.socket.gettimeout()
            tcp_protocol.socket.settimeout(5.0)  # 5秒超时，避免长时间等待
            
            try:
                # 接收文件数据
                received_bytes = 0
                last_progress = 0
                retry_count = 0
                max_retries = 3
                
                with open(save_path, 'wb') as f:
                    while received_bytes < file_size and retry_count < max_retries:
                        try:
                            # 接收数据块
                            remaining = file_size - received_bytes
                            chunk_size = min(8192, remaining)
                            chunk = tcp_protocol.socket.recv(chunk_size)
                            
                            if not chunk:
                                retry_count += 1
                                self.logger.warning(f"收到空数据，重试 {retry_count}/{max_retries}")
                                continue
                            
                            f.write(chunk)
                            received_bytes += len(chunk)
                            retry_count = 0  # 重置重试计数
                            
                            # 显示进度
                            progress = (received_bytes / file_size) * 100
                            if progress - last_progress >= 5 or received_bytes == file_size:
                                print(f"\r下载进度: {progress:.1f}% ({self._format_size(received_bytes)}/{self._format_size(file_size)})", end='')
                                last_progress = progress
                                
                        except socket.timeout:
                            retry_count += 1
                            self.logger.warning(f"接收超时，重试 {retry_count}/{max_retries}")
                            continue
                        except Exception as e:
                            self.logger.error(f"接收数据出错: {e}")
                            break
                                
            except Exception as e:
                self.logger.error(f"接收文件失败: {e}")
                return False
            finally:
                tcp_protocol.socket.settimeout(original_timeout)  # 恢复超时设置
                    
            print()  # 换行
                    
            if received_bytes == file_size:
                self.logger.info(f"✅ 文件接收完成: {filename}")
                print(f"\n✅ 文件下载完成: {save_path}")
                return True
            else:
                self.logger.error(f"❌ 文件下载不完整: {received_bytes}/{file_size}")
                print(f"\n❌ 文件下载不完整: {save_path}")
                return False
                    
        except Exception as e:
            self.logger.error(f"接收文件失败: {e}")
            print(f"\n❌ 文件接收失败: {str(e)}")
            return False

    def download_file_tcp(self, file_path: str, tcp_protocol: TCPProtocol,target: tuple = None) -> bool:
        try:
            filename = file_path
            data_dir = self.file_ops.get_data_directory()
            download_dir = os.path.join(data_dir, "downloads")
            os.makedirs(download_dir, exist_ok=True)
            local_path = os.path.join(download_dir, filename)
            transfer_id = f"download_{int(time.time())}_{random.randint(1000, 9999)}"
        
            header = {
            'type': 'download_request',
            'filename': filename,
            'transfer_id': transfer_id,
            'timestamp': time.time()
            }
        
            self.logger.info(f"请求下载文件: {filename}")
          
            # 发送下载请求
            if not tcp_protocol.sendall(json.dumps(header).encode('utf-8')):
                self.logger.error("发送下载请求失败")
                return False
            
            # 接收服务器响应
            response_data = b''
            original_timeout = tcp_protocol.socket.gettimeout()
            tcp_protocol.socket.settimeout(30.0)  # 30秒超时
            
            try:
                while True:
                    chunk = tcp_protocol.socket.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                    
                    # 尝试解析响应
                    try:
                        response_str = response_data.decode('utf-8')
                        response = json.loads(response_str)
                        
                        # 如果收到文件开始传输的消息
                        if response.get('type') == 'file_transfer_start':
                            # 接收文件数据
                            return self._receive_file_data(tcp_protocol, filename, response)
                        elif response.get('type') == 'error':
                            print(f"\n❌ 服务器错误: {response.get('message', '未知错误')}")
                            return False
                            
                    except json.JSONDecodeError:
                        # 继续接收数据
                        continue
                    except UnicodeDecodeError:
                        # 可能是文件数据，继续接收
                        continue
                        
            except socket.timeout:
                self.logger.error("下载超时")
                return False
            finally:
                tcp_protocol.socket.settimeout(original_timeout)
                
            return False
            
        except Exception as e:
            self.logger.error(f"下载文件失败: {e}")
            print(f"\n❌ 下载失败: {str(e)}")
            return False

    def send_file_tcp(self, file_path: str, tcp_protocol: TCPProtocol, target: tuple = None) -> bool:
        """通过TCP发送文件"""
        import time
        self._last_sent_file = {
        'path': file_path,
        'time': time.time()
        }
        PACKET_DELIMITER = b'\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF'
        transfer_info = None
        
        try:
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            print(f"文件大小: {file_size} 字节")
            
            transfer_info = self.prepare_file_transfer(file_path, "TCP")
            if not transfer_info:
                return False
                
            transfer_id = transfer_info['id']
            transfer_info['status'] = 'sending'
            start_time = time.perf_counter()
            transfer_info['start_time'] = start_time
            
            # 计算总块数
            chunk_size = 1028
            total_chunks = (file_size + chunk_size - 1) // chunk_size
            print(f"预计总块数: {total_chunks}")
            
            # 发送文件信息头
            header = {
                'type': 'upload',
                'data': transfer_info['file_info'],
                'transfer_id': transfer_id
            }

            header_data = json.dumps(header, ensure_ascii = False).encode('utf-8')  
            complete_packet = header_data + PACKET_DELIMITER
        
            self.logger.info(f"发送文件头，大小: {len(header_data)} 字节")
            time.sleep(0.001)
            if not tcp_protocol.sendall(complete_packet):
                self.logger.error("发送文件信息头失败")
                return False
            
            # 发送文件数据
            bytes_sent = 0
            chunk_count = 0
            sent_chunks = set()  # 跟踪已发送的块
            
            for chunk in self.file_ops.read_file_chunks(file_path, 1028):
                chunk_count += 1
                
                # 记录已发送的块
                sent_chunks.add(chunk_count)
                
                chunk_base64 = base64.b64encode(chunk).decode('utf-8')
                chunk_header = {
                    'type': 'file_chunk',
                    'transfer_id': transfer_info['id'],
                    'chunk_size': len(chunk),
                    'chunk_index': chunk_count,
                    'total_chunks': total_chunks,  # 添加总块数
                    'content': chunk_base64
                }
                chunk_data = json.dumps(chunk_header, ensure_ascii=False).encode('utf-8')
                complete_chunk = chunk_data + PACKET_DELIMITER
            
                # 发送块头信息
                if not tcp_protocol.sendall(complete_chunk):
                    self.logger.error(f"发送文件块 {chunk_count} 失败")
                    return False
                time.sleep(0.001)
                bytes_sent += len(chunk)
                transfer_info['bytes_transferred'] = bytes_sent
                
                # 每10个块输出一次进度
                if chunk_count % 10 == 0:
                    progress = (bytes_sent / file_size) * 100
                    print(f"发送进度: {progress:.1f}% ({bytes_sent}/{file_size}), 块 {chunk_count}/{total_chunks}")
            
            # 验证所有块是否都发送了
            if chunk_count != total_chunks:
                print(f"警告: 发送块数不匹配! 实际发送 {chunk_count}, 预期 {total_chunks}")
            
            print(f"发送完成: 共发送 {chunk_count} 个块，{bytes_sent} 字节")
            print(f"已发送块索引: {sorted(sent_chunks)}")
            
            # 检查是否有缺失的块
            missing_chunks = []
            for i in range(1, total_chunks + 1):
                if i not in sent_chunks:
                    missing_chunks.append(i)
            
            if missing_chunks:
                print(f"警告: 缺失的块: {missing_chunks}")
            
            # 发送传输完成信号
            completion_packet = {
                'type': 'transfer_complete',
                'transfer_id': transfer_id,
                'total_chunks': chunk_count,
                'total_size': bytes_sent,
                'file_size': file_size
            }
        
            completion_data = json.dumps(completion_packet, ensure_ascii=False).encode('utf-8')
            complete_completion = completion_data + PACKET_DELIMITER
            
            if not tcp_protocol.sendall(complete_completion):
                self.logger.error("发送传输完成信号失败")
                return False
            
            # 更新状态
            transfer_info['status'] = 'completed'
            transfer_info['end_time'] = time.time()
            end_time = time.perf_counter()
            duration = end_time - start_time
            transfer_info['total_chunks'] = chunk_count
            self.completed_transfers.append(transfer_info)
            
            speed = bytes_sent / duration if duration > 0 else 0
            
            self.logger.info(f"文件发送完成: {file_path}")
            self.logger.info(f"大小: {bytes_sent} 字节, 块数: {chunk_count}/{total_chunks}")
            self.logger.info(f"速度: {speed/1024:.2f} KB/s, 耗时: {duration:.2f}秒")
            
            return True
            
        except Exception as e:
            self.logger.error(f"发送文件失败: {e}")
            import traceback
            traceback.print_exc()
            if transfer_info:
                transfer_info['status'] = 'failed'
            return False
        
    def _send_file_data_to_client(self, client_addr: tuple, file_path: str, file_size: int, tcp_protocol: TCPProtocol) -> bool:
        """发送文件数据给客户端"""
        try:
            self.logger.info(f"开始发送文件给客户端 {client_addr}: {file_path}")
            
            # 获取客户端socket
            client_socket = None
            with tcp_protocol.client_lock:
                for client in tcp_protocol.clients:
                    try:
                        if isinstance(client, socket.socket):
                            peer_addr = client.getpeername()
                            if peer_addr == client_addr:
                                client_socket = client
                                break
                    except:
                        continue
            
            if not client_socket:
                self.logger.error(f"找不到客户端 {client_addr} 的socket")
                return False
            
            # 打开并发送文件
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                chunk_size = 8192
                
                while bytes_sent < file_size:
                    # 读取数据块
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    try:
                        # 发送数据块
                        client_socket.sendall(chunk)
                        bytes_sent += len(chunk)
                        
                        # 显示进度
                        if bytes_sent % (1024 * 1024) < chunk_size or bytes_sent == file_size:
                            progress = (bytes_sent / file_size) * 100
                            self.logger.info(f"发送进度: {progress:.1f}% ({self._format_size(bytes_sent)}/{self._format_size(file_size)})")
                            
                    except (ConnectionResetError, BrokenPipeError, socket.error) as e:
                        self.logger.error(f"发送数据时连接错误: {e}")
                        return False
            
            self.logger.info(f"文件发送完成: {bytes_sent} 字节")
            return bytes_sent == file_size
            
        except FileNotFoundError:
            self.logger.error(f"文件不存在: {file_path}")
            return False
        except Exception as e:
            self.logger.error(f"发送文件数据失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    def handle_download_request(self, data: bytes, client_addr: tuple, tcp_protocol: TCPProtocol) -> bool:
        """处理下载请求"""
        try:
            message = json.loads(data.decode('utf-8'))
            msg_type = message.get('type')
            
            if msg_type == 'download_request':
                filename = message.get('filename', '')
                transfer_id = message.get('transfer_id', '')
                
                if not filename:
                    self.logger.error("下载请求缺少文件名")
                    error_response = {
                        'type': 'error',
                        'message': '缺少文件名',
                        'timestamp': time.time()
                    }
                    tcp_protocol.send_data(json.dumps(error_response).encode('utf-8'), target=client_addr)
                    return False
                
                self.logger.info(f"处理下载请求: {filename} 来自 {client_addr}")
                
                # 获取文件路径
                data_dir = self.file_ops.get_data_directory()  # 新增
                upload_dir = os.path.join(data_dir, "uploads")  # 修改
                file_path = os.path.join(upload_dir, filename)
                
                # 检查文件是否存在
                if not os.path.exists(file_path):
                    self.logger.error(f"文件不存在: {file_path}")
                    error_response = {
                        'type': 'error',
                        'message': f'文件不存在: {filename}',
                        'timestamp': time.time()
                    }
                    tcp_protocol.send_data(json.dumps(error_response).encode('utf-8'), target=client_addr)
                    return False
                
                # 获取文件信息
                file_size = os.path.getsize(file_path)
                
                # 发送文件传输开始响应
                start_response = {
                    'type': 'file_transfer_start',
                    'filename': filename,
                    'file_size': file_size,
                    'transfer_id': transfer_id,
                    'timestamp': time.time()
                }
                
                start_response_bytes = json.dumps(start_response).encode('utf-8')
                
                # 使用send_data发送响应
                if not tcp_protocol.send_data(start_response_bytes, target=client_addr):
                    self.logger.error("发送开始响应失败")
                    return False
                
                self.logger.info(f"开始发送文件: {filename} ({self._format_size(file_size)})")
                
                # 等待一下确保客户端准备好接收
                time.sleep(0.1)
                
                # 发送文件数据
                return self._send_file_data_to_client(client_addr, file_path, file_size, tcp_protocol)
                
            else:
                self.logger.warning(f"未知的下载请求类型: {msg_type}")
                return False
                
        except json.JSONDecodeError as e:
            self.logger.error(f"解析下载请求失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"处理下载请求失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def receive_file_tcp(self, data: bytes, client_addr: tuple, tcp_protocol: TCPProtocol) -> bool:
        """通过TCP接收文件"""
        print(f"收到数据类型: {type(data)}, 长度: {len(data)}")
        print(f"前100字节: {data[:100]}")
        PACKET_DELIMITER = b'\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF'
        try:
            # 初始化客户端缓冲区
            client_key = str(client_addr)
            if not hasattr(self, '_client_buffers'):
                self._client_buffers = {}
            
            if client_key not in self._client_buffers:
                self._client_buffers[client_key] = b''
            
            # 添加到缓冲区
            self._client_buffers[client_key] += data
            
            # 获取当前缓冲
            buffer = self._client_buffers[client_key]
            
            # 按分隔符分割
            packets = buffer.split(PACKET_DELIMITER)
            
            # 处理完整的数据包
            processed_packets = []
            success = True
            
            for packet in packets:
                if len(packet) == 0:  # 跳过空包
                    continue
                    
                # 尝试处理这个包
                if self._process_single_packet(packet, client_addr, tcp_protocol):
                    processed_packets.append(packet)
                else:
                    success = False
            
            # 更新缓冲区（保留最后一个不完整的包）
            if packets and len(packets[-1]) > 0:
                # 如果最后一个包没被处理，保留它
                if packets[-1] not in processed_packets:
                    self._client_buffers[client_key] = packets[-1]
                else:
                    self._client_buffers[client_key] = b''
            else:
                self._client_buffers[client_key] = b''
            
            return success
            
        except Exception as e:
            self.logger.error(f"接收文件失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    def _process_single_packet(self, packet: bytes, client_addr: tuple, tcp_protocol: TCPProtocol) -> bool:
        """处理单个数据包（修复重复处理问题）"""
        try:
            print(f"处理数据包，长度: {len(packet)}")
            
            # 1. 提取JSON部分
            json_start = packet.find(b'{')
            json_end = packet.rfind(b'}')
                
            if json_start == -1 or json_end == -1:
                print(f"未找到完整的JSON数据")
                return False
                
            json_part = packet[json_start:json_end+1]
                
            # 2. 解码和解析JSON
            try:
                json_str = json_part.decode('utf-8', errors='ignore')
                message = json.loads(json_str)
                msg_type = message.get('type')
                print(f"成功解析JSON，消息类型: {msg_type}")
            except Exception as e:
                print(f"JSON处理失败: {e}")
                return False
                
            transfer_id = message.get('transfer_id')
                
            # 3. 处理不同类型的消息
            # 添加重传相关消息处理
            if msg_type == 'retransmit_ack':
                return self._handle_retransmit_ack(message, transfer_id, client_addr, tcp_protocol)
                    
            elif msg_type == 'retransmit_chunk':
                return self._handle_retransmit_chunk(message, transfer_id, client_addr, tcp_protocol)
                    
            elif msg_type == 'retransmit_complete':
                return self._handle_retransmit_complete(message, transfer_id, client_addr, tcp_protocol)
                    
            elif msg_type == 'upload':
                return self._handle_upload(message, transfer_id, client_addr)
                    
            elif msg_type == 'file_chunk':
                return self._handle_file_chunk_with_dedup(message, transfer_id, client_addr)
                    
            elif msg_type == 'transfer_complete':
                return self._handle_transfer_complete(message, transfer_id, client_addr, tcp_protocol)
                    
            elif msg_type == 'retransmit_request':
                return self.handle_retransmit_request(message, client_addr, tcp_protocol)
                    
            else:
                print(f"未知消息类型: {msg_type}")
                return False
                
        except Exception as e:
            print(f"处理数据包失败: {e}")
            import traceback
            traceback.print_exc()
            return False


    def _handle_retransmit_ack(self, message: dict, client_addr: tuple, tcp_protocol) -> bool:
        """处理重传确认"""
        transfer_id = message.get('transfer_id')
        
        if transfer_id in self.transfers:
            current_transfer = self.transfers[transfer_id]
            total_missing = message.get('total_missing', 0)
            print(f"收到重传确认，将重传 {total_missing} 个块")
            current_transfer['retransmit_ack_time'] = time.time()
        
        return True

    def _handle_retransmit_chunk(self, message: dict, client_addr: tuple, tcp_protocol) -> bool:
        """处理重传的块"""
        transfer_id = message.get('transfer_id')
        
        if transfer_id not in self.transfers:
            print(f"未知的传输ID: {transfer_id}")
            return False
        
        current_transfer = self.transfers[transfer_id]
        
        # 检查是否是缺失的块
        chunk_index = message.get('chunk_index')
        missing_chunks = current_transfer.get('missing_chunks', [])
        
        if chunk_index not in missing_chunks:
            print(f"警告: 收到非缺失块 {chunk_index} 的重传")
        
        # 使用现有的块处理逻辑
        return self._handle_file_chunk_with_dedup_and_order(message, transfer_id, client_addr)

    def _handle_transfer_complete(self, message: dict, transfer_id: str, client_addr: tuple, tcp_protocol: TCPProtocol) -> bool:
        """处理传输完成消息（修复统计）"""
        if not transfer_id or transfer_id not in self.transfers:
            print(f"未知的传输ID: {transfer_id}")
            return False
        
        current_transfer = self.transfers[transfer_id]
        
        # 获取发送端的信息
        total_chunks = message.get('total_chunks', 0)
        total_size = message.get('total_size', 0)
        
        if total_chunks > 0:
            current_transfer['expected_chunks'] = total_chunks
        
        if total_size > 0:
            current_transfer['total_bytes'] = total_size
        
        # 首先，尝试写入所有缓冲区中的块
        self._write_all_buffered_chunks(current_transfer)
        
        # 再次检查缓冲区（确保没有遗漏）
        if current_transfer.get('chunk_buffer'):
            print(f"警告: 传输完成但缓冲区仍有 {len(current_transfer['chunk_buffer'])} 个块")
            print(f"缓冲区内容: {sorted(current_transfer['chunk_buffer'].keys())}")
            # 再次尝试写入
            self._write_all_buffered_chunks(current_transfer)
        
        # 验证文件
        file_path = current_transfer.get('file_path')
        if file_path and os.path.exists(file_path):
            actual_size = os.path.getsize(file_path)
            expected_size = current_transfer['total_bytes']
            
            # 计算统计 - 使用最新数据
            received_chunks = len(current_transfer['processed_chunks'])
            expected_chunks = current_transfer.get('expected_chunks', 0)
            
            # 找出所有缺失的块
            missing_chunks = []
            if expected_chunks > 0:
                for i in range(1, expected_chunks + 1):
                    if i not in current_transfer['processed_chunks']:
                        missing_chunks.append(i)
            
            # 再次检查缓冲区是否有这些缺失块
            buffer_chunks = list(current_transfer.get('chunk_buffer', {}).keys())
            if buffer_chunks:
                print(f"警告: 仍有块在缓冲区中: {buffer_chunks}")
                for chunk_index in buffer_chunks:
                    if chunk_index in missing_chunks:
                        missing_chunks.remove(chunk_index)
                        print(f"  块 {chunk_index} 在缓冲区中但被标记为缺失")
            
            print(f"=== 最终传输统计 ===")
            print(f"文件: {current_transfer['file_info']['filename']}")
            print(f"预期大小: {expected_size} 字节")
            print(f"实际大小: {actual_size} 字节")
            print(f"预期块数: {expected_chunks}")
            print(f"接收块数: {received_chunks}")
            print(f"已处理块集合大小: {len(current_transfer['processed_chunks'])}")
            print(f"已处理块: {sorted(current_transfer['processed_chunks'])}")
            print(f"缺失块: {missing_chunks}")
            print(f"缓冲区剩余块: {sorted(current_transfer.get('chunk_buffer', {}).keys())}")
            
            # 验证文件完整性
            bytes_missing = expected_size - actual_size
            chunks_missing = len(missing_chunks)
            
            if bytes_missing == 0 and chunks_missing == 0:
                # 传输成功
                current_transfer['status'] = 'completed'
                current_transfer['end_time'] = time.time()
                
                duration = current_transfer['end_time'] - current_transfer['start_time']
                speed_kbps = (actual_size / 1024) / duration if duration > 0 else 0
                
                print(f"✅ 文件接收完成!")
                print(f"  大小: {actual_size} 字节")
                print(f"  耗时: {duration:.2f} 秒")
                print(f"  速度: {speed_kbps:.2f} KB/s")
                
                # 发送成功确认（检查连接是否有效）
                if self._is_connection_valid(tcp_protocol):
                    ack = {
                        'type': 'transfer_ack',
                        'transfer_id': transfer_id,
                        'status': 'success',
                        'received_size': actual_size,
                        'received_chunks': received_chunks
                    }
                    self._safe_send(tcp_protocol, json.dumps(ack).encode('utf-8'))
                else:
                    print(f"连接已断开，无法发送确认")
                
                # 清理
                self.completed_transfers.append(current_transfer.copy())
                del self.transfers[transfer_id]
                return True
            else:
                # 传输不完整
                print(f"❌ 传输不完整!")
                print(f"  缺失 {chunks_missing} 个块: {missing_chunks}")
                print(f"  缺失 {bytes_missing} 字节")
                
                # 如果有缺失块，请求重传
                if missing_chunks:
                    print(f"请求重传缺失的块: {missing_chunks}")
                    
                    # 检查连接是否有效
                    if not self._is_connection_valid(tcp_protocol):
                        print(f"连接已断开，无法发送重传请求")
                        current_transfer['status'] = 'failed_due_to_disconnection'
                        return False
                    
                    # 发送重传请求
                    retransmit_request = {
                        'type': 'retransmit_request',
                        'transfer_id': transfer_id,
                        'missing_chunks': missing_chunks,
                        'missing_bytes': bytes_missing
                    }
                    
                    # 使用安全发送
                    success = self._safe_send(tcp_protocol, json.dumps(retransmit_request).encode('utf-8'))
                    
                    if success:
                        print(f"✅ 已发送重传请求")
                        # 设置重传状态
                        current_transfer['retransmit_request_time'] = time.time()
                        current_transfer['retransmit_missing_chunks'] = missing_chunks.copy()
                        current_transfer['status'] = 'waiting_retransmit'
                        current_transfer['retry_count'] = current_transfer.get('retry_count', 0) + 1
                        
                        print(f"已发送第 {current_transfer['retry_count']} 次重传请求")
                        
                        # 限制重试次数
                        if current_transfer['retry_count'] >= 3:
                            print(f"已达到最大重试次数，传输失败")
                            current_transfer['status'] = 'failed'
                        return True
                    else:
                        print(f"❌ 发送重传请求失败")
                        current_transfer['status'] = 'failed'
                        return False
                else:
                    current_transfer['status'] = 'failed'
                    return False
        else:
            print(f"文件不存在: {file_path}")
            current_transfer['status'] = 'failed'
            return False

    def _is_connection_valid(self, tcp_protocol: TCPProtocol) -> bool:
        """检查TCP连接是否有效"""
        try:
            # 检查TCP协议对象是否存在且有sendall方法
            if not tcp_protocol:
                return False
            
            # 如果有socket属性，检查socket状态
            if hasattr(tcp_protocol, 'socket'):
                sock = tcp_protocol.socket
                if not sock:
                    return False
                
                # 简单检查socket是否可用
                # 注意：这只是一个基本的检查，不能保证100%准确
                return True
                
            return hasattr(tcp_protocol, 'sendall')
            
        except Exception as e:
            print(f"检查连接状态失败: {e}")
            return False

    def _safe_send(self, tcp_protocol: TCPProtocol, data: bytes) -> bool:
        """安全发送数据，避免连接错误"""
        try:
            if not self._is_connection_valid(tcp_protocol):
                print(f"连接无效，无法发送数据")
                return False
            
            # 添加分隔符
            PACKET_DELIMITER = b'\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF'
            complete_data = data + PACKET_DELIMITER
            
            # 尝试发送
            if hasattr(tcp_protocol, 'sendall'):
                success = tcp_protocol.sendall(complete_data)
                if success is False:
                    print(f"sendall返回失败")
                    return False
                return True
            else:
                print(f"tcp_protocol没有sendall方法")
                return False
                
        except ConnectionError as e:
            print(f"连接错误: {e}")
            return False
        except OSError as e:
            print(f"系统错误: {e}")
            return False
        except Exception as e:
            print(f"发送数据失败: {e}")
            return False
        
    def _handle_upload(self, message: dict, transfer_id: str, client_addr: tuple) -> bool:
        """处理上传消息"""
        if not transfer_id:
            print("upload消息缺少transfer_id")
            return False
        
        file_info = message.get('data')
        if not file_info:
            print("upload消息缺少data")
            return False
        
        # 检查是否已有传输记录
        if transfer_id in self.transfers:
            print(f"传输ID {transfer_id} 已存在，跳过")
            return True
        
        try:
            data_dir = self.file_ops.get_data_directory()  # 新增
            upload_dir = os.path.join(data_dir, "uploads")  # 修改
            os.makedirs(upload_dir, exist_ok=True)
        
            safe_filename = file_info['filename'].replace('/', '_').replace('\\', '_')
            file_path = os.path.join(upload_dir, safe_filename)
            
            # 删除已存在的文件（避免旧数据干扰）
            if os.path.exists(file_path):
                print(f"删除已存在的文件: {file_path}")
                os.remove(file_path)
            
            # 创建传输记录，添加processed_chunks集合
            self.transfers[transfer_id] = {
                'id': transfer_id,
                'file_info': file_info,
                'protocol': 'TCP',
                'status': 'receiving',
                'start_time': time.time(),
                'end_time': None,
                'bytes_transferred': 0,
                'total_bytes': file_info['size'],
                'client_addr': client_addr,
                'chunks_received': 0,
                'file_path': file_path,
                'processed_chunks': set(),  # 记录已处理的块索引
                'last_written_index': 0,    # 记录最后一个写入的块索引
                'expected_chunks': 0,       # 预期总块数
                'chunk_buffer': {},         # 块缓冲区
                'file_created': False       # 新增：标记文件是否已创建
            }
            
            print(f"[接收] 开始接收文件: {file_info['filename']}, 大小: {file_info['size']} 字节")
            return True
            
        except Exception as e:
            print(f"创建文件失败: {e}")
            return False
    
    def _handle_file_chunk_with_dedup(self, message: dict, transfer_id: str, client_addr: tuple) -> bool:
        """处理文件块消息（带重复检测和乱序处理）- 修复连接状态管理"""
        if not transfer_id:
            print("file_chunk消息缺少transfer_id")
            return False
            
        if transfer_id not in self.transfers:
            print(f"未知的传输ID: {transfer_id}")
            return False
        
        current_transfer = self.transfers[transfer_id]
        
        # 更新连接活跃状态
        current_transfer['connection_active'] = True
        current_transfer['last_activity_time'] = time.time()
        
        # 获取块索引
        chunk_index = message.get('chunk_index')
        if chunk_index is None:
            print(f"错误: 块索引缺失")
            return False
        
        # 检查是否已处理过这个块（已写入文件）
        if chunk_index in current_transfer['processed_chunks']:
            print(f"块 {chunk_index} 已处理过，跳过")
            return True
        
        # 检查是否已在缓冲区中（重要修复！）
        if 'chunk_buffer' in current_transfer and chunk_index in current_transfer['chunk_buffer']:
            print(f"块 {chunk_index} 已在缓冲区中，跳过重复接收")
            return True
        
        chunk_size = message.get('chunk_size', 0)
        base64_content = message.get('content', '')
        
        if not base64_content:
            print(f"[接收] 警告: 块内容为空")
            return False
        
        try:
            # 解码base64数据
            chunk_data = base64.b64decode(base64_content)
            actual_size = len(chunk_data)
            
            # 存储到缓冲区（不立即写入）
            if 'chunk_buffer' not in current_transfer:
                current_transfer['chunk_buffer'] = {}
            
            # 保存块数据到缓冲区
            current_transfer['chunk_buffer'][chunk_index] = {
                'data': chunk_data,
                'size': actual_size,
                'received_time': time.time()
            }
            
            print(f"收到块 {chunk_index}, 大小: {actual_size} 字节，存入缓冲区")
            
            # 尝试写入连续的块
            self._write_continuous_chunks(current_transfer)
            
            # 检查是否有待处理的重传请求
            if current_transfer.get('status') == 'waiting_retransmit':
                # 如果收到了缺失块，更新状态
                missing_chunks = current_transfer.get('retransmit_missing_chunks', [])
                if chunk_index in missing_chunks:
                    missing_chunks.remove(chunk_index)
                    print(f"收到缺失块 {chunk_index}，剩余缺失: {missing_chunks}")
                    
                    if not missing_chunks:
                        # 所有缺失块都已收到
                        print(f"✅ 所有缺失块都已收到，传输可以继续")
                        current_transfer['status'] = 'receiving'
            
            return True
            
        except Exception as e:
            print(f"❌ 处理文件块时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def _write_continuous_chunks(self, transfer):
        """写入连续的块"""
        file_path = transfer.get('file_path')
        if not file_path or 'chunk_buffer' not in transfer:
            return
        
        # 检查文件是否存在
        file_exists = os.path.exists(file_path)
        
        # 确定下一个应该写入的块索引
        next_index = 1
        if 'last_written_index' in transfer:
            next_index = transfer['last_written_index'] + 1
        
        chunks_written = 0
        
        while next_index in transfer['chunk_buffer']:
            # 获取块数据并从缓冲区移除
            chunk_info = transfer['chunk_buffer'].pop(next_index)
            chunk_data = chunk_info['data']
            
            # 确定写入模式
            mode = 'ab'
            if next_index == 1 and not file_exists:
                mode = 'wb'
                file_exists = True
            
            # 写入文件
            with open(file_path, mode) as f:
                f.write(chunk_data)
            
            print(f"写入块 {next_index}, 大小: {len(chunk_data)} 字节, 模式: {mode}")
            
            # 关键修复：立即标记为已处理
            transfer['processed_chunks'].add(next_index)
            transfer['last_written_index'] = next_index
            transfer['bytes_transferred'] += len(chunk_data)
            
            next_index += 1
            chunks_written += 1
        
        if chunks_written > 0:
            print(f"批量写入 {chunks_written} 个连续块")
            
            # 更新接收块数
            transfer['chunks_received'] = len(transfer['processed_chunks'])
            
            # 显示进度
            received = transfer['chunks_received']
            expected_chunks = transfer.get('expected_chunks', 0)
            total_bytes = transfer.get('total_bytes', 0)
            
            if total_bytes > 0 and received % 5 == 0:
                progress = (transfer['bytes_transferred'] / total_bytes) * 100
                print(f"接收进度: {progress:.1f}% ({transfer['bytes_transferred']}/{total_bytes})")
                
                if expected_chunks > 0:
                    # 找出缺失的块
                    missing = []
                    for i in range(1, expected_chunks + 1):
                        if i not in transfer['processed_chunks'] and i not in transfer.get('chunk_buffer', {}):
                            missing.append(i)
                    
                    print(f"已接收块: {received}/{expected_chunks}, 缺失块: {missing[:10]}{'...' if len(missing) > 10 else ''}")
                    print(f"缓冲区中的块: {sorted(transfer.get('chunk_buffer', {}).keys())}")

    def _handle_transfer_complete(self, message: dict, transfer_id: str, client_addr: tuple, tcp_protocol: TCPProtocol) -> bool:
        """处理传输完成消息（修复统计）"""
        if not transfer_id or transfer_id not in self.transfers:
            print(f"未知的传输ID: {transfer_id}")
            return False
        
        current_transfer = self.transfers[transfer_id]
        
        # 获取发送端的信息
        total_chunks = message.get('total_chunks', 0)
        total_size = message.get('total_size', 0)
        
        if total_chunks > 0:
            current_transfer['expected_chunks'] = total_chunks
        
        if total_size > 0:
            current_transfer['total_bytes'] = total_size
        
        # 首先，尝试写入所有缓冲区中的块
        self._write_all_buffered_chunks(current_transfer)
        
        # 再次检查缓冲区（确保没有遗漏）
        if current_transfer.get('chunk_buffer'):
            print(f"警告: 传输完成但缓冲区仍有 {len(current_transfer['chunk_buffer'])} 个块")
            print(f"缓冲区内容: {sorted(current_transfer['chunk_buffer'].keys())}")
            # 再次尝试写入
            self._write_all_buffered_chunks(current_transfer)
        
        # 验证文件
        file_path = current_transfer.get('file_path')
        if file_path and os.path.exists(file_path):
            actual_size = os.path.getsize(file_path)
            expected_size = current_transfer['total_bytes']
            
            # 计算统计 - 使用最新数据
            received_chunks = len(current_transfer['processed_chunks'])
            expected_chunks = current_transfer.get('expected_chunks', 0)
            
            # 找出所有缺失的块
            missing_chunks = []
            if expected_chunks > 0:
                for i in range(1, expected_chunks + 1):
                    if i not in current_transfer['processed_chunks']:
                        missing_chunks.append(i)
            
            # 再次检查缓冲区是否有这些缺失块
            buffer_chunks = list(current_transfer.get('chunk_buffer', {}).keys())
            if buffer_chunks:
                print(f"警告: 仍有块在缓冲区中: {buffer_chunks}")
                for chunk_index in buffer_chunks:
                    if chunk_index in missing_chunks:
                        missing_chunks.remove(chunk_index)
                        print(f"  块 {chunk_index} 在缓冲区中但被标记为缺失")
            
            print(f"=== 最终传输统计 ===")
            print(f"文件: {current_transfer['file_info']['filename']}")
            print(f"预期大小: {expected_size} 字节")
            print(f"实际大小: {actual_size} 字节")
            print(f"预期块数: {expected_chunks}")
            print(f"接收块数: {received_chunks}")
            print(f"已处理块集合大小: {len(current_transfer['processed_chunks'])}")
            print(f"已处理块: {sorted(current_transfer['processed_chunks'])}")
            print(f"缺失块: {missing_chunks}")
            print(f"缓冲区剩余块: {sorted(current_transfer.get('chunk_buffer', {}).keys())}")
            
            # 验证文件完整性 - 修复：允许小范围的大小误差
            size_difference = expected_size - actual_size
            chunks_missing = len(missing_chunks)
            
            # 允许1%的大小误差（1024字节以内）
            size_tolerance = max(1024, expected_size * 0.01)
            
            if abs(size_difference) <= size_tolerance and chunks_missing == 0:
                # 传输成功
                current_transfer['status'] = 'completed'
                current_transfer['end_time'] = time.time()
                
                duration = current_transfer['end_time'] - current_transfer['start_time']
                speed_kbps = (actual_size / 1024) / duration if duration > 0 else 0
                
                print(f"✅ 文件接收完成!")
                print(f"  大小: {actual_size} 字节 (允许误差: ±{size_tolerance:.0f} 字节)")
                print(f"  耗时: {duration:.2f} 秒")
                print(f"  速度: {speed_kbps:.2f} KB/s")
                
                # 发送成功确认
                try:
                    ack = {
                        'type': 'transfer_ack',
                        'transfer_id': transfer_id,
                        'status': 'success',
                        'received_size': actual_size,
                        'received_chunks': received_chunks
                    }
                    # 添加分隔符
                    PACKET_DELIMITER = b'\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF'
                    ack_data = json.dumps(ack).encode('utf-8') + PACKET_DELIMITER
                    tcp_protocol.sendall(ack_data)
                    print(f"✅ 已发送成功确认")
                except Exception as e:
                    print(f"发送成功确认失败: {e}")
                
                # 清理
                self.completed_transfers.append(current_transfer.copy())
                del self.transfers[transfer_id]
                return True
            else:
                # 传输不完整
                print(f"❌ 传输不完整!")
                if size_difference > 0:
                    print(f"  文件大小不足: 缺少 {size_difference} 字节")
                elif size_difference < 0:
                    print(f"  文件大小超出: 多出 {abs(size_difference)} 字节")
                
                if chunks_missing > 0:
                    print(f"  缺失 {chunks_missing} 个块: {missing_chunks}")
                
                # 如果有缺失块，请求重传
                if missing_chunks:
                    print(f"请求重传缺失的块: {missing_chunks}")
                    
                    try:
                        # 构建重传请求
                        retransmit_request = {
                            'type': 'retransmit_request',
                            'transfer_id': transfer_id,
                            'missing_chunks': missing_chunks,
                            'missing_bytes': abs(size_difference) if size_difference > 0 else 0
                        }
                        
                        # 发送重传请求
                        request_data = json.dumps(retransmit_request).encode('utf-8')
                        PACKET_DELIMITER = b'\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF'
                        complete_request = request_data + PACKET_DELIMITER
                        
                        if tcp_protocol.sendall(complete_request):
                            print(f"✅ 已发送重传请求")
                            current_transfer['retransmit_request_time'] = time.time()
                            current_transfer['retransmit_missing_chunks'] = missing_chunks.copy()
                            current_transfer['status'] = 'waiting_retransmit'
                            current_transfer['retry_count'] = current_transfer.get('retry_count', 0) + 1
                            
                            print(f"已发送第 {current_transfer['retry_count']} 次重传请求")
                            
                            # 限制重试次数
                            if current_transfer['retry_count'] >= 3:
                                print(f"已达到最大重试次数，传输失败")
                                current_transfer['status'] = 'failed'
                            return True
                        else:
                            print(f"❌ 发送重传请求失败")
                            current_transfer['status'] = 'failed'
                            return False
                            
                    except Exception as e:
                        print(f"发送重传请求出错: {e}")
                        current_transfer['status'] = 'failed'
                        return False
                else:
                    # 只有大小问题，没有缺失块
                    print(f"文件大小不匹配但所有块都已接收")
                    current_transfer['status'] = 'size_mismatch'
                    return False
        else:
            print(f"文件不存在: {file_path}")
            current_transfer['status'] = 'failed'
            return False
                
    def _write_all_buffered_chunks(self, transfer):
        """写入所有缓冲区的块（修复统计更新）"""
        file_path = transfer.get('file_path')
        if not file_path or 'chunk_buffer' not in transfer:
            return
        
        # 按索引排序
        sorted_indices = sorted(transfer['chunk_buffer'].keys())
        
        if not sorted_indices:
            return
        
        print(f"准备写入所有缓冲区的 {len(sorted_indices)} 个块: {sorted_indices}")
        
        # 检查文件是否存在以及当前大小
        file_exists = os.path.exists(file_path)
        current_size = 0
        if file_exists:
            current_size = os.path.getsize(file_path)
            print(f"文件当前大小: {current_size} 字节")
        
        chunks_written = 0
        total_bytes_written = 0
        
        for chunk_index in sorted_indices:
            # 关键修复：跳过已经处理过的块
            if chunk_index in transfer['processed_chunks']:
                print(f"跳过已处理的块 {chunk_index}，从缓冲区移除")
                # 从缓冲区移除但不再写入
                transfer['chunk_buffer'].pop(chunk_index, None)
                continue
                
            if chunk_index in transfer['chunk_buffer']:
                chunk_info = transfer['chunk_buffer'].pop(chunk_index)
                chunk_data = chunk_info['data']
                
                # 确定写入模式
                mode = 'ab'
                if chunk_index == 1 and not file_exists:
                    mode = 'wb'
                
                # 写入文件
                with open(file_path, mode) as f:
                    f.write(chunk_data)
                
                print(f"写入缓冲块 {chunk_index}, 大小: {len(chunk_data)} 字节，模式: {mode}")
                
                # 立即更新统计！
                transfer['last_written_index'] = max(transfer.get('last_written_index', 0), chunk_index)
                transfer['processed_chunks'].add(chunk_index)
                transfer['bytes_transferred'] += len(chunk_data)
                
                chunks_written += 1
                total_bytes_written += len(chunk_data)
        
        print(f"完成写入 {chunks_written} 个缓冲区块，共 {total_bytes_written} 字节")
        print(f"当前已处理块集合: {sorted(transfer['processed_chunks'])}")
        
        # 更新接收块数
        transfer['chunks_received'] = len(transfer['processed_chunks'])
        
        # 清理空的缓冲区
        if not transfer['chunk_buffer']:
            print(f"缓冲区已清空")

    def handle_retransmit_request(self, message: dict, client_addr: tuple, tcp_protocol) -> bool:
        """处理重传请求"""
        try:
            transfer_id = message.get('transfer_id')
            missing_chunks = message.get('missing_chunks', [])
            
            if not transfer_id or not missing_chunks:
                print(f"无效的重传请求")
                return False
            
            print(f"收到重传请求: 传输ID {transfer_id}, 缺失块 {missing_chunks}")
            
            # 1. 查找最近发送的文件
            if not hasattr(self, '_last_sent_file'):
                print(f"没有找到最近发送的文件记录")
                return False
            
            file_path = self._last_sent_file.get('path', '')
            if not os.path.exists(file_path):
                print(f"文件不存在: {file_path}")
                return False
            
            # 检查连接是否有效
            if not self._is_connection_valid(tcp_protocol):
                print(f"连接已断开，无法发送重传数据")
                return False
            
            # 2. 发送确认
            ack = {
                'type': 'retransmit_ack',
                'transfer_id': transfer_id,
                'status': 'started',
                'total_missing': len(missing_chunks)
            }
            
            if not self._safe_send(tcp_protocol, json.dumps(ack).encode('utf-8')):
                print(f"发送重传确认失败")
                return False
            
            # 3. 重传缺失的块
            chunk_size = 1028
            missing_chunks.sort()  # 按顺序重传
            
            for chunk_index in missing_chunks:
                # 读取指定块
                with open(file_path, 'rb') as f:
                    offset = (chunk_index - 1) * chunk_size
                    f.seek(offset)
                    chunk_data = f.read(chunk_size)
                    
                    if not chunk_data:
                        continue
                    
                    # 构建重传包
                    retransmit_packet = {
                        'type': 'retransmit_chunk',
                        'transfer_id': transfer_id,
                        'chunk_index': chunk_index,
                        'chunk_size': len(chunk_data),
                        'content': base64.b64encode(chunk_data).decode('utf-8'),
                        'is_retransmit': True
                    }
                    
                    # 安全发送
                    if not self._safe_send(tcp_protocol, json.dumps(retransmit_packet).encode('utf-8')):
                        print(f"重传块 {chunk_index} 失败")
                        return False
                    
                    print(f"重传块 {chunk_index}, 大小: {len(chunk_data)} 字节")
            
            # 4. 发送重传完成
            complete_msg = {
                'type': 'retransmit_complete',
                'transfer_id': transfer_id,
                'retransmitted_count': len(missing_chunks)
            }
            
            if not self._safe_send(tcp_protocol, json.dumps(complete_msg).encode('utf-8')):
                print(f"发送重传完成消息失败")
                return False
            
            print(f"✅ 重传完成: {len(missing_chunks)} 个块")
            return True
            
        except Exception as e:
            print(f"处理重传请求失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def send_file_list(self, client_addr, file_list, directory_info=None):
        """发送文件列表给客户端（兼容你的现有接口）"""
        try:
            import json
            import struct
            
        except Exception as e:
            self.logger.error(f"接收文件失败: {e}")
            return False
                
            # 构建响应消息（与你的格式保持一致）
            response = {
                'type': 'file_list' if not directory_info else 'directory_structure',
                'files': file_list,
                'count': len(file_list),
                'timestamp': time.time()
            }
            
            # 添加目录信息（如果需要）
            if directory_info:
                response.update({
                    'directory': directory_info.get('path', ''),
                    'total_size': directory_info.get('total_size', 0),
                    'directory_count': directory_info.get('directory_count', 0),
                    'file_count': directory_info.get('file_count', 0)
                })
            
            # 转换为JSON
            json_data = json.dumps(response, ensure_ascii=False)
            
            # 发送数据
            return self.send_data(json_data.encode('utf-8'), target=client_addr)
            
        except Exception as e:
            self.logger.error(f"发送文件列表失败: {e}")
            return False
    
    def send_directory_structure(self, client_addr, root_directory, recursive=True, include_hidden=False):
        """发送完整的目录结构"""
        import os
        import json
        
        def scan_directory(dir_path, base_path, current_level=0, max_depth=5):
            """递归扫描目录"""
            if current_level >= max_depth:
                return []
                
            result = []
            total_size = 0
            file_count = 0
            dir_count = 0
            
            try:
                for item in os.listdir(dir_path):
                    # 跳过隐藏文件（可选）
                    if not include_hidden and item.startswith('.'):
                        continue
                    
                    full_path = os.path.join(dir_path, item)
                    relative_path = os.path.relpath(full_path, base_path)
                    
                    try:
                        stat = os.stat(full_path)
                        is_dir = os.path.isdir(full_path)
                        
                        file_info = {
                            'name': item,
                            'path': relative_path.replace('\\', '/'),
                            'size': stat.st_size,
                            'modified': stat.st_mtime,
                            'is_directory': is_dir,
                            'permissions': stat.st_mode
                        }
                        
                        if is_dir:
                            dir_count += 1
                            file_info['type'] = 'directory'
                            if recursive:
                                file_info['children'] = scan_directory(
                                    full_path, base_path, current_level + 1, max_depth
                                )
                                file_info['item_count'] = len(file_info['children'])
                        else:
                            file_count += 1
                            total_size += stat.st_size
                            file_info['type'] = 'file'
                        
                        result.append(file_info)
                        
                    except (PermissionError, OSError) as e:
                        file_info = {
                            'name': item,
                            'path': relative_path.replace('\\', '/'),
                            'error': str(e),
                            'type': 'error'
                        }
                        result.append(file_info)
                        
            except PermissionError as e:
                return [{
                    'name': os.path.basename(dir_path),
                    'path': os.path.relpath(dir_path, base_path),
                    'error': f"无法访问目录: {e}",
                    'type': 'error'
                }]
            
            return result
        
        try:
            if not os.path.exists(root_directory):
                error_response = {
                    'type': 'error',
                    'message': f"目录不存在: {root_directory}"
                }
                return self.send_data(json.dumps(error_response).encode('utf-8'), target=client_addr)
            
            # 扫描目录
            directory_structure = scan_directory(root_directory, root_directory)
            
            # 计算统计信息
            total_size = sum(item.get('size', 0) for item in directory_structure if not item.get('is_directory'))
            file_count = sum(1 for item in directory_structure if not item.get('is_directory'))
            dir_count = sum(1 for item in directory_structure if item.get('is_directory'))
            
            # 构建响应
            response = {
                'type': 'directory_structure',
                'directory': root_directory,
                'files': directory_structure,
                'statistics': {
                    'total_items': len(directory_structure),
                    'file_count': file_count,
                    'directory_count': dir_count,
                    'total_size': total_size,
                    'total_size_human': self._format_size(total_size)
                },
                'timestamp': time.time()
            }
            
            # 发送响应
            return self.send_file_list(client_addr, directory_structure, {
                'path': root_directory,
                'total_size': total_size,
                'directory_count': dir_count,
                'file_count': file_count
            })
            
        except Exception as e:
            error_response = {
                'type': 'error',
                'message': f"扫描目录失败: {e}"
            }
            return self.send_data(json.dumps(error_response).encode('utf-8'), target=client_addr)
    
    def _format_size(self, size_bytes):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def send_data(self, data, target=None):
        """发送数据（需要根据你的实际实现调整）"""
        try:
            if target:
                # 如果target是客户端地址，找到对应的socket
                for client_id, client_info in self.clients.items():
                    if client_info.get('address') == target:
                        client_socket = client_info['socket']
                        client_socket.send(data)
                        return True
            else:
                # 广播给所有客户端
                for client_id, client_info in self.clients.items():
                    try:
                        client_socket = client_info['socket']
                        client_socket.send(data)
                    except:
                        continue
                return True
        except Exception as e:
            self.logger.error(f"发送数据失败: {e}")
            return False
    
    def get_transfer_status(self, transfer_id: str) -> Optional[Dict]:
        """获取传输状态"""
        return self.transfers.get(transfer_id)
    
    def get_all_transfers(self) -> List[Dict]:
        """获取所有传输记录"""
        active = list(self.transfers.values())
        return active + self.completed_transfers

    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
