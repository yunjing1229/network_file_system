import os
import hashlib
import json
from typing import Dict, List, Tuple, Optional
from utils.logger import setup_logger

class FileOperations:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            # 获取当前文件所在目录 (src/file_manager/)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 获取src目录 (file_manager的父目录)
            src_dir = os.path.dirname(current_dir)
            # 获取项目根目录 (src的父目录) - 这就是 network_file_system 目录
            project_root = os.path.dirname(src_dir)
            # data目录在项目根目录下
            self.base_dir = os.path.join(project_root, "data")
        else:
            self.base_dir = base_dir
        
        self.upload_dir = os.path.join(self.base_dir, "uploads")
        self.download_dir = os.path.join(self.base_dir, "downloads")
        
        self.logger = setup_logger("FileOperations")
        
        # 创建必要的目录
        self._create_directories()
        self._create_directories()
    
    def _create_directories(self) -> None:
        """创建必要的目录结构"""
        directories = [self.upload_dir, self.download_dir]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            self.logger.info(f"创建目录: {directory}")
    
    def list_files(self, directory: str) -> List[Dict[str, str]]:
        """列出目录中的文件 - 演示列表和字典使用"""
        try:
            dir_path = os.path.join(self.base_dir, directory)
            if not os.path.exists(dir_path):
                return []
            
            files_info = []
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                if os.path.isfile(file_path):
                    file_info = {
                        'name': filename,
                        'size': os.path.getsize(file_path),
                        'path': file_path,
                        'modified': os.path.getmtime(file_path),
                        
                    }
                    files_info.append(file_info)
            
            return files_info
        except Exception as e:
            self.logger.error(f"列出文件失败: {e}")
            return []
    
    def write_file_chunks(self, file_path: str,chunk_data: bytes,
                     chunk_index: int = 0, is_first_chunk: bool = False) -> bool:
        """写入文件块"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            mode = 'wb' if is_first_chunk else 'ab'
        
            with open(file_path, mode) as f:
                f.write(chunk_data)
            
            self.logger.info(f"文件写入成功: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"写入文件失败: {e}")
            return False

    def read_file_chunks(self, file_path: str, chunk_size: int = 4096) -> bytes:
        """读取文件块 - 生成器函数"""
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            self.logger.error(f"读取文件失败: {e}")
            raise

    def calculate_file_hash(self, file_path: str) -> Optional[str]:
        """计算文件哈希值 - 演示字符串处理"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            self.logger.error(f"计算文件哈希失败: {e}")
            return None
    
    def get_file_info(self, file_path: str) -> Dict[str, str]:
        """获取文件信息"""
        try:
            stat = os.stat(file_path)
            return {
                'filename': os.path.basename(file_path),
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'hash': self.calculate_file_hash(file_path) or 'unknown'
            }
        except Exception as e:
            self.logger.error(f"获取文件信息失败: {e}")
            return {}
    
    def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"文件已删除: {file_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"删除文件失败: {e}")
            return False
    
    def format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小显示 - 演示字符串处理"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def get_data_directory(self) -> str:
        """获取数据目录的绝对路径"""
        return self.base_dir
