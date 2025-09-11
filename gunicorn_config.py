# gunicorn_config.py
import os
from app import app, initialize_scheduler, scheduler

def when_ready(server):
    """
    当 Gunicorn 服务器完全准备好时，在主进程中执行。
    这是启动调度器的理想位置。
    """
    initialize_scheduler(app)
    if not scheduler.running:
        scheduler.start()
        server.log.info("APScheduler started in Gunicorn master process.")

# 绑定地址和端口
bind = "0.0.0.0:5000"

# 工作进程数
workers = 3

# Worker 类型
worker_class = "gevent"

# 超时时间
timeout = 120

# PID 文件
pidfile = "ptero_manager.pid"

# 日志文件
accesslog = "/opt/ptero_manager/logs/access.log"
errorlog = "/opt/ptero_manager/logs/error.log"
loglevel = "info"

# 预加载应用
preload_app = True

# 后台运行
daemon = True