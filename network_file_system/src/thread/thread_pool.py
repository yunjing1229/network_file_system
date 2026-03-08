import threading
import queue
import time
from typing import Callable, List, Dict, Any
from utils.logger import setup_logger

class ThreadPool:
    def __init__(self, num_threads: int = 5):
        self.num_threads = num_threads
        self.tasks = queue.Queue()
        self.threads: List[threading.Thread] = []
        self.is_running = False
        self.logger = setup_logger("ThreadPool")
        
        # 任务统计字典
        self.stats: Dict[str, Any] = {
            'tasks_completed': 0,
            'tasks_failed': 0,
            'tasks_queued': 0
        }
        self.stats_lock = threading.Lock()
    
    def start(self) -> None:
        """启动线程池"""
        self.is_running = True
        self.threads = []
        
        for i in range(self.num_threads):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"Worker-{i+1}",
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
        
        self.logger.info(f"线程池启动，工作线程数: {self.num_threads}")
    
    def stop(self) -> None:
        """停止线程池"""
        self.is_running = False
        
        # 添加停止信号
        for _ in range(self.num_threads):
            self.tasks.put(None)
        
        # 等待线程结束
        for thread in self.threads:
            thread.join(timeout=5)
        
        self.logger.info("线程池已停止")
    
    def submit_task(self, task_func: Callable, *args, **kwargs) -> None:
        """提交任务到线程池"""
        if not self.is_running:
            self.logger.warning("线程池未运行，无法提交任务")
            return
        
        self.tasks.put((task_func, args, kwargs))
        with self.stats_lock:
            self.stats['tasks_queued'] += 1
        
        self.logger.debug(f"任务已提交: {task_func.__name__}")
    
    def _worker_loop(self) -> None:
        """工作线程循环"""
        while self.is_running:
            try:
                task = self.tasks.get(timeout=1)
                if task is None:  # 停止信号
                    break
                
                task_func, args, kwargs = task
                
                try:
                    # 执行任务
                    task_func(*args, **kwargs)
                    with self.stats_lock:
                        self.stats['tasks_completed'] += 1
                    
                    self.logger.debug(f"任务完成: {task_func.__name__}")
                    
                except Exception as e:
                    with self.stats_lock:
                        self.stats['tasks_failed'] += 1
                    
                    self.logger.error(f"任务执行失败 {task_func.__name__}: {e}")
                
                finally:
                    self.tasks.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"工作线程异常: {e}")
    
    def wait_completion(self, timeout: float = None) -> bool:
        """等待所有任务完成"""
        try:
            self.tasks.join()
            return True
        except Exception as e:
            self.logger.error(f"等待任务完成时出错: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取线程池统计信息"""
        with self.stats_lock:
            stats = self.stats.copy()
            stats['active_threads'] = sum(1 for t in self.threads if t.is_alive())
            stats['pending_tasks'] = self.tasks.qsize()
        return stats
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()