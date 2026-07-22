# network_file_system

Python 程序代码，实现文件传输。

## 作者信息

- **姓名**：江紫涵
- **学校**：上海海事大学
- **邮箱**：18019449191@163.com
- **手机号**：18019449191
- **微信号**：9696969696961229

## 概述

- **时间**：2026/1/9 ~ 2026/3/8（大二寒假期间）
- **目的**：通过此项目熟悉 Python 编程，了解项目的开发、调试、测试等知识。
- **学习知识点**：

### a. 日志与配置（config / logger）
`config` 和 `logger` 实现了日志功能，对程序运行进行实时更新，方便跟踪和调试。

### b. 文件系统类继承（file_system）
`file_system` 中三个文件体现了类的继承。Server 和 Client 部分功能类似，因此设计公有的 `base` 基类存放公共函数，再在各自类中实现不同功能。客户端实现了上传文件、下载文件、获取文件列表的功能，内部调用 `file_transfer` 实现更深层次的功能。TCP 协议涉及网络协议知识，初始化时加入回调机制，实现网络层与应用层分离。

### c. 线程池（thread_pool）
`thread_pool` 位于 `thread` 文件夹中，可对线程池进行管理，实现线程的启动，避免频繁创建销毁线程的开销，并能安全地停止所有线程。同时支持将任务放入队列，按先进先出顺序执行。

### d. 网络协议（protocols）
`protocols` 包含 TCP 和 UDP 协议，运行时主要使用 TCP 协议。UDP 和 TCP 基于基类完善各自功能。TCP 实现了服务器和客户端功能，服务器支持监听、接受、处理等，客户端支持连接、收发等功能。

### e. 文件管理（file_manager）
`file_manager` 分为 `file_operations` 和 `file_transfer` 两个文件：
- `file_operations`：为 `file_transfer` 提供服务，支持文件路径初始化、列出目录文件、读写文件块、删除文件、格式化文件等功能。
- `file_transfer`：包含上传和下载时所需的具体函数，作为任务加入线程池。服务器和客户端发送文件使用不同函数，内部根据信号进行不同操作。

### f. UI 界面（ui）
`ui` 设计了客户端界面，利用窗口、标签等组件，将按键与函数结合，实现交互功能。

## 目录结构

工程分为四个文件夹：`config`、`data`、`logs` 和 `src`。

- `config`：存放配置文件（如 `setting.json`），可修改服务器地址等。
- `data`：存放上传和下载的文件（`uploads` / `downloads`）。
- `logs`：记录程序运行日志。
- `src`：存放主要代码。

network_file_system/
├── config/
│ └── setting.json
├── data/
│ ├── uploads/
│ └── downloads/
├── logs/
└── src/
├── file_manager/
│ ├── file_operations.py
│ └── file_transfer.py
├── file_system/
│ ├── base_filesystem.py
│ ├── client_filesystem.py
│ └── server_filesystem.py
├── protocols/
│ ├── base_protocol.py
│ ├── tcp_protocol.py
│ └── udp_protocol.py
├── thread/
│ ├── sync_utils.py
│ └── thread_pool.py
├── ui/
│ ├── clientUI.py
│ └── serverUI.py
├── utils/
│ ├── config.py
│ └── logger.py
├── server.py
└── client.py


## 运行方法

### Server 端
直接运行：
```bash
python server.py


### Client 端
通过参数选择运行方式：

- **启动 UI 界面**：
  ```bash
  python client.py ui
  # 或
  python client.py gui
启动后可在图形界面上传、下载文件，并查看服务端文件列表。