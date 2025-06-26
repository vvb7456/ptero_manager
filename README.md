# 艾萝工坊统一绿皮运维管理系统
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![Version](https://img.shields.io/badge/version-v1.2.0-brightgreen.svg)

本系统是一个基于 Flask 和 Pterodactyl API 的 Web 管理面板，旨在简化对 Pterodactyl 面板上大量服务器生命周期的管理。


## 核心功能

-   **统一的仪表盘**: 集中概览用户总数、服务器总数，以及服务器状态（正常、即将到期、已冻结等）的图表化统计。
-   **强大的服务器管理**: 列表、筛选、排序和搜索所有服务器。支持对单个或批量服务器进行**续期、冻结/解冻、删除**等操作。
-   **精细的用户管理**: 列表、筛选和管理 Pterodactyl 用户。支持**批量删除用户（及其名下所有服务器）**和编辑用户信息。
-   **可视化的创建流程**: 通过向导式表单轻松创建新用户和新服务器，支持动态加载服务器预设(Egg)的变量和节点可用端口。
-   **灵活的邮件系统**: 可在 UI 界面自定义三种场景的 **HTML 邮件模板**（批量通知、到期提醒、新用户欢迎）。
-   **后台自动化任务**:
    -   **自动冻结**: 服务器到期次日自动冻结。
    -   **自动删除**: 服务器到期超过指定天数后自动删除。
    -   **到期提醒**: 在服务器到期前一天自动发送邮件提醒。

---

## 目录

- [第一部分：部署与维护指南](#第一部分部署与维护指南)
  - [1. 环境准备](#1-环境准备)
  - [2. 部署步骤](#2-部署步骤)
  - [3. 核心配置 (`settings.json`)](#3-核心配置-settingsjson)
  - [4. 运行与管理](#4-运行与管理)
  - [5. 生产环境部署 (systemd)](#5-生产环境部署-systemd)
- [第二部分：系统使用手册](#第二部分系统使用手册)
  - [1. 登录与仪表盘](#1-登录与仪表盘)
  - [2. 服务器与用户管理](#2-服务器与用户管理)
  - [3. 创建服务器](#3-创建服务器)
  - [4. 邮件与自动化](#4-邮件与自动化)

---

## 第一部分：部署与维护指南

本部分面向需要部署、配置和维护此系统的技术人员。

### 1. 环境准备

-   **操作系统**: Linux (推荐 CentOS 7+, Debian 9+, Ubuntu 18.04+)
-   **Python**: 版本 3.8 或更高。
-   **Git**: 版本控制工具。
-   **网络**: 服务器必须能访问您要管理的 Pterodactyl 面板的 URL。

### 2. 部署步骤

1.  **克隆仓库**:
    ```bash
    cd /opt
    git clone https://github.com/vvb7456/ptero_manager.git
    ```

2.  **创建并激活虚拟环境**:
    ```bash
    cd /opt/ptero_manager
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **创建并配置 `settings.json`**:
    **此为关键步骤！** 您必须在项目根目录 `/opt/ptero_manager/` 下手动创建一个 `settings.json` 文件，并填入您的配置。

### 3. 核心配置 (`settings.json`)

这是 `settings.json` 的一个完整模板。请根据您的实际情况填写所有值。

```json
{
    "UI_SYSTEM_NAME": "艾萝工坊运维系统",
    "UI_BANNER_URL": "https://your-logo-url.com/logo.png",
    "ADMIN_PASSWORD": "your_super_secret_password",
    "PTERO_PANEL_URL": "https://panel.yourdomain.com",
    "PTERO_API_KEY": "your_pterodactyl_application_api_key",
    
    "SMTP_HOST": "smtp.mxhichina.com",
    "SMTP_PORT": 465,
    "SMTP_USE_SSL": true,
    "SMTP_PASSWORD": "your_email_password_or_app_token",
    "SENDER_EMAIL": "no-reply1@example.com,no-reply2@example.com",
    "EMAIL_SEND_DELAY": 3,
    
    "DEFAULT_NEST_ID": 1,
    "DEFAULT_EGG_ID": 1,
    "DEFAULT_NODE_ID": 1,
    "DOCKER_IMAGE": "ghcr.io/pterodactyl/yolks:java_17",
    "DEFAULT_CPU": 100,
    "DEFAULT_MEMORY": 1024,
    "DEFAULT_DISK": 5120,
    "DEFAULT_DATABASES": 0,
    "DEFAULT_BACKUPS": 1,
    "DEFAULT_ALLOCATIONS": 1,
    
    "AUTOMATION_SUSPEND_ENABLED": true,
    "AUTOMATION_DELETE_ENABLED": true,
    "AUTOMATION_EMAIL_ENABLED": true,
    "AUTOMATION_RUN_HOUR": 2,
    "AUTOMATION_RUN_MINUTE": 0,
    "AUTOMATION_DELETE_DAYS": 14,
    "AUTOMATION_EMAIL_RUN_HOUR": 10,
    "AUTOMATION_EMAIL_RUN_MINUTE": 0
}
```

**配置项说明**:
-   `SMTP_*` & `SENDER_EMAIL`: **强烈推荐**使用专业的邮件推送服务（如阿里云邮件推送、SendGrid）的 SMTP 信息，以保证邮件送达率。`SENDER_EMAIL` 支持填写多个发件人地址（用逗号分隔）组成轮询池，以规避速率限制。`SMTP_PASSWORD` 必须对池中所有邮箱都有效。
-   `PTERO_*`: Pterodactyl 面板的 URL 和 Application API Key。
-   `DEFAULT_*`: 创建服务器时表单的默认预填值。
-   `AUTOMATION_*`: 自动化任务的开关和执行时间。

### 4. 运行与管理

请使用 `manager.sh` 脚本来管理应用，它会以后台模式启动 Gunicorn 生产服务器。
-   `chmod +x manager.sh` (首次使用需授权)
-   **启动服务**: `./manager.sh start`
-   **停止服务**: `./manager.sh stop`
-   **重启服务**: `./manager.sh restart`
-   **查看状态**: `./manager.sh status`

服务默认监听在 `0.0.0.0:5000`。

### 5. 生产环境部署 (systemd)

为确保服务开机自启，建议使用 `systemd` 管理。

1.  创建 `logs` 目录: `mkdir /opt/ptero_manager/logs`
2.  创建服务文件 `sudo nano /etc/systemd/system/ptero-manager.service`。
3.  粘贴以下内容，并根据需要修改 `User` 和 `WorkingDirectory`。
    ```ini
    [Unit]
    Description=Ptero Manager Gunicorn Service
    After=network.target

    [Service]
    User=www-data
    Group=www-data
    WorkingDirectory=/opt/ptero_manager
    ExecStart=/opt/ptero_manager/venv/bin/gunicorn --workers 3 --bind unix:ptero_manager.sock -m 007 wsgi:app --daemon --pid /opt/ptero_manager/ptero_manager.pid --log-level=info --error-logfile /opt/ptero_manager/logs/error.log --access-logfile /opt/ptero_manager/logs/access.log
    ExecStop=/bin/kill -s TERM $(cat /opt/ptero_manager/ptero_manager.pid)
    ExecReload=/bin/kill -s HUP $(cat /opt/ptero_manager/ptero_manager.pid)
    Restart=always
    RestartSec=5s

    [Install]
    WantedBy=multi-user.target
    ```

4.  使用 `systemctl` 管理服务：
    -   `sudo systemctl daemon-reload`
    -   `sudo systemctl start ptero-manager`
    -   `sudo systemctl enable ptero-manager`
    -   `sudo systemctl status ptero-manager`

---

## 第二部分：系统使用手册

### 1. 登录与仪表盘
访问 `http://<您的服务器IP>:5000`，输入您在 `settings.json` 中设置的 `ADMIN_PASSWORD` 即可登录。仪表盘提供系统核心指标的概览。

### 2. 服务器与用户管理
-   **服务器列表**: 核心功能页面。可筛选、排序、搜索，并对单个或批量服务器进行续期、冻结/解冻、删除和发送邮件。
-   **用户列表**: 管理所有 Pterodactyl 用户，可编辑用户信息，或批量删除用户（及其所有服务器）和发送通知。

### 3. 创建服务器
通过可视化表单，为指定用户创建新服务器。系统会自动加载所选预设的变量和节点的可用端口，简化配置过程。

### 4. 邮件与自动化
-   **邮件模板**: 在 Web UI 中自定义三种邮件（批量通知、到期提醒、新用户欢迎）的核心内容。
-   **自动化**: 在 UI 中配置自动冻结、自动删除和自动邮件提醒的执行时间和开关。
-   **重要提示**: **任何对系统设置（如API、密码）或自动化时间的修改，都必须重启应用服务 (`./manager.sh restart` 或 `sudo systemctl restart ptero-manager`) 才能完全生效。**