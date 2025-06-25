# 艾萝工坊统一绿皮运维管理系统

本系统是一个基于 Flask 和 Pterodactyl API 的 Web 管理面板，旨在简化对 Pterodactyl 面板上大量服务器生命周期的管理。

![GitHub](https://img.shields.io/github/license/vvb7456/ptero_manager)
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)

## 核心功能

-   统一的服务器到期时间管理与续期。
-   自动化的服务器冻结、删除和到期邮件提醒。
-   友好的 Web UI，用于批量管理服务器和用户。
-   灵活的服务器创建和资源配置。

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

在部署前，请确保您的服务器满足以下条件：

-   **操作系统**: Linux (推荐 CentOS 7+, Debian 9+, Ubuntu 18.04+)
-   **Python**: 版本 3.8 或更高。
-   **Git**: 版本控制工具，用于获取项目代码。
-   **网络**: 服务器必须能访问您要管理的 Pterodactyl 面板的 URL。

### 2. 部署步骤

#### 第 1 步：克隆项目仓库

首先，使用 `git` 从 GitHub 克隆项目到您选择的目录，例如 `/opt`。

```bash
cd /opt
git clone https://github.com/vvb7456/ptero_manager.git
```

#### 第 2 步：创建并激活虚拟环境

进入项目目录，创建并激活 Python 虚拟环境。这能确保项目的依赖与系统其他 Python 应用隔离。

```bash
# 进入项目目录
cd /opt/ptero_manager

# 创建虚拟环境 (文件夹名为 venv)
python3 -m venv venv

# 激活虚拟环境 (后续所有命令都在此环境下执行)
source venv/bin/activate
```
成功激活后，您的命令行提示符前会显示 `(venv)`。

#### 第 3 步：安装依赖

在已激活的虚拟环境中，使用 `pip` 安装所有必需的 Python 包。

```bash
pip install -r requirements.txt
```

#### 第 4 步：创建并配置 `settings.json`

**这是一个关键步骤！** 包含所有敏感信息（如密码、API密钥）的 `settings.json` 文件已被 `.gitignore` 排除，不会被 Git 下载。您必须手动创建它。

1.  在项目根目录 `/opt/ptero_manager/` 创建 `settings.json` 文件。
2.  将下面的模板内容复制到文件中，并根据您的实际情况填写所有值。

```bash
nano settings.json
```

#### 第 5 步：授权管理脚本

为 `manager.sh` 脚本添加可执行权限。

```bash
chmod +x manager.sh
```

### 3. 核心配置 (`settings.json`)

这是 `settings.json` 的模板。**请务必用您的真实信息替换所有 `""` 和 `null` 的值。**

```json
{
    "ADMIN_PASSWORD": "your_super_secret_password",
    "PTERO_PANEL_URL": "https://panel.yourdomain.com",
    "PTERO_API_KEY": "your_pterodactyl_application_api_key",
    "SMTP_HOST": "smtp.yourprovider.com",
    "SMTP_PORT": 587,
    "SMTP_USE_SSL": false,
    "SENDER_EMAIL": "sender1@example.com,sender2@example.com",
    "SMTP_PASSWORD": "your_email_password_or_app_token",
    "AUTOMATION_SUSPEND_HOUR": 2,
    "AUTOMATION_DELETE_HOUR": 3,
    "AUTOMATION_DELETE_DAYS": 10,
    "AUTOMATION_REMIND_HOUR": 10,
    "DEFAULT_CPU": 100,
    "DEFAULT_RAM": 1024,
    "DEFAULT_DISK": 5120,
    "DEFAULT_BACKUPS": 1,
    "APP_TITLE": "艾萝工坊运维系统",
    "APP_LOGO_URL": "https://your-logo-url.com/logo.png"
}
```

### 4. 运行与管理

请 **不要** 直接使用 `python app.py` 运行。请务必使用 `manager.sh` 脚本，它会以后台守护进程模式启动 Gunicorn 生产服务器。

-   **启动服务**: `./manager.sh start`
-   **停止服务**: `./manager.sh stop`
-   **重启服务**: `./manager.sh restart`
-   **查看状态**: `./manager.sh status`

服务启动后，默认监听在 `0.0.0.0:5000`。

### 5. 生产环境部署 (systemd)

为了确保应用能在服务器重启后自动运行，并由系统统一管理，强烈建议使用 `systemd`。

1.  创建服务文件 `sudo nano /etc/systemd/system/ptero-manager.service`。
2.  将以下内容粘贴到文件中，并根据您的实际情况修改 `User` 和 `WorkingDirectory`。

    ```ini
    [Unit]
    Description=Ptero Manager Gunicorn Service
    After=network.target

    [Service]
    # 推荐使用非 root 用户运行
    User=www-data
    Group=www-data
    WorkingDirectory=/opt/ptero_manager
    
    # 确保虚拟环境中的 gunicorn 被调用
    ExecStart=/opt/ptero_manager/venv/bin/gunicorn --workers 3 --bind unix:ptero_manager.sock -m 007 wsgi:app --daemon --pid ptero_manager.pid --log-level=info --error-logfile logs/error.log --access-logfile logs/access.log
    ExecStop=/bin/kill -s TERM $(cat /opt/ptero_manager/ptero_manager.pid)
    ExecReload=/bin/kill -s HUP $(cat /opt/ptero_manager/ptero_manager.pid)
    
    Restart=always
    RestartSec=5s

    [Install]
    WantedBy=multi-user.target
    ```
    *注意：为提高安全性，此处的 `ExecStart` 示例已更新为使用 `gunicorn` 直接启动，并绑定到 socket 文件，这在与 Nginx 等反向代理结合使用时是更佳实践。如果您仅内网访问，原 `manager.sh` 脚本依然有效。*

3.  使用 `systemctl` 管理服务：
    -   `sudo systemctl daemon-reload`
    -   `sudo systemctl start ptero-manager`
    -   `sudo systemctl enable ptero-manager`
    -   `sudo systemctl status ptero-manager`

---

## 第二部分：系统使用手册

本部分面向日常使用此 Web 界面的操作人员。由于界面功能直观，此处仅作简要介绍。

### 1. 登录与仪表盘
访问 `http://<您的服务器IP>:5000`，输入您在 `settings.json` 中设置的 `ADMIN_PASSWORD` 即可登录。仪表盘提供系统核心指标的概览。

### 2. 服务器与用户管理
-   **服务器列表**：核心功能页面。可进行筛选、排序、搜索，并对单个或批量服务器进行续期、冻结/解冻、删除和发送邮件等操作。
-   **用户列表**：管理所有 Pterodactyl 用户，可编辑用户信息、查看其名下服务器或批量发送通知。

### 3. 创建服务器
通过可视化表单，为指定用户创建新服务器。需要依次选择用户、预设组(Nest)、预设(Egg)、节点，并配置资源。

### 4. 邮件与自动化
-   **邮件模板**：在 Web UI 中自定义批量邮件和到期提醒邮件的内容。支持 `{{username}}` 等变量。
-   **自动化**：配置自动冻结、自动删除和自动邮件提醒的执行时间和开关。
-   **重要提示**：**任何对系统设置（如API、密码）或自动化时间的修改，都必须重启应用服务 (`./manager.sh restart` 或 `sudo systemctl restart ptero-manager`) 才能完全生效。**