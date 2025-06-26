# 艾萝工坊绿皮运维管理系统
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![Version](https://img.shields.io/badge/version-v2.0.0-brightgreen.svg)

一个基于 Flask 和 Pterodactyl API 的 Web 管理面板，旨在为系统管理员提供一个集中、高效的图形化界面，以简化对 Pterodactyl 面板上大量服务器生命周期的管理。

## 核心特性

-   **安全的多用户认证**: 支持创建多个管理员账号，密码经过加盐哈希安全存储，专为公网部署设计。
-   **统一的仪表盘**: 集中概览用户总数、服务器总数，以及服务器状态（正常、即将到期、已冻结等）的图表化统计。
-   **强大的服务器管理**: 在统一界面中列表、筛选、排序和搜索所有服务器。支持对单个或批量服务器进行**续期、冻结/解冻、删除**等操作。
-   **精细的用户管理**: 列表、筛选和管理 Pterodactyl 用户。支持**批量删除用户（及其名下所有服务器）**和编辑用户信息。
-   **可视化的创建流程**: 通过向导式表单轻松创建新用户和新服务器，支持动态加载服务器预设(Egg)的变量和节点可用端口。
-   **专业的邮件系统**: 配置简单，可直接对接专业的云邮件推送服务（如 Amazon SES, SendGrid 等），并支持在后台自定义三种场景的 **HTML 邮件模板**（批量通知、到期提醒、新用户欢迎）。
-   **后台自动化任务**:
    -   **自动冻结**: 服务器到期次日自动执行冻结。
    -   **自动删除**: 服务器到期超过指定天数后自动彻底删除。
    -   **到期提醒**: 在服务器到期前一天自动向用户发送邮件提醒。

---

## 目录

- [部署与管理指南](#部署与管理指南)
  - [1. 环境要求](#1-环境要求)
  - [2. 全新部署流程](#2-全新部署流程)
  - [3. 核心配置 (`settings.json`)](#3-核心配置-settingsjson)
  - [4. 服务运行与维护](#4-服务运行与维护)
  - [5. 生产环境进阶 (systemd)](#5-生产环境进阶-systemd)
- [系统使用手册](#系统使用手册)
  - [1. 登录与会话管理](#1-登录与会话管理)
  - [2. 功能模块概览](#2-功能模块概览)

---

## 部署与管理指南

本部分面向需要部署、配置和维护此系统的技术人员。

### 1. 环境要求

-   **操作系统**: Linux (推荐 CentOS 7+, Debian 9+, Ubuntu 18.04+)
-   **Python**: 版本 3.8 或更高。
-   **Git**: 版本控制工具。
-   **网络**: 部署本系统的服务器必须能够通过网络访问您要管理的 Pterodactyl 面板的 URL。

### 2. 全新部署流程

#### 第 1 步：克隆代码仓库
```bash
cd /opt
git clone https://github.com/vvb7456/ptero_manager.git
```

#### 第 2 步：创建并激活 Python 虚拟环境
一个独立、干净的虚拟环境是稳定运行的保障。```bash
cd /opt/ptero_manager
python3 -m venv venv
source venv/bin/activate
```
成功激活后，您的命令行提示符前会显示 `(venv)`。

#### 第 3 步：安装项目依赖
```bash
pip install -r requirements.txt
```

#### 第 4 步：初始化数据库
系统需要一个数据库文件来存储管理员账号。此命令会自动创建所需的表。
```bash
flask shell
```
进入 `>>>` 提示符后，执行以下命令：
```python
from app import db
db.create_all()
exit()
```

#### 第 5 步：创建第一个管理员账号
使用我们提供的命令行工具，安全地创建您的第一个后台管理员账号。
```bash
flask create-admin
```
根据终端提示，输入您要设置的**用户名**和**密码**。

### 3. 核心配置 (`settings.json`)

**部署中最关键的一步。** 在项目根目录 `/opt/ptero_manager/` 下，您必须**手动创建**一个名为 `settings.json` 的文件，并填入您的配置。

**`settings.json` 完整配置模板：**
```json
{
    "UI_SYSTEM_NAME": "我的管理面板",
    "UI_BANNER_URL": "https://your-logo-url.com/logo.png",
    
    "PTERO_PANEL_URL": "https://panel.yourdomain.com",
    "PTERO_API_KEY": "ptla_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    
    "SMTP_HOST": "smtp.example-provider.com",
    "SMTP_PORT": 465,
    "SMTP_USE_SSL": true,
    "SMTP_PASSWORD": "your_email_service_password_or_app_token",
    "SENDER_EMAIL": "no-reply@yourdomain.com",
    "EMAIL_SEND_DELAY": 3,
    
    "DEFAULT_NEST_ID": 1,
    "DEFAULT_EGG_ID": 15,
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
-   `PTERO_*`: 您的 Pterodactyl 面板 URL 和 **Application API Key**。
-   `SMTP_*`: **强烈推荐**使用专业的邮件推送服务（如阿里云邮件推送、SendGrid）的 SMTP 信息以保证送达率。
-   `DEFAULT_*`: 用于在“创建服务器”页面预填表单的默认值。
-   `AUTOMATION_*`: 后台自动化任务的开关和执行时间（24小时制）。

### 4. 服务运行与维护

本项目自带一个 `manager.sh` 脚本，用于以后台模式启动 Gunicorn 生产服务器。

-   **首次使用需授权**: `chmod +x manager.sh`
-   **启动服务**: `./manager.sh start`
-   **停止服务**: `./manager.sh stop`
-   **重启服务**: `./manager.sh restart`
-   **查看状态**: `./manager.sh status`

服务启动后，默认监听在 `0.0.0.0:5000`。您可以通过 `http://<服务器IP>:5000` 访问。

### 5. 生产环境进阶 (systemd)

为确保服务在服务器重启后能自动运行，建议使用 `systemd` 进行托管。

1.  创建 `logs` 目录: `mkdir /opt/ptero_manager/logs`
2.  创建服务文件: `sudo nano /etc/systemd/system/ptero-manager.service`
3.  粘贴以下内容，并根据需要修改 `User` 和 `Group`。
    ```ini
    [Unit]
    Description=Ptero Manager Gunicorn Service
    After=network.target

    [Service]
    User=root
    Group=root
    WorkingDirectory=/opt/ptero_manager
    ExecStart=/opt/ptero_manager/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 app:app --pid /opt/ptero_manager/ptero_manager.pid --log-level=info --error-logfile /opt/ptero_manager/logs/error.log --access-logfile /opt/ptero_manager/logs/access.log
    Restart=always
    RestartSec=5s

    [Install]
    WantedBy=multi-user.target
    ```
4.  使用 `systemctl` 管理服务：
    -   `sudo systemctl daemon-reload`
    -   `sudo systemctl start ptero-manager`
    -   `sudo systemctl enable ptero-manager` (设置开机自启)
    -   `sudo systemctl status ptero-manager`

---

## 系统使用手册

### 1. 登录与会话管理
-   **登录**: 访问系统 URL，输入您在部署时通过 `flask create-admin` 命令创建的**用户名和密码**即可登录。
-   **会话超时**: 为了安全与便利，系统默认会话超时时间为 **31 天**。如果您在 31 天内未与系统交互，下次访问时需要重新登录。

### 2. 功能模块概览

-   **仪表盘**: 系统首页，提供核心指标（用户、服务器、状态分布）的全局概览。
-   **服务器列表**: 核心功能页面。可进行复杂的筛选、排序和搜索，并对服务器进行续期、冻结/解冻、删除和发送邮件等批量操作。
-   **用户列表**: 管理所有 Pterodactyl 用户，可编辑用户信息，或批量删除用户及其名下所有服务器。
-   **邮件模板**: 在 Web UI 中直观地编辑三种自动化邮件（批量通知、到期提醒、新用户欢迎）的标题和正文内容。
-   **自动化设置**: 在后台页面控制自动冻结、自动删除和自动邮件提醒的执行时间和开关。
-   **系统设置**: 配置与 Pterodactyl、SMTP 和新服务器默认资源相关的核心参数。

> **重要提示**: 任何对 **系统设置** 或 **自动化** 页面的修改，都必须**重启应用服务** (`./manager.sh restart` 或 `sudo systemctl restart ptero-manager`) 才能使改动完全生效。