# network_file_system
python程序代码，实现文件传输
作者信息：
姓名：  江紫涵
学校：  上海海事大学
邮箱：  18019449191@163.com
手机号：18019449191
微信号:_9696969696961229
概述:
时间：2026/1/9 ~2026/3/8 (大二寒假期间)
目的：通过此项目熟悉python编程，了解项目的开发，调式，测试等知识
学习知识点：
a. config和logger实现了日志的功能，对于程序运行进行实时的更新，方便对程序运行进行更好的跟踪。
调试时也能根据这个信息确定哪里有问题。
b. file_system中三个文件体现了类的继承，因为server和client有些功能是类似的，因此设计公有的base基类存
放他们公有的函数，再在各自类里写各自不同的功能。客服端的代码基本实现了上传文件，下载文件，获取文
件列表的函数。函数内部调用file_transfer实现更深层次的功能，server的system端也一样。其中tcp协议还包
括了网络协议的知识。在初始化客户端和服务端协议时加入回调机制，让网络层与应用层分离。
c.  thread_pool在thread文件夹中。它可以对线程池进行管理，实现线程的启动，避免频繁创建销毁线程的开销，
安全地停止所有线程 。并且能将任务放入队列，先进先出执行任务
d.  protocols文件包含了tcp和udp协议，运行时主要使用的是tcp协议，udp有些功能并没有实现。udp和tcp基于
基类上完善自己的功能。tcp协议实现了服务器和客户端的功能，服务器功能有监听、接受、处理等，客户端功能
有连接、收发等功能。
e.  file_manager分为file_operations和file_transfer两个文件。file_operations是为file_transfer服务的。file_operations
能对文件进行各种操作，初始化函数确定了文件的路径，并有列出目录中文件，写入读取文件块的功能，以及删除文件，
格式化文件的功能。
file_transfer里的函数更多，包含了上传和下载文件时需要的具体函数，这些函数会作为任务在需要时加入线程池中。
服务器发送文件和客户端发送文件分别使用了不同的函数，函数内部会根据发送和接收的信号进行不同的操作。
f. ui函数设计了客户端的界面，上面利用了窗口，界面，标签等，将按键和函数结合起来，实现了需要的效果。
目录结构:
工程分为四个文件夹，分别是config，data，logs和src文件夹。
客户可以编辑config文件夹里的配置文件，由此可以改变连接的服务器端的地址以及其他的配置。
data文件夹中存放上传以及下载的文件。
Logger 用于记录程序运行信息的工具。
src存放主要的代码。
network_file_system目录结构如下：
|---------config
                          |----------setting.json
|----------data
                         |-------uploads
                         |-------downloads
|----------logs
|----------src
                    |------file_manager
                                                   |--------file_operations.py
                                                   |--------file_transfer.py
                    |------file_system
                                                   |--------base_filesystem.py
                                                   |--------client_filesystem.py
                                                   |--------server_filesystem.py
                    |------protocols
                                                   |--------base_protocol.py
                                                   |--------tcp_protocol.py
                                                   |--------udp_protocol.py

                    |------thread
                                                   |--------sync_utils.py
                                                   |--------thread_pool.py
                    |------ui
                                                   |--------clientUI.py
                                                   |--------serverUI.py
                    |------utils
                                                   |--------config.py
                                                   |--------logger.py
                    |------server.py
                    |------client.py

5.  运行方法：
server端代码可以直接运行，输入python server.py的命令直接运行。
client端可以通过参数选择不同的运行方式。主要分为直接用命令行执行和使用界面执行，在client.py后面会加上参数来确定执行的方式，
如果第一个参数command是ui或者gui就会启动界面,然后直接在页面上传输和下载文件，并可以查看当前服务端有哪些文件。直接在命令行
运行时，第一个参数是命令，有三种不同的命令，分别是：upload，download_request，get_filelist。第二个参数是文件名，当命令
是get_filelist不需要这个参数。运行时会有打印信息显示是否传输成功，如果失败或者漏传文件块会报错。这样就能实现传输文件。

如果有缺失的包，根据提示安装相应的包。
