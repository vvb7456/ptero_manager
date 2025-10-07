# gunicorn_config.py
import os
import logging
from logging.handlers import RotatingFileHandler
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

def post_fork(server, worker):
    """
    在 worker 进程被 fork 后调用。
    暂停从 master 继承的 scheduler，防止 worker 执行重复任务。
    """
    scheduler.pause()

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

# --- 日志配置 ---
# 移除旧的日志文件路径配置
# accesslog = "/opt/ptero_manager/logs/access.log"
# errorlog = "/opt/ptero_manager/logs/error.log"
loglevel = "info"

# 使用 Python logging 进行高级配置
# 这会同时捕获 Gunicorn 的日志和 Flask app 的日志
logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'generic': {
            'format': '%(asctime)s [%(process)d] [%(levelname)s] %(message)s',
            'datefmt': '[%Y-%m-%d %H:%M:%S %z]',
            'class': 'logging.Formatter',
        },
    },
    'handlers': {
        # 控制台输出 Handler
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'generic',
            'stream': 'ext://sys.stdout',
        },
        # 错误日志文件 Handler (轮转)
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'generic',
            'filename': '/opt/ptero_manager/logs/error.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'encoding': 'utf-8',
        },
        # 访问日志文件 Handler (轮转)
        'access_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'generic',
            'filename': '/opt/ptero_manager/logs/access.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        # Gunicorn 的错误日志，应用日志也会被定向到这里
        'gunicorn.error': {
            'handlers': ['console', 'error_file'],
            'level': 'INFO',
            'propagate': False, # 防止向 root logger 传播
        },
        # Gunicorn 的访问日志
        'gunicorn.access': {
            'handlers': ['access_file'],
            'level': 'INFO',
            'propagate': False, # 防止向 root logger 传播
        },
    },
    # Root logger 配置，可以捕获其他未明确指定的日志
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'error_file'],
    },
}


# 预加载应用
preload_app = True

# 后台运行
daemon = True