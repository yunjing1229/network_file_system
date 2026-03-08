import json
import os
from typing import Dict, Any

class ConfigManager:    
    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8-sig') as f:
                    return json.load(f)
            else:
                return self._get_default_config()
        except Exception as e:
            print(f"配置加载失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置 - 演示字典使用"""
        return {
            "tcp_port": 8888,
            "udp_port": 8889,
            "buffer_size": 8192,
            "max_connections": 10,
            "upload_dir": "data/uploads",
            "download_dir": "data/downloads",
            "log_dir": "logs",
            "max_file_size": 104857600,
            "thread_pool_size": 5,
            "timeout": 30
        }
    
    def get(self, key: str, default=None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置值"""
        self.config[key] = value
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def __str__(self) -> str:
        """字符串表示 - 演示字符串处理"""
        config_info = []
        for key, value in self.config.items():
            config_info.append(f"{key}: {value}")
        return "\n".join(config_info)