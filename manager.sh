#!/bin/bash

# Gunicorn 服务管理脚本 (已升级为支持 gevent 和更完整的命令)

# --- 配置 ---
# 应用名称 (用于日志文件名等)
APP_NAME="ptero_manager"

# 项目的根目录 (脚本所在的目录)
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Gunicorn 进程ID文件
PID_FILE="$APP_DIR/$APP_NAME.pid"

# 激活虚拟环境 (如果存在)
VENV_ACTIVATE="$APP_DIR/venv/bin/activate"
if [ -f "$VENV_ACTIVATE" ]; then
    echo "正在激活虚拟环境..."
    source "$VENV_ACTIVATE"
else
    echo "警告: 未找到虚拟环境 'venv'。将使用系统级的 Python 环境。"
fi

# 日志文件目录
LOG_DIR="$APP_DIR/logs"

# Flask 应用入口，格式为 `模块名:Flask实例名`
APP_MODULE="app:app"

# --- Gunicorn 生产环境推荐配置 ---
# 绑定的 IP 和端口。0.0.0.0 表示监听所有网络接口。
BIND_ADDR="0.0.0.0:5000"

# 工作进程数。推荐值为 (2 * CPU核心数) + 1。可以先从 3 开始。
WORKERS=3

# 【关键】Worker 类型。使用 gevent 来处理异步IO，防止超时。
WORKER_CLASS="gevent"

# 【关键】超时时间（秒）。延长以应对慢速API响应。
TIMEOUT=120

# Gunicorn 用户和组 (如果需要，可以取消注释并修改)
# USER="your_user"
# GROUP="your_group"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 检查 gunicorn 是否存在
if ! command -v gunicorn &> /dev/null
then
    echo "错误: gunicorn 命令未找到。"
    echo "请确保您已经激活了项目的虚拟环境 (source venv/bin/activate)，或者 gunicorn 在您的系统 PATH 中。"
    exit 1
fi


start() {
    # 检查PID文件是否存在，如果存在则表示可能已在运行
    if [ -f "$PID_FILE" ]; then
        echo "PID 文件 $PID_FILE 已存在。请先停止现有进程 (./manager.sh stop) 或手动删除该文件。"
        exit 1
    fi

    echo "正在启动 $APP_NAME..."

    # 切换到应用目录
    cd "$APP_DIR" || exit

    # 启动 Gunicorn (已加入 --preload 参数)
    gunicorn --config gunicorn_config.py ${APP_MODULE} \
      --workers ${WORKERS} \
      --worker-class ${WORKER_CLASS} \
      --timeout ${TIMEOUT} \
      --bind ${BIND_ADDR} \
      --pid ${PID_FILE} \
      --access-logfile "$LOG_DIR/access.log" \
      --error-logfile "$LOG_DIR/error.log" \
      --log-level "info" \
      --preload \
      --daemon

    # --daemon 参数让 Gunicorn 在后台运行

    sleep 2 # 等待一下，确保进程启动
    if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null; then
        echo "$APP_NAME 已成功启动。"
        echo "PID: $(cat "$PID_FILE")"
        echo "日志文件位于: $LOG_DIR"
    else
        echo "错误: $APP_NAME 启动失败。请检查 $LOG_DIR/error.log 文件获取详情。"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "$APP_NAME 似乎没有在运行 (未找到 PID 文件)。"
        return
    fi

    echo "正在停止 $APP_NAME..."
    # 从PID文件读取进程ID并发送TERM信号
    kill $(cat "$PID_FILE")
    # 等待进程退出
    rm -f "$PID_FILE"
    echo "$APP_NAME 已停止。"
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "$APP_NAME 正在运行，PID: $PID"
        else
            echo "$APP_NAME 状态异常：PID 文件存在，但进程不在运行。建议执行 'stop' 后再 'start'。"
        fi
    else
        echo "$APP_NAME 没有在运行。"
    fi
}

# --- 脚本主逻辑 ---
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0