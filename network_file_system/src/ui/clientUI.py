import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import time
from datetime import datetime
import sys

# 导入您的client类
# 获取当前UI文件所在目录
current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)  # ui目录
parent_dir = os.path.dirname(current_dir)    # 项目根目录

# 将项目根目录添加到 Python 搜索路径
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 现在尝试导入
try:
    from file_system.client_filesystem import ClientFileSystem
    CLIENT_AVAILABLE = True
    print(f"✅ 成功导入 ClientFileSystem from {parent_dir}")
except ImportError as e:
    print(f"❌ 导入 ClientFileSystem 失败: {e}")
    print(f"搜索路径: {sys.path}")
    CLIENT_AVAILABLE = False
    # 尝试另一种路径
    try:
        # 如果ui目录在src下
        src_dir = parent_dir
        sys.path.insert(0, src_dir)
        from file_system.client_filesystem import ClientFileSystem
        CLIENT_AVAILABLE = True
        print(f"✅ 通过src目录导入成功")
    except ImportError as e2:
        print(f"❌ 第二次导入尝试也失败: {e2}")
        CLIENT_AVAILABLE = False

class FileTransferClientGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("文件传输客户端")
        self.root.geometry("1000x700")
        
        self.client = None
        self.is_connected = False
        self.upload_in_progress = False
        self.download_in_progress = False
        
        # 上传统计
        self.upload_stats = {
            'start_time': None,
            'bytes_sent': 0,
            'total_bytes': 0,
            'last_update': 0
        }
        
        # 下载统计
        self.download_stats = {
            'start_time': None,
            'bytes_received': 0,
            'total_bytes': 0,
            'last_update': 0
        }
        
        # 服务器文件列表缓存
        self.server_files = []
        
        # 设置样式
        self.setup_styles()
        
        # 创建主界面
        self.create_widgets()
        
        # 启动UI更新线程
        self.running = True
        self.ui_update_thread = threading.Thread(target=self.update_ui_loop, daemon=True)
        self.ui_update_thread.start()
        
        # 连接服务器
        self.connect_to_server()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_styles(self):
        """设置UI样式"""
                                                                      
        style = ttk.Style()  # 创建一个ttk样式对象
        style.theme_use('clam')
        # 自定义样式
        style.configure('Title.TLabel', font=('微软雅黑', 14, 'bold'))
        style.configure('Section.TLabel', font=('微软雅黑', 11, 'bold'))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Highlight.TButton', font=('微软雅黑', 10, 'bold'))
        
        # 配置Treeview
        style.configure('Treeview', font=('微软雅黑', 10))
        style.configure('Treeview.Heading', font=('微软雅黑', 10, 'bold'))
    
    def create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 标题栏
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill='x', pady=(0, 10))
        
        title_label = ttk.Label(title_frame, text="📁 文件传输客户端", style='Title.TLabel')
        title_label.pack(side='left')
        
        # 连接状态
        self.connection_label = ttk.Label(title_frame, text="未连接", style='Error.TLabel')
        self.connection_label.pack(side='right', padx=10)
        
        # 创建Notebook（选项卡）
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # 创建四个选项卡
        self.create_upload_tab()
        self.create_download_tab()
        self.create_filelist_tab()
        self.create_status_tab()
    
    def create_upload_tab(self):
        """创建上传文件选项卡"""
        upload_frame = ttk.Frame(self.notebook)
        self.notebook.add(upload_frame, text='📤 文件上传')
        
        # 文件选择区域
        select_frame = ttk.LabelFrame(upload_frame, text="选择文件")
        select_frame.pack(fill='x', padx=10, pady=(10, 5))
        
        # 文件路径显示
        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(select_frame, textvariable=self.file_path_var)
        file_entry.pack(side='left', fill='x', expand=True, padx=(10, 5), pady=10)
        
        # 浏览按钮
        browse_btn = ttk.Button(select_frame, text="浏览...", command=self.browse_file)
        browse_btn.pack(side='right', padx=(0, 10), pady=10)
        
        # 上传控制区域
        control_frame = ttk.Frame(upload_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        self.upload_btn = ttk.Button(control_frame, text="开始上传", 
                                     command=self.start_upload, style='Highlight.TButton',
                                     state='disabled')
        self.upload_btn.pack(side='left', padx=5)
        
        self.cancel_upload_btn = ttk.Button(control_frame, text="取消上传",
                                           command=self.cancel_upload, state='disabled')
        self.cancel_upload_btn.pack(side='left', padx=5)
        
        # 上传进度
        progress_frame = ttk.LabelFrame(upload_frame, text="上传进度")
        progress_frame.pack(fill='x', padx=10, pady=(5, 10))
        
        # 进度条
        self.upload_progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.upload_progress.pack(fill='x', padx=10, pady=(10, 5))
        
        # 进度标签
        self.upload_status = ttk.Label(progress_frame, text="等待上传...")
        self.upload_status.pack(pady=(0, 5))
        
        # 传输信息网格
        info_frame = ttk.Frame(progress_frame)
        info_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        # 第一行
        ttk.Label(info_frame, text="文件:").grid(row=0, column=0, sticky='w', pady=2)
        self.file_name_label = ttk.Label(info_frame, text="未选择")
        self.file_name_label.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(info_frame, text="大小:").grid(row=0, column=2, sticky='w', pady=2, padx=(20, 0))
        self.file_size_label = ttk.Label(info_frame, text="0 字节")
        self.file_size_label.grid(row=0, column=3, sticky='w', padx=5, pady=2)
        
        # 第二行
        ttk.Label(info_frame, text="已传输:").grid(row=1, column=0, sticky='w', pady=2)
        self.transferred_label = ttk.Label(info_frame, text="0 字节")
        self.transferred_label.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(info_frame, text="进度:").grid(row=1, column=2, sticky='w', pady=2, padx=(20, 0))
        self.upload_percent_label = ttk.Label(info_frame, text="0%")
        self.upload_percent_label.grid(row=1, column=3, sticky='w', padx=5, pady=2)
        
        # 第三行
        ttk.Label(info_frame, text="速度:").grid(row=2, column=0, sticky='w', pady=2)
        self.upload_speed_label = ttk.Label(info_frame, text="0 KB/s")
        self.upload_speed_label.grid(row=2, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(info_frame, text="剩余时间:").grid(row=2, column=2, sticky='w', pady=2, padx=(20, 0))
        self.upload_eta_label = ttk.Label(info_frame, text="--")
        self.upload_eta_label.grid(row=2, column=3, sticky='w', padx=5, pady=2)

    def create_download_tab(self):
        """创建下载文件选项卡"""
        download_frame = ttk.Frame(self.notebook)
        self.notebook.add(download_frame, text='📥 文件下载')
        
        # 文件列表区域
        list_frame = ttk.LabelFrame(download_frame, text="服务器文件列表 (data/uploads/)")
        list_frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))
        
        # 工具栏
        toolbar = ttk.Frame(list_frame)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(toolbar, text="当前目录:").pack(side='left', padx=(0, 5))
        self.current_dir_label = ttk.Label(toolbar, text="data/uploads/", font=('微软雅黑', 9, 'bold'))
        self.current_dir_label.pack(side='left')
        
        # 创建Treeview
        columns = ('文件名', '大小', '修改时间', '类型')
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # 设置列
        column_configs = {
            '文件名': {'width': 300, 'anchor': 'w', 'stretch': True},
            '大小': {'width': 100, 'anchor': 'center', 'stretch': False},
            '修改时间': {'width': 150, 'anchor': 'center', 'stretch': False},
            '类型': {'width': 80, 'anchor': 'center', 'stretch': False}
        }
        
        for col in columns:
            self.file_tree.heading(col, text=col)
            config = column_configs.get(col, {'width': 100, 'anchor': 'center'})
            self.file_tree.column(col, **config)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.file_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y', padx=(0, 5), pady=5)
        
        # 绑定选择事件
        self.file_tree.bind('<<TreeviewSelect>>', self.on_file_selected)
        self.file_tree.bind('<Double-1>', self.on_file_double_click)
        
        # 控制区域
        control_frame = ttk.Frame(download_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        # 左侧按钮组
        left_btn_frame = ttk.Frame(control_frame)
        left_btn_frame.pack(side='left')
        
        refresh_btn = ttk.Button(left_btn_frame, text="🔄 刷新列表", 
                                command=self.refresh_file_list, width=15)
        refresh_btn.pack(side='left', padx=5)
        
        # 路径导航按钮
        nav_btn_frame = ttk.Frame(control_frame)
        nav_btn_frame.pack(side='left', padx=20)
        
        ttk.Button(nav_btn_frame, text="⬆️ 上一级", 
                  command=self.navigate_to_parent, width=10).pack(side='left', padx=2)
        
        # 右侧按钮组
        right_btn_frame = ttk.Frame(control_frame)
        right_btn_frame.pack(side='right')
        
        self.download_btn = ttk.Button(right_btn_frame, text="⬇️ 下载选中文件", 
                                      command=self.start_download, style='Highlight.TButton',
                                      state='disabled', width=15)
        self.download_btn.pack(side='left', padx=5)
        
        self.cancel_download_btn = ttk.Button(right_btn_frame, text="取消下载",
                                             command=self.cancel_download, state='disabled', width=10)
        self.cancel_download_btn.pack(side='left', padx=5)
        
        # 下载进度
        progress_frame = ttk.LabelFrame(download_frame, text="下载进度")
        progress_frame.pack(fill='x', padx=10, pady=(5, 10))
        
        # 进度条
        self.download_progress = ttk.Progressbar(progress_frame, mode='determinate', length=100)
        self.download_progress.pack(fill='x', padx=10, pady=(10, 5))

        self.download_status = ttk.Label(progress_frame, text="等待下载...", font=('微软雅黑', 9))
        self.download_status.pack(pady=(0, 10))

        
        # 状态标签
        status_frame = ttk.Frame(progress_frame)
        status_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        # 第一行：文件信息和进度
        file_info_frame = ttk.Frame(status_frame)
        file_info_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(file_info_frame, text="文件:", width=8).pack(side='left')
        self.download_file_label = ttk.Label(file_info_frame, text="无", foreground='blue')
        self.download_file_label.pack(side='left', padx=(0, 20))
        
        ttk.Label(file_info_frame, text="进度:", width=8).pack(side='left')
        self.download_percent_label = ttk.Label(file_info_frame, text="0%", font=('微软雅黑', 10, 'bold'))
        self.download_percent_label.pack(side='left', padx=(0, 20))
        
        ttk.Label(file_info_frame, text="大小:", width=8).pack(side='left')
        self.download_size_label = ttk.Label(file_info_frame, text="0 字节")
        self.download_size_label.pack(side='left')
        
        # 第二行：传输统计
        stats_frame = ttk.Frame(status_frame)
        stats_frame.pack(fill='x')
        
        ttk.Label(stats_frame, text="已下载:", width=8).pack(side='left')
        self.downloaded_label = ttk.Label(stats_frame, text="0 字节")
        self.downloaded_label.pack(side='left', padx=(0, 20))
        
        ttk.Label(stats_frame, text="速度:", width=8).pack(side='left')
        self.download_speed_label = ttk.Label(stats_frame, text="0 KB/s")
        self.download_speed_label.pack(side='left', padx=(0, 20))
        
        ttk.Label(stats_frame, text="剩余时间:", width=8).pack(side='left')
        self.download_eta_label = ttk.Label(stats_frame, text="--")
        self.download_eta_label.pack(side='left')
    
    def create_filelist_tab(self):
        """创建文件列表选项卡"""
        filelist_frame = ttk.Frame(self.notebook)
        self.notebook.add(filelist_frame, text='📋 文件列表')
        
        # 标题
        title_label = ttk.Label(filelist_frame, text="服务器文件管理 (data/uploads/)", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # 控制面板
        control_panel = ttk.Frame(filelist_frame)
        control_panel.pack(fill='x', padx=20, pady=(0, 10))
        
        # 路径信息
        path_frame = ttk.Frame(control_panel)
        path_frame.pack(side='left', fill='x', expand=True)
        
        ttk.Label(path_frame, text="当前目录:").pack(side='left')
        server_path_label = ttk.Label(path_frame, text="data/uploads/", 
                                     font=('微软雅黑', 9, 'bold'), foreground='blue')
        server_path_label.pack(side='left', padx=5)
        
        # 按钮区域
        btn_frame = ttk.Frame(control_panel)
        btn_frame.pack(side='right')
        
        # 刷新按钮（保存引用以便后续禁用/启用）
        self.server_refresh_btn = ttk.Button(btn_frame, text="🔄 刷新列表", 
                                            command=self.refresh_server_file_list,
                                            width=12)
        self.server_refresh_btn.pack(side='left', padx=2)
        
        # 删除按钮
        delete_btn = ttk.Button(btn_frame, text="🗑️ 删除文件", 
                               command=self.delete_selected_file,
                               width=12)
        delete_btn.pack(side='left', padx=2)
        
        # 下载按钮
        download_btn = ttk.Button(btn_frame, text="⬇️ 下载到本地", 
                                 command=self.start_download,
                                 width=12)
        download_btn.pack(side='left', padx=2)
        
        # 文件列表
        list_frame = ttk.LabelFrame(filelist_frame, text="服务器文件列表")
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('文件名', '大小', '修改时间', '类型')
        self.server_file_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # 设置列
        column_configs = {
            '文件名': {'width': 350, 'anchor': 'w'},
            '大小': {'width': 120, 'anchor': 'center'},
            '修改时间': {'width': 150, 'anchor': 'center'},
            '类型': {'width': 80, 'anchor': 'center'}
        }
        
        for col in columns:
            self.server_file_tree.heading(col, text=col)
            config = column_configs.get(col, {'width': 100})
            self.server_file_tree.column(col, **config)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.server_file_tree.yview)
        self.server_file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.server_file_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y', padx=5, pady=5)
        
        # 状态信息
        self.filelist_status = ttk.Label(filelist_frame, text="点击'刷新列表'获取文件", foreground='gray')
        self.filelist_status.pack(pady=5)
        
        # 绑定双击事件（查看文件详情）
        self.server_file_tree.bind('<Double-1>', self.on_file_double_click)
        
        # 自动刷新一次
        if self.is_connected:
            self.root.after(1000, self.refresh_server_file_list)
    
    def create_status_tab(self):
        """创建状态选项卡"""
        status_frame = ttk.Frame(self.notebook)
        self.notebook.add(status_frame, text='📊 系统状态')
        
        # 标题
        title_label = ttk.Label(status_frame, text="系统状态", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # 连接状态
        conn_frame = ttk.LabelFrame(status_frame, text="连接状态")
        conn_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(conn_frame, text="服务器地址:").grid(row=0, column=0, sticky='w', pady=5, padx=10)
        self.server_addr_label = ttk.Label(conn_frame, text="169.254.150.106:8888")
        self.server_addr_label.grid(row=0, column=1, sticky='w', pady=5, padx=10)
        
        ttk.Label(conn_frame, text="连接状态:").grid(row=1, column=0, sticky='w', pady=5, padx=10)
        self.connection_status_label = ttk.Label(conn_frame, text="离线", style='Error.TLabel')
        self.connection_status_label.grid(row=1, column=1, sticky='w', pady=5, padx=10)
        
        # 传输统计
        stats_frame = ttk.LabelFrame(status_frame, text="传输统计")
        stats_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(stats_frame, text="总上传文件:").grid(row=0, column=0, sticky='w', pady=5, padx=10)
        self.total_upload_label = ttk.Label(stats_frame, text="0")
        self.total_upload_label.grid(row=0, column=1, sticky='w', pady=5, padx=10)
        
        ttk.Label(stats_frame, text="总下载文件:").grid(row=1, column=0, sticky='w', pady=5, padx=10)
        self.total_download_label = ttk.Label(stats_frame, text="0")
        self.total_download_label.grid(row=1, column=1, sticky='w', pady=5, padx=10)
        
        ttk.Label(stats_frame, text="当前连接数:").grid(row=2, column=0, sticky='w', pady=5, padx=10)
        self.connection_count_label = ttk.Label(stats_frame, text="0")
        self.connection_count_label.grid(row=2, column=1, sticky='w', pady=5, padx=10)
        
        # 操作日志
        log_frame = ttk.LabelFrame(status_frame, text="操作日志")
        log_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        self.log_text = tk.Text(log_frame, height=15, font=('微软雅黑', 9))
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y', padx=5, pady=5)
        
        # 清空日志按钮
        clear_btn = ttk.Button(status_frame, text="清空日志", command=self.clear_log)
        clear_btn.pack(pady=5)

    def on_file_double_click(self, event):
        """文件双击事件（进入目录）"""
        try:
            selection = self.file_tree.selection()
            if not selection:
                return
            
            item = self.file_tree.item(selection[0])
            values = item['values']
            
            # 获取完整路径（如果有保存的话）
            full_path = None
            if hasattr(self, 'selected_file_info') and self.selected_file_info:
                full_path = self.selected_file_info.get('full_path')
            
            # 如果没有保存完整路径，尝试从当前路径和文件名构建
            if not full_path:
                current_path = getattr(self, 'current_download_path', 'data/uploads/')
                filename = values[0] if values else ''
                
                # 检查是否是目录（类型列是第4列）
                if len(values) > 3 and values[3] == "📁 目录":
                    # 如果是目录，双击进入
                    if current_path.endswith('/'):
                        new_path = f"{current_path}{filename}/"
                    else:
                        new_path = f"{current_path}/{filename}/"
                    
                    # 更新当前目录
                    self.current_download_path = new_path
                    self.current_dir_label.config(text=new_path)
                    
                    # 刷新该目录的文件列表
                    self.refresh_file_list(new_path)
                    self.log_message(f"进入目录: {new_path}")
                else:
                    # 如果是文件，双击触发下载
                    self.log_message(f"双击文件: {filename}")
                    # 可以选择自动开始下载，这里只是记录
            else:
                # 如果有完整路径信息
                self.log_message(f"双击: {full_path}")
                
        except Exception as e:
            self.log_message(f"双击事件错误: {e}", "error")

    def navigate_to_parent(self):
        """导航到上一级目录"""
        try:
            # 获取当前目录
            current_path = getattr(self, 'current_download_path', 'data/uploads/')
            
            if not current_path or current_path == "data/uploads/" or current_path == "/":
                # 已经在根目录
                self.log_message("已经在根目录")
                return
            
            # 计算上一级目录
            # 移除末尾的斜杠
            if current_path.endswith('/'):
                current_path = current_path.rstrip('/')
            
            # 分割路径
            parts = current_path.split('/')
            
            # 构建上一级目录
            if len(parts) > 1:
                parent_path = '/'.join(parts[:-1])
                if parent_path:  # 如果不是空路径
                    parent_path += '/'
                else:
                    parent_path = 'data/uploads/'  # 回到默认目录
            else:
                parent_path = 'data/uploads/'
            
            # 更新当前目录
            self.current_download_path = parent_path
            
            # 更新UI显示
            if hasattr(self, 'current_dir_label'):
                self.current_dir_label.config(text=parent_path)
            
            # 刷新文件列表
            self.log_message(f"⬆️ 导航到上一级目录: {parent_path}")
            self.refresh_file_list(parent_path)
            
        except Exception as e:
            self.log_message(f"导航到上一级目录失败: {str(e)}", "error")
        
    def refresh_server_file_list(self):
        """刷新服务器文件列表（从data/uploads/目录）"""
        if not self.is_connected:
            messagebox.showwarning("警告", "未连接到服务器")
            return
        
        try:
            self.filelist_status.config(text="正在刷新...", foreground='blue')
            self.log_message("🔄 正在从服务器获取文件列表...")
            
            # 禁用刷新按钮，避免重复点击
            if hasattr(self, 'server_refresh_btn'):
                self.server_refresh_btn.config(state='disabled')
            
            # 调用client的方法获取文件列表
            # 假设你的client有获取文件列表的方法
            if hasattr(self.client, 'list_filename_client'):
                file_list = self.client.list_filename_client('TCP')
                
                # 清空现有列表
                for item in self.server_file_tree.get_children():
                    self.server_file_tree.delete(item)
                
                if not file_list or len(file_list) == 0:
                    self.filelist_status.config(text="服务器文件列表为空", foreground='orange')
                    self.log_message("服务器文件列表为空")
                    return
                
                # 过滤出data/uploads/目录下的文件
                uploads_files = []
                other_files = []
                
                for file_info in file_list:
                    filename = file_info.get('filename', '')
                    
                    # 检查是否在data/uploads/目录下
                    if filename.startswith('data/uploads/'):
                        uploads_files.append(file_info)
                    else:
                        other_files.append(file_info)
                
                # 显示data/uploads/目录下的文件
                file_count = 0
                dir_count = 0
                
                for file_info in uploads_files:
                    # 提取相对路径（去掉data/uploads/前缀）
                    filename = file_info.get('filename', '')
                    relative_path = filename
                    if filename.startswith('data/uploads/'):
                        relative_path = filename[len('data/uploads/'):]
                    
                    # 跳过空文件名
                    if not relative_path:
                        continue
                    
                    # 获取文件信息
                    size = file_info.get('size', 0)
                    modified = file_info.get('modified', '')
                    file_type = "文件"
                    
                    # 检查是否是目录（以/结尾或类型为directory）
                    if filename.endswith('/') or file_info.get('type') == 'directory':
                        file_type = "目录"
                        dir_count += 1
                    else:
                        file_count += 1
                    
                    # 格式化显示
                    size_str = self.format_size(size) if file_type == "文件" else "--"
                    modified_str = self.format_time(modified) if modified else ''
                    
                    # 插入到Treeview
                    self.server_file_tree.insert('', 'end', values=(
                        relative_path,  # 显示相对路径
                        size_str,
                        modified_str,
                        file_type
                    ))
                
                # 更新状态
                status_text = f"找到 {file_count} 个文件, {dir_count} 个目录"
                self.filelist_status.config(text=status_text, foreground='green')
                self.log_message(f"✅ {status_text} (来自: data/uploads/)")
                
                # 如果有其他目录的文件，可以记录但不同时显示
                if other_files:
                    self.log_message(f"注: 服务器还有 {len(other_files)} 个其他位置的文件")
            
            else:
                # 如果client没有list_filename_client方法，尝试其他方法
                self.log_message("⚠️ 客户端缺少list_filename_client方法", "warning")
                self._refresh_with_alternative_method()
            
        except Exception as e:
            error_msg = str(e)
            self.filelist_status.config(text="刷新失败", foreground='red')
            self.log_message(f"❌ 刷新文件列表失败: {error_msg}", "error")
            messagebox.showerror("错误", f"刷新文件列表失败:\n{error_msg}")
        
        finally:
            # 重新启用刷新按钮
            if hasattr(self, 'server_refresh_btn'):
                self.root.after(1000, lambda: self.server_refresh_btn.config(state='normal'))
    
    def delete_selected_file(self):
        """删除选中的文件"""
        if not self.is_connected:
            messagebox.showwarning("警告", "未连接到服务器")
            return
        
        # 获取选中的文件
        selection = self.server_file_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择要删除的文件")
            return
        
        item = self.server_file_tree.item(selection[0])
        filename = item['values'][0]
        
        # 确认删除
        if not messagebox.askyesno("确认删除", f"确定要删除文件 '{filename}' 吗？"):
            return
        
        try:
            self.filelist_status.config(text="正在删除...")
            self.log_message(f"正在删除文件: {filename}")
            
            # 这里调用实际的删除逻辑
            # 例如：success = self.client.delete_file(filename)
            
            self.filelist_status.config(text="删除完成")
            self.log_message(f"文件 '{filename}' 删除成功")
            
            # 刷新列表
            self.refresh_server_file_list()
            
        except Exception as e:
            self.filelist_status.config(text="删除失败")
            self.log_message(f"删除文件失败: {str(e)}", "error")
            messagebox.showerror("错误", f"删除文件失败: {str(e)}")
    
    # ========== 核心功能方法 ==========
    
    def connect_to_server(self):
        """连接到服务器"""
        try:
            self.log_message("正在连接服务器...")
            
            if not CLIENT_AVAILABLE:
                self.log_message("❌ 客户端模块不可用", "error")
                self.log_message("请检查项目结构", "error")
                return False
            
            # 创建客户端实例
            self.client = ClientFileSystem()
            self.log_message("✅ 客户端实例创建成功")
            
            # 初始化协议
            if not self.client.initialize_protocols():
                self.log_message("❌ 协议初始化失败", "error")
                return False
            self.log_message("✅ 协议初始化成功")
            
            # 启动连接
            if not self.client.start():
                self.log_message("❌ 连接服务器失败", "error")
                return False
            self.log_message("✅ 服务器连接成功")
            
            self.is_connected = True
            self.connection_label.config(text="已连接", style='Success.TLabel')
            self.connection_status_label.config(text="在线", style='Success.TLabel')
            self.log_message("✅ 成功连接到服务器")
            
            # 刷新文件列表
            self.refresh_file_list()
            
            return True
            
        except Exception as e:
            self.log_message(f"❌ 连接失败: {str(e)}", "error")
            import traceback
            error_details = traceback.format_exc()
            self.log_message(f"详细错误:\n{error_details}", "error")
            return False
            
    def browse_file(self):
        """浏览文件"""
        filepath = filedialog.askopenfilename(
            title="选择要上传的文件",
            filetypes=[("所有文件", "*.*"), ("文本文件", "*.txt"), ("图片文件", "*.jpg *.png *.gif")]
        )
        if filepath:
            self.file_path_var.set(filepath)
            self.upload_btn.config(state='normal')
            
            # 显示文件信息
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            
            self.file_name_label.config(text=filename)
            self.file_size_label.config(text=self.format_size(file_size))
            
            self.log_message(f"选择了文件: {filename} ({self.format_size(file_size)})")
    
    def start_upload(self):
        """开始上传文件"""
        if not self.is_connected:
            messagebox.showerror("错误", "未连接到服务器")
            return
        
        filepath = self.file_path_var.get()
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("错误", "请选择有效的文件")
            return
        
        # 检查文件大小
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            messagebox.showwarning("警告", "文件为空")
            return
        
        # 初始化上传统计
        self.upload_stats = {
            'start_time': time.time(),
            'bytes_sent': 0,
            'total_bytes': file_size,
            'last_update': time.time()
        }
        
        # 更新UI状态
        self.upload_in_progress = True
        self.upload_btn.config(state='disabled', text="上传中...")
        self.cancel_upload_btn.config(state='normal')
        self.upload_status.config(text="正在上传...")
        self.upload_progress['value'] = 0
        
        self.log_message(f"开始上传文件: {os.path.basename(filepath)}")
        
        # 在新线程中执行上传
        upload_thread = threading.Thread(target=self.do_upload, args=(filepath,))
        upload_thread.daemon = True
        upload_thread.start()
    
    def do_upload(self, filepath):
        """执行上传操作"""
        try:
            filename = os.path.basename(filepath)
            
            # 调用client的上传方法
            # 注意：您需要修改send_file方法以支持进度回调
            success = self.client.send_file(filepath, 'TCP')
            
            if success:
                self.log_message(f"✅ 文件上传成功: {filename}")
                
                # 上传完成后刷新文件列表
                self.root.after(0, self.refresh_file_list)
            else:
                self.log_message(f"❌ 文件上传失败: {filename}", "error")
            
        except Exception as e:
            self.log_message(f"❌ 上传过程中出错: {str(e)}", "error")
        finally:
            # 重置UI状态
            self.upload_in_progress = False
            self.root.after(0, lambda: self.upload_btn.config(state='normal', text="开始上传"))
            self.root.after(0, lambda: self.cancel_upload_btn.config(state='disabled'))
            self.root.after(0, lambda: self.upload_status.config(text="上传完成"))
    
    def refresh_file_list(self):
        """刷新服务器文件列表"""
        if not self.is_connected:
            return
        
        try:
            self.log_message("正在获取文件列表...")
            
            # 调用client的获取文件列表方法
            file_list = self.client.list_filename_client()
            
            # 调试：打印接收到的数据
            print(f"DEBUG: 接收到文件列表，数量: {len(file_list) if file_list else 0}")
            if file_list:
                for i, file_info in enumerate(file_list[:5]):  # 只打印前5个
                    print(f"DEBUG: 文件{i+1}: {file_info}")
            
            if file_list:
                # 清空现有列表
                for item in self.file_tree.get_children():
                    self.file_tree.delete(item)
                
                # 添加新项目
                added_count = 0
                for file_info in file_list:
                    filename = file_info.get('filename', '')
                    size = file_info.get('size', 0)
                    modified = file_info.get('modified', '')
                    
                    # 调试：打印每个文件的信息
                    print(f"DEBUG: 处理文件 - 文件名: {filename}, 大小: {size}, 修改时间: {modified}")
                    
                    # 检查是否是data/uploads/目录下的文件
                    if not filename.startswith('data/uploads/'):
                        print(f"DEBUG: 跳过非uploads目录文件: {filename}")
                        continue
                    
                    # 提取相对路径
                    relative_path = filename[len('data/uploads/'):] if filename.startswith('data/uploads/') else filename
                    
                    # 跳过空文件名
                    if not relative_path or relative_path == '/':
                        print(f"DEBUG: 跳过空文件名: {relative_path}")
                        continue
                    
                    # 格式化显示
                    size_str = self.format_size(size)
                    modified_str = self.format_time(modified) if modified else ''
                    
                    # 插入到Treeview
                    self.file_tree.insert('', 'end', values=(relative_path, size_str, modified_str))
                    added_count += 1
                
                self.log_message(f"获取到 {added_count} 个文件（从 {len(file_list)} 个中）")
                print(f"DEBUG: 实际添加到界面的文件数量: {added_count}")
            else:
                self.log_message("服务器文件列表为空")
                
        except Exception as e:
            self.log_message(f"❌ 获取文件列表失败: {str(e)}", "error")
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def on_file_selected(self, event):
        """文件选择事件"""
        selection = self.file_tree.selection()
        if selection:
            self.download_btn.config(state='normal')
            
            # 获取选中文件信息
            item = self.file_tree.item(selection[0])
            filename = item['values'][0]
            self.download_file_label.config(text=filename)
        else:
            self.download_btn.config(state='disabled')
            self.download_file_label.config(text="无")
    
    def start_download(self):
        """开始下载文件"""
        if not self.is_connected:
            messagebox.showerror("错误", "未连接到服务器")
            return
        
        selection = self.file_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择要下载的文件")
            return
        
        # 获取选中文件
        item = self.file_tree.item(selection[0])
        filename = item['values'][0]
        
        # 选择保存位置
        save_dir = filedialog.askdirectory(title="选择保存位置")
        if not save_dir:
            return
        
        save_path = os.path.join(save_dir, filename)
        
        # 初始化下载统计
        self.download_stats = {
            'start_time': time.time(),
            'bytes_received': 0,
            'total_bytes': 0,  # 稍后从服务器获取
            'last_update': time.time()
        }
        
        # 更新UI状态
        self.download_in_progress = True
        self.download_btn.config(state='disabled', text="下载中...")
        self.cancel_download_btn.config(state='normal')
        if hasattr(self, 'download_status'):
            self.download_status.config(text=f"正在下载: {filename}")
        else:
            # 如果 download_status 不存在，创建一个临时标签
            print(f"正在下载: {filename}")
        
        if hasattr(self, 'download_progress'):
            self.download_progress['value'] = 0
        
        self.log_message(f"开始下载文件: {filename}")
        
        # 在新线程中执行下载
        download_thread = threading.Thread(target=self.do_download, args=(filename, save_path))
        download_thread.daemon = True
        download_thread.start()
    
    def do_download(self, filename, save_path):
        """执行下载操作"""
        try:
            # 调用client的下载方法
            # 注意：您需要修改download_file方法以支持进度回调
            success = self.client.download_file(filename, 'TCP', target=None)
            
            if success:
                self.log_message(f"✅ 文件下载成功: {filename}")
            else:
                self.log_message(f"❌ 文件下载失败: {filename}", "error")
            
        except Exception as e:
            self.log_message(f"❌ 下载过程中出错: {str(e)}", "error")
        finally:
            # 重置UI状态
            self.download_in_progress = False
            self.root.after(0, lambda: self.download_btn.config(state='normal', text="下载选中文件"))
            self.root.after(0, lambda: self.cancel_download_btn.config(state='disabled'))
            self.root.after(0, lambda: self.download_status.config(text="下载完成"))
    
    def cancel_upload(self):
        """取消上传"""
        self.upload_in_progress = False
        self.log_message("上传已取消")
        
        self.upload_btn.config(state='normal', text="开始上传")
        self.cancel_upload_btn.config(state='disabled')
        self.upload_status.config(text="上传已取消")
    
    def cancel_download(self):
        """取消下载"""
        self.download_in_progress = False
        self.log_message("下载已取消")
        
        self.download_btn.config(state='normal', text="下载选中文件")
        self.cancel_download_btn.config(state='disabled')
        self.download_status.config(text="下载已取消")
    
    def update_ui_loop(self):
        """UI更新循环"""
        while self.running:
            try:
                # 更新连接状态
                if self.client and hasattr(self.client, 'tcp_client'):
                    is_connected = self.client.tcp_client.is_connected if hasattr(self.client.tcp_client, 'is_connected') else False
                    
                    if is_connected != self.is_connected:
                        self.is_connected = is_connected
                        if is_connected:
                            self.root.after(0, lambda: self.connection_label.config(text="已连接", style='Success.TLabel'))
                            self.root.after(0, lambda: self.connection_status_label.config(text="在线", style='Success.TLabel'))
                        else:
                            self.root.after(0, lambda: self.connection_label.config(text="未连接", style='Error.TLabel'))
                            self.root.after(0, lambda: self.connection_status_label.config(text="离线", style='Error.TLabel'))
                
                # 更新上传进度（模拟）
                if self.upload_in_progress:
                    current_time = time.time()
                    elapsed = current_time - self.upload_stats['start_time']
                    
                    # 模拟进度
                    if elapsed < 5:  # 假设上传需要5秒
                        progress = (elapsed / 5) * 100
                        bytes_sent = int(self.upload_stats['total_bytes'] * (elapsed / 5))
                        
                        self.root.after(0, lambda p=progress, b=bytes_sent: self.update_upload_progress(p, b))
                
                # 更新下载进度（模拟）
                if self.download_in_progress:
                    current_time = time.time()
                    elapsed = current_time - self.download_stats['start_time']
                    
                    # 模拟进度
                    if elapsed < 5:  # 假设下载需要5秒
                        progress = (elapsed / 5) * 100
                        bytes_received = int(self.download_stats.get('total_bytes', 1024*1024) * (elapsed / 5))
                        
                        self.root.after(0, lambda p=progress, b=bytes_received: self.update_download_progress(p, b))
                
                time.sleep(0.1)  # 100ms更新一次
                
            except Exception as e:
                print(f"UI更新错误: {e}")
                time.sleep(1)
    
    def update_upload_progress(self, progress, bytes_sent):
        """更新上传进度"""
        self.upload_progress['value'] = progress
        self.upload_percent_label.config(text=f"{progress:.1f}%")
        self.transferred_label.config(text=self.format_size(bytes_sent))
        
        # 计算速度和剩余时间
        if progress > 0:
            total_time = (100 / progress) * (time.time() - self.upload_stats['start_time'])
            remaining_time = total_time * (1 - progress/100)
            
            speed = bytes_sent / (time.time() - self.upload_stats['start_time']) / 1024  # KB/s
            
            self.upload_speed_label.config(text=f"{speed:.1f} KB/s")
            self.upload_eta_label.config(text=f"{remaining_time:.0f}秒")
    
    def update_download_progress(self, progress, bytes_received):
        """更新下载进度"""
        self.download_progress['value'] = progress
        self.download_percent_label.config(text=f"{progress:.1f}%")
        self.downloaded_label.config(text=self.format_size(bytes_received))
        
        # 计算速度和剩余时间
        if progress > 0:
            total_time = (100 / progress) * (time.time() - self.download_stats['start_time'])
            remaining_time = total_time * (1 - progress/100)
            
            speed = bytes_received / (time.time() - self.download_stats['start_time']) / 1024  # KB/s
            
            self.download_speed_label.config(text=f"{speed:.1f} KB/s")
            self.download_eta_label.config(text=f"{remaining_time:.0f}秒")
    
    def log_message(self, message, level="info"):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.root.after(0, lambda: self.log_text.insert('end', log_entry))
        self.root.after(0, lambda: self.log_text.see('end'))
        
        # 根据日志级别设置颜色
        if level == "error":
            self.root.after(0, lambda: self.log_text.tag_add('error', 'end-2l', 'end-1l'))
            self.root.after(0, lambda: self.log_text.tag_config('error', foreground='red'))
        elif level == "success":
            self.root.after(0, lambda: self.log_text.tag_add('success', 'end-2l', 'end-1l'))
            self.root.after(0, lambda: self.log_text.tag_config('success', foreground='green'))
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', 'end')
    
    def format_size(self, bytes):
        """格式化文件大小"""
        if bytes < 1024:
            return f"{bytes} B"
        elif bytes < 1024 * 1024:
            return f"{bytes/1024:.1f} KB"
        elif bytes < 1024 * 1024 * 1024:
            return f"{bytes/(1024*1024):.1f} MB"
        else:
            return f"{bytes/(1024*1024*1024):.1f} GB"
    
    def format_time(self, timestamp):
        """格式化时间"""
        try:
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            else:
                return str(timestamp)
        except:
            return str(timestamp)
    
    def on_closing(self):
        """关闭窗口"""
        self.running = False
        if self.client:
            self.client.stop()
        self.root.destroy()
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()

# 主程序入口
if __name__ == "__main__":
    app = FileTransferClientGUI()
    app.run()
