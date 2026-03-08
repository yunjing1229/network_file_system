import logging
import os
from datetime import datetime
from typing import Optional

def setup_logger(name: str, log_dir: str = None, level=logging.INFO) -> logging.Logger:
    if log_dir is None:
        # 获取当前文件所在目录 (utils文件夹)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 获取src目录 (utils的父目录)
        src_dir = os.path.dirname(current_dir)
        # 获取项目根目录 (src的父目录)
        project_root = os.path.dirname(src_dir)
        # 在项目根目录创建logs文件夹
        log_dir = os.path.join(project_root, "logs")
    
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加handler
    if not logger.handlers:
        # 创建formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 文件handler
        log_file = os.path.join(log_dir, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 添加handler
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger
