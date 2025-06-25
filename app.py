import os
import re
import math
import json
import requests
import smtplib
import time
import pytz
import logging
from logging.config import dictConfig
import random
import string
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, case, or_, desc, asc
from dotenv import load_dotenv
from datetime import date, timedelta, datetime
from urllib.parse import urlencode
from flask_apscheduler import APScheduler

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 全局时区配置 ---
LOCAL_TZ = pytz.timezone('Asia/Shanghai')

# --- 配置管理 ---
class ConfigManager:
    def __init__(self):
        self.settings_file = 'settings.json'
        self.config = {}
        self.load_config()

    def load_config(self):
        load_dotenv()
        self.config = {
            'SECRET_KEY': os.getenv('SECRET_KEY', 'a_default_secret_key_for_dev'),
            'ADMIN_PASSWORD': os.getenv('ADMIN_PASSWORD', 'changeme'), # 添加默认密码
            'PTERO_PANEL_URL': os.getenv('PTERO_PANEL_URL', ''),
            'PTERO_API_KEY': os.getenv('PTERO_API_KEY', ''),
            'DEFAULT_NEST_ID': int(os.getenv('DEFAULT_NEST_ID', 1)),
            'DEFAULT_EGG_ID': int(os.getenv('DEFAULT_EGG_ID', 1)),
            'DEFAULT_NODE_ID': int(os.getenv('DEFAULT_NODE_ID', 1)),
            'DOCKER_IMAGE': os.getenv('DOCKER_IMAGE', 'ghcr.io/pterodactyl/yolks:java_17'),
            'DEFAULT_CPU': int(os.getenv('DEFAULT_CPU', 100)),
            'DEFAULT_MEMORY': int(os.getenv('DEFAULT_MEMORY', 1024)),
            'DEFAULT_DISK': int(os.getenv('DEFAULT_DISK', 5120)),
            'DEFAULT_DATABASES': int(os.getenv('DEFAULT_DATABASES', 0)),
            'DEFAULT_BACKUPS': int(os.getenv('DEFAULT_BACKUPS', 0)),
            'DEFAULT_ALLOCATIONS': int(os.getenv('DEFAULT_ALLOCATIONS', 1)),
            'SMTP_HOST': os.getenv('SMTP_HOST', ''),
            'SMTP_PORT': int(os.getenv('SMTP_PORT', 587)),
            'SMTP_USE_SSL': os.getenv('SMTP_USE_SSL', 'true').lower() in ('true', '1', 't'),
            'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD', ''),
            'SENDER_EMAIL': os.getenv('SENDER_EMAIL', ''),
            'EMAIL_SEND_DELAY': int(os.getenv('EMAIL_SEND_DELAY', 2)),
            'AUTOMATION_SUSPEND_ENABLED': os.getenv('AUTOMATION_SUSPEND_ENABLED', 'false').lower() in ('true', '1', 't'),
            'AUTOMATION_DELETE_ENABLED': os.getenv('AUTOMATION_DELETE_ENABLED', 'false').lower() in ('true', '1', 't'),
            'AUTOMATION_EMAIL_ENABLED': os.getenv('AUTOMATION_EMAIL_ENABLED', 'false').lower() in ('true', '1', 't'),
            'AUTOMATION_RUN_HOUR': int(os.getenv('AUTOMATION_RUN_HOUR', 2)),
            'AUTOMATION_RUN_MINUTE': int(os.getenv('AUTOMATION_RUN_MINUTE', 0)),
            'AUTOMATION_DELETE_DAYS': int(os.getenv('AUTOMATION_DELETE_DAYS', 14)),
            'AUTOMATION_EMAIL_RUN_HOUR': int(os.getenv('AUTOMATION_EMAIL_RUN_HOUR', 10)),
            'AUTOMATION_EMAIL_RUN_MINUTE': int(os.getenv('AUTOMATION_EMAIL_RUN_MINUTE', 0)),
            'UI_SYSTEM_NAME': os.getenv('UI_SYSTEM_NAME', 'Pterodactyl 管理面板'),
            'UI_BANNER_URL': os.getenv('UI_BANNER_URL', ''),
        }
        
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                ui_settings = json.load(f)
                int_keys = [
                    'DEFAULT_NEST_ID', 'DEFAULT_EGG_ID', 'DEFAULT_NODE_ID', 'DEFAULT_CPU', 
                    'DEFAULT_MEMORY', 'DEFAULT_DISK', 'DEFAULT_DATABASES', 'DEFAULT_BACKUPS', 
                    'DEFAULT_ALLOCATIONS', 'SMTP_PORT', 'EMAIL_SEND_DELAY',
                    'AUTOMATION_RUN_HOUR', 'AUTOMATION_RUN_MINUTE', 'AUTOMATION_DELETE_DAYS',
                    'AUTOMATION_EMAIL_RUN_HOUR', 'AUTOMATION_EMAIL_RUN_MINUTE'
                ]
                for key in int_keys:
                    if key in ui_settings and ui_settings[key] is not None and ui_settings[key] != '':
                        ui_settings[key] = int(ui_settings[key])
                
                bool_keys = [
                    'SMTP_USE_SSL', 'AUTOMATION_SUSPEND_ENABLED', 
                    'AUTOMATION_DELETE_ENABLED', 'AUTOMATION_EMAIL_ENABLED'
                ]
                for key in bool_keys:
                    if key in ui_settings:
                        ui_settings[key] = str(ui_settings[key]).lower() in ('true', '1', 't')
                
                self.config.update(ui_settings)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        sender_emails_str = self.config.get('SENDER_EMAIL', '')
        if isinstance(sender_emails_str, str) and sender_emails_str:
            self.config['SENDER_EMAIL_LIST'] = [email.strip() for email in sender_emails_str.split(',') if email.strip()]
        else:
            self.config['SENDER_EMAIL_LIST'] = []

    def save_config(self, new_settings):
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                data_to_save = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data_to_save = {}
        
        data_to_save.update(new_settings)

        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        
        self.load_config()

    def get(self, key, default=None):
        return self.config.get(key, default)

config_manager = ConfigManager()
email_sender_index = 0

app = Flask(__name__)
app.config['SECRET_KEY'] = config_manager.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SCHEDULER_TIMEZONE'] = LOCAL_TZ

db = SQLAlchemy(app)
scheduler = APScheduler()

EMAIL_TEMPLATE_FILE = 'email_template.json'
REMINDER_TEMPLATE_FILE = 'reminder_template.json'
CREATE_USER_TEMPLATE_FILE = 'create_user_template.json'

@app.before_request
def check_auth():
    if not session.get('logged_in') and request.endpoint not in ('login', 'static'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password_attempt = request.form.get('password')
        admin_password = config_manager.get('ADMIN_PASSWORD')
        if password_attempt == admin_password:
            session['logged_in'] = True
            flash('登录成功！', 'success')
            next_url = request.args.get('next') or url_for('dashboard')
            return redirect(next_url)
        else:
            flash('密码错误，请重试。', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('您已成功退出登录。', 'info')
    return redirect(url_for('login'))

def get_today():
    return datetime.now(LOCAL_TZ).date()

@app.context_processor
def inject_ui_settings():
    return {
        'UI_SYSTEM_NAME': config_manager.get('UI_SYSTEM_NAME'),
        'UI_BANNER_URL': config_manager.get('UI_BANNER_URL'),
        'current_year': datetime.now(LOCAL_TZ).year
    }

class Server(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    ptero_server_id=db.Column(db.Integer,nullable=False)
    server_name=db.Column(db.String(100),nullable=False)
    expiration_date=db.Column(db.Date,nullable=True)
    owner_id=db.Column(db.Integer,nullable=True)
    owner_username=db.Column(db.String(100),nullable=True)
    status=db.Column(db.String(50),nullable=True)
    def __repr__(self): return f'<Server {self.server_name}>'

class Pagination:
    def __init__(self, page, per_page, total_count, items):
        self.page, self.per_page, self.total, self.items = page, per_page, total_count, items
    @property
    def pages(self): return math.ceil(self.total / self.per_page) if self.per_page > 0 else 0
    @property
    def has_prev(self): return self.page > 1
    @property
    def prev_num(self): return self.page - 1
    @property
    def has_next(self): return self.page < self.pages
    @property
    def next_num(self): return self.page + 1

def get_api_headers():
    return {"Authorization": f"Bearer {config_manager.get('PTERO_API_KEY')}", "Accept": "application/json", "Content-Type": "application/json"}

def handle_api_error(e, action):
    error_detail = str(e)
    try:
        if e.response is not None:
            response_json = e.response.json()
            errors = response_json.get('errors', [])
            error_messages = []
            for err in errors:
                detail = err.get('detail', 'Unknown error')
                meta = err.get('meta')
                if meta: detail += f" (Meta: {json.dumps(meta)})"
                error_messages.append(f"{err.get('code', 'N/A')}: {detail}")
            if error_messages: error_detail = '; '.join(error_messages)
    except Exception: pass
    flash(f"{action} API 请求失败: {error_detail}", "error")

def get_ptero_data(endpoint, params=None):
    all_items = []
    page = 1
    panel_url = config_manager.get('PTERO_PANEL_URL')
    if not panel_url or not config_manager.get('PTERO_API_KEY'): return None
    base_url = f"{panel_url.rstrip('/')}/api/application/{endpoint}"
    headers = get_api_headers()
    is_single_item_endpoint = re.search(r'/\d+(\?|$)', endpoint)
    while True:
        try:
            query_params = {'page': page, 'per_page': 100}
            if params: query_params.update(params)
            final_params = query_params if not is_single_item_endpoint else params
            res = requests.get(base_url, headers=headers, params=final_params, timeout=15)
            res.raise_for_status()
            data = res.json()
            if data.get('object') != 'list':
                return [data] if 'attributes' in data else []
            current_items = data.get('data', [])
            if not current_items: break
            all_items.extend(current_items)
            meta = data.get('meta', {}).get('pagination', {})
            current_page = meta.get('current_page')
            total_pages = meta.get('total_pages')
            if is_single_item_endpoint or current_page is None or total_pages is None or current_page >= total_pages: break
            page += 1
        except requests.RequestException as e:
            app.logger.error(f"Error fetching {endpoint}: {e}")
            handle_api_error(e, f"获取 {endpoint}")
            return None
    return all_items

def get_ptero_single_item(endpoint):
    panel_url = config_manager.get('PTERO_PANEL_URL')
    if not panel_url or not config_manager.get('PTERO_API_KEY'): return None
    try:
        res = requests.get(f"{panel_url.rstrip('/')}/api/application/{endpoint}", headers=get_api_headers(), timeout=10)
        res.raise_for_status()
        return res.json().get('attributes')
    except requests.RequestException: return None

def _sync_database_with_pterodactyl():
    api_servers_list = get_ptero_data("servers", params={'include': 'user'})
    if api_servers_list is None: return False

    local_servers = {s.ptero_server_id: s for s in Server.query.all()}
    api_server_ids = {s['attributes']['id'] for s in api_servers_list}
    
    for server_data in api_servers_list:
        attrs = server_data['attributes']
        ptero_id = attrs['id']
        
        owner_username = '未知'
        if 'user' in attrs.get('relationships', {}) and attrs['relationships']['user'].get('attributes'):
            owner_username = attrs['relationships']['user']['attributes'].get('username', '未知')

        if ptero_id in local_servers:
            local_server = local_servers[ptero_id]
            if local_server.server_name != attrs['name']: local_server.server_name = attrs['name']
            if local_server.owner_id != attrs['user']: local_server.owner_id = attrs['user']
            if local_server.owner_username != owner_username: local_server.owner_username = owner_username
            if local_server.uuid != attrs['uuid']: local_server.uuid = attrs['uuid']
            
            api_install_status = attrs.get('status')
            if local_server.status == '安装中' and api_install_status != 'installing':
                local_server.status = None
            
            api_is_suspended = attrs.get('suspended', False)
            if api_is_suspended and local_server.status != '已冻结':
                local_server.status = '已冻结'
            elif not api_is_suspended and local_server.status == '已冻结':
                 local_server.status = None
        else:
            expiration_date = None
            description = attrs.get('description', '')
            match = re.search(r'到期时间[：:]\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})', description or '')
            if match:
                try: expiration_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                except ValueError: pass
            
            new_server = Server(
                ptero_server_id=ptero_id, uuid=attrs['uuid'], server_name=attrs['name'],
                owner_id=attrs['user'], owner_username=owner_username,
                expiration_date=expiration_date, status='已冻结' if attrs.get('suspended') else None
            )
            db.session.add(new_server)

    for local_id in list(local_servers.keys()):
        if local_id not in api_server_ids:
            db.session.delete(local_servers[local_id])
            
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"同步过程中发生数据库错误: {e}")
        return False
    return True

def update_ptero_description(server_ptero_id, new_expiration_date=None):
    panel_url = config_manager.get('PTERO_PANEL_URL')
    if not panel_url: return False
    server_data_list = get_ptero_data(f"servers/{server_ptero_id}")
    if not server_data_list:
        flash(f"无法从 API 获取服务器 {server_ptero_id} 的当前详情，无法更新描述。", "error")
        return False
    server_details_from_api = server_data_list[0]['attributes']
    current_desc = server_details_from_api.get('description', '') or ''
    new_desc_base = re.sub(r'到期时间[：:][^\n]*\n?|\n?到期时间[：:][^\n]*', '', current_desc, flags=re.MULTILINE).strip()
    new_desc = f"到期时间：{new_expiration_date.strftime('%Y/%m/%d')}\n{new_desc_base}".strip() if new_expiration_date else new_desc_base
    details_payload = {"name": server_details_from_api['name'], "user": server_details_from_api['user'], "description": new_desc}
    try:
        res = requests.patch(f"{panel_url.rstrip('/')}/api/application/servers/{server_ptero_id}/details", headers=get_api_headers(), json=details_payload, timeout=20)
        res.raise_for_status()
        return True
    except requests.RequestException as e:
        handle_api_error(e, f"更新服务器 {server_ptero_id} 的描述")
        return False

def create_ptero_user(email, username):
    panel_url = config_manager.get('PTERO_PANEL_URL').rstrip('/')
    api_url = f"{panel_url}/api/application/users"
    headers = get_api_headers()
    password = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12)) # 密码加长以增加安全性

    try:
        # 步骤 1: 创建用户，但不包含密码，以阻止 Pterodactyl 发送邮件
        create_payload = {
            "email": email, 
            "username": username, 
            "first_name": "New", 
            "last_name": "User",
            "root_admin": False
        }
        res_create = requests.post(api_url, headers=headers, json=create_payload, timeout=20)
        res_create.raise_for_status()
        new_user_data = res_create.json()
        user_id = new_user_data['attributes']['id']

        # 步骤 2: 立即更新用户，为其设置密码
        update_url = f"{api_url}/{user_id}"
        update_payload = {"password": password}
        res_update = requests.patch(update_url, headers=headers, json=update_payload, timeout=20)
        res_update.raise_for_status()

        # 步骤 3: 发送我们自己的、完全可控的欢迎邮件
        template = load_create_user_template()
        body_raw = template.get('body', '')
        # 确保模板中的 {{password}} 变量被替换
        final_body = body_raw.replace('{{username}}', username).replace('{{password}}', password)

        send_email(
            recipient_email=email,
            subject=template.get('subject'),
            main_content_raw=final_body,
            greeting=f"您好, {username}!",
            action_text="点此登录您的账户",
            action_url=panel_url
        )
        
        flash(f"用户 '{username}' 创建成功！初始密码已通过邮件发送至 {email}。", "success")
        return new_user_data['attributes']

    except requests.RequestException as e:
        handle_api_error(e, f"创建用户 '{username}'")
        return None

def create_ptero_server(user_id, server_name, expiration_days, node_id, allocation_id, egg_id, docker_image, startup_command, environment, cpu, memory, disk, databases, backups, allocations):
    expiration_date = get_today() + timedelta(days=expiration_days)
    description = f"到期时间：{expiration_date.strftime('%Y/%m/%d')}"
    api_url = f"{config_manager.get('PTERO_PANEL_URL').rstrip('/')}/api/application/servers"
    payload = {"name": server_name, "user": user_id, "egg": egg_id, "description": description, "docker_image": docker_image, "startup": startup_command, "environment": environment, "limits": {"memory": memory, "swap": 0, "disk": disk, "io": 500, "cpu": cpu}, "feature_limits": {"databases": databases, "allocations": allocations, "backups": backups}, "allocation": {"default": allocation_id}}
    try:
        res = requests.post(api_url, headers=get_api_headers(), json=payload, timeout=20)
        res.raise_for_status()
        server_data = res.json().get('attributes')
        user_info = get_ptero_single_item(f"users/{user_id}")
        owner_username = user_info.get('username', '未知') if user_info else '未知'
        new_server = Server(ptero_server_id=server_data.get('id'), uuid=server_data.get('uuid'), server_name=server_data.get('name'), owner_id=server_data.get('user'), owner_username=owner_username, expiration_date=expiration_date, status="安装中")
        db.session.add(new_server)
        db.session.commit()
        return server_data
    except requests.RequestException as e:
        handle_api_error(e, "创建服务器")
        return None

def load_email_template():
    try:
        with open(EMAIL_TEMPLATE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {"subject": "来自 {{panel_name}} 的通知", "body": "这是一封通知邮件。", "panel_name": "艾萝工坊运维系统"}

def save_email_template(data):
    with open(EMAIL_TEMPLATE_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

def load_reminder_template():
    try:
        with open(REMINDER_TEMPLATE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"subject": "【重要】您的服务器即将到期", "body": "您好！\n\n您在 {{panel_name}} 的 {{server_count}} 台服务器将于 {{expiration_date}} 到期。\n\n服务器列表:\n{{server_list}}\n\n请及时处理。"}

def save_reminder_template(data):
    with open(REMINDER_TEMPLATE_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

def load_create_user_template():
    try:
        with open(CREATE_USER_TEMPLATE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"subject": "欢迎！您的新账户已创建成功", "body": "您的账户已经成功创建。\n\n登录用户名: {{username}}\n初始密码: {{password}}\n\n请尽快登录面板修改您的密码。\n\n使用教程: https://www.erocraft.com/silly-tavern/\n\n祝您使用愉快！"}

def save_create_user_template(data):
    with open(CREATE_USER_TEMPLATE_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

def send_email(recipient_email, subject, main_content_raw, greeting, action_text=None, action_url=None):
    global email_sender_index
    cfg = config_manager.config
    sender_email_list = cfg.get('SENDER_EMAIL_LIST', [])

    # 增强检查：确保所有必要配置都存在且邮箱池不为空
    if not all([cfg.get('SMTP_HOST'), cfg.get('SMTP_PORT'), cfg.get('SMTP_PASSWORD'), sender_email_list]):
        error_msg = "SMTP配置不完整或发件人邮箱池为空，请检查系统设置。"
        app.logger.error(error_msg)
        return False, error_msg

    # 在访问列表前再次确认列表长度，防止除零错误
    num_senders = len(sender_email_list)
    if num_senders == 0:
        error_msg = "发件人邮箱池在运行时变为空，无法发送邮件。"
        app.logger.error(error_msg)
        return False, error_msg
        
    current_sender_email = sender_email_list[email_sender_index % num_senders]
    email_sender_index += 1
    
    panel_name = load_email_template().get('panel_name', 'Pterodactyl')
    panel_url = config_manager.get('PTERO_PANEL_URL')
    
    # 将文本换行符转换成HTML换行符
    main_content_html = main_content_raw.replace('\n', '<br>')
    
    html_body = render_template('email_base.html', 
                                panel_name=panel_name,
                                panel_url=panel_url,
                                greeting=greeting, 
                                main_content=main_content_html,
                                action_text=action_text,
                                action_url=action_url)
    
    msg = MIMEText(html_body, 'html', 'utf-8')
    msg['From'] = formataddr((Header(panel_name, 'utf-8').encode(), current_sender_email))
    msg['To'] = recipient_email
    msg['Subject'] = Header(subject, 'utf-8')

    try:
        server_class = smtplib.SMTP_SSL if cfg['SMTP_USE_SSL'] else smtplib.SMTP
        with server_class(cfg['SMTP_HOST'], int(cfg['SMTP_PORT']), timeout=20) as server:
            if not cfg['SMTP_USE_SSL']: server.starttls()
            server.login(current_sender_email, cfg['SMTP_PASSWORD'])
            server.sendmail(current_sender_email, [recipient_email], msg.as_string())
        app.logger.info(f"邮件已成功发送至 {recipient_email}")
        return True, "发送成功"
    except Exception as e:
        app.logger.error(f"邮件发送失败 to {recipient_email}: {e}", exc_info=True)
        return False, str(e)

def get_redirect_params(form_data):
    view_args = {}
    valid_keys = ['page', 'per_page', 'filter_status', 'sort_by', 'sort_order', 'owner_id', 'search_term', 'filter_server_status']
    for key in valid_keys:
        if key in form_data: view_args[key] = form_data[key]
    return view_args

def get_processed_servers_data(args):
    query = Server.query
    filter_status = args.get('filter_status', 'all')
    sort_by = args.get('sort_by', 'expiration_date')
    sort_order = args.get('sort_order', 'asc')
    search_term = args.get('search_term', '').strip()

    if search_term:
        query = query.filter(or_(Server.server_name.ilike(f'%{search_term}%'), Server.owner_username.ilike(f'%{search_term}%')))
    
    today = get_today()
    if filter_status == 'normal': query = query.filter(Server.expiration_date >= today)
    elif filter_status == 'expiring_soon': query = query.filter(Server.expiration_date.between(today, today + timedelta(days=7)))
    elif filter_status == 'expired': query = query.filter(Server.expiration_date < today)
    elif filter_status == 'permanent': query = query.filter(Server.expiration_date.is_(None))
    
    sort_column = getattr(Server, sort_by, Server.ptero_server_id)
    if sort_by == 'expiration_date':
        if sort_order == 'asc':
             query = query.order_by(sort_column.asc().nulls_last())
        else:
             query = query.order_by(sort_column.desc().nulls_first())
    else:
        if sort_order == 'desc':
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
    return query.all()

def get_processed_users_data(args):
    users_data = get_ptero_data("users")
    if users_data is None:
        return None
    all_users = [u['attributes'] for u in users_data]
    search_term = args.get('search_term', '').strip()
    filter_server_status = args.get('filter_server_status', 'all')
    sort_by = args.get('sort_by', 'username')
    sort_order = args.get('sort_order', 'asc')

    if search_term:
        search_term_lower = search_term.lower()
        all_users = [u for u in all_users if search_term_lower in u.get('username', '').lower() or search_term_lower in u.get('email', '').lower()]
    
    server_counts = dict(db.session.query(Server.owner_id, func.count(Server.owner_id)).group_by(Server.owner_id).all())
    for user in all_users:
        user['server_count'] = server_counts.get(user['id'], 0)

    if filter_server_status == 'has_servers': all_users = [u for u in all_users if u['server_count'] > 0]
    elif filter_server_status == 'no_servers': all_users = [u for u in all_users if u['server_count'] == 0]
    
    reverse = sort_order == 'desc'
    sort_key_map = {'username': lambda u: u.get('username', '').lower(), 'id': lambda u: u.get('id', 0), 'server_count': lambda u: u.get('server_count', 0)}
    all_users.sort(key=sort_key_map.get(sort_by, sort_key_map['username']), reverse=reverse)
    return all_users

@app.route('/')
def dashboard():
    _sync_database_with_pterodactyl()
    if not all([config_manager.get('PTERO_PANEL_URL'), config_manager.get('PTERO_API_KEY')]):
        flash("Pterodactyl API 未配置，无法加载仪表盘数据。", "error")
        return render_template('dashboard.html', page_title="仪表盘", dashboard_data=None)

    total_users = len(get_ptero_data("users") or [])
    local_servers_list = Server.query.all()
    total_servers = len(local_servers_list)
    
    status_counts = {'normal': 0, 'expiring_soon': 0, 'expired': 0, 'suspended': 0, 'permanent': 0}
    today = get_today()
    for s in local_servers_list:
        if s.status == '已冻结': status_counts['suspended'] += 1
        if s.expiration_date is None: status_counts['permanent'] += 1
        else:
            days_left = (s.expiration_date - today).days
            if days_left < 0: status_counts['expired'] += 1
            elif days_left <= 7: status_counts['expiring_soon'] += 1
            else: status_counts['normal'] += 1
            
    normal_servers_count = status_counts['normal'] + status_counts['expiring_soon'] + status_counts['permanent']
    dashboard_data = {
        'core_metrics': { 'total_users': total_users, 'total_servers': total_servers, 'normal_servers_count': normal_servers_count, },
        'status_distribution': { 'labels': ['正常', '即将到期', '已到期', '已冻结', '永久'], 'counts': [status_counts['normal'], status_counts['expiring_soon'], status_counts['expired'], status_counts['suspended'], status_counts['permanent']], }
    }
    return render_template('dashboard.html', page_title="仪表盘", dashboard_data=dashboard_data)

@app.route('/servers')
def servers_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    all_servers = get_processed_servers_data(request.args)
    pagination = Pagination(page, per_page, len(all_servers), all_servers[(page-1)*per_page:page*per_page])
    context = {'page_title': "服务器列表", 'servers': pagination.items, 'today': get_today(), 'PANEL_URL': config_manager.get('PTERO_PANEL_URL', '').rstrip('/')}
    context.update(request.args.to_dict())
    return render_template('dashboard.html', **context)

@app.route('/users')
def users_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    all_users = get_processed_users_data(request.args)
    if all_users is None:
        flash("无法从 Pterodactyl API 获取用户列表。", "error")
        return render_template('dashboard.html', page_title="用户列表", users=[], **request.args.to_dict())
    pagination = Pagination(page, per_page, len(all_users), all_users[(page-1)*per_page:page*per_page])
    return render_template('dashboard.html', page_title="用户列表", users=pagination.items, **request.args.to_dict())

# ... (API routes for infinite scroll are unchanged)
@app.route('/api/load_servers')
def api_load_servers():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    all_servers = get_processed_servers_data(request.args)
    pagination = Pagination(page, per_page, len(all_servers), all_servers[(page-1)*per_page:page*per_page])
    rendered_html = render_template('_server_rows.html', servers=pagination.items, today=get_today(), PANEL_URL=config_manager.get('PTERO_PANEL_URL', '').rstrip('/'), request=request)
    return jsonify({"html": rendered_html, "has_more": pagination.has_next})

@app.route('/api/load_users')
def api_load_users():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    all_users = get_processed_users_data(request.args)
    if all_users is None: return jsonify({"html": "", "has_more": False})
    pagination = Pagination(page, per_page, len(all_users), all_users[(page-1)*per_page:page*per_page])
    rendered_html = render_template('_user_rows.html', users=pagination.items, request=request)
    return jsonify({"html": rendered_html, "has_more": pagination.has_next})

@app.route('/set_expiry/<int:ptero_id>', methods=['POST'])
def set_expiry(ptero_id):
    server = Server.query.filter_by(ptero_server_id=ptero_id).first_or_404()
    try: days = int(request.form['renew_days'])
    except (ValueError, KeyError): flash("续期天数无效。", "error"); return redirect(url_for('servers_list', **request.args))
    today = get_today()
    new_date = (server.expiration_date or today) + timedelta(days=days)
    if update_ptero_description(ptero_id, new_date):
        server.expiration_date = new_date; db.session.commit()
        flash(f"服务器 '{server.server_name}' 已成功续期至 {new_date.strftime('%Y-%m-%d')}。", "success")
    else:
        db.session.rollback(); flash(f"服务器 '{server.server_name}' 续期失败，无法更新面板。", "error")
    return redirect(url_for('servers_list', **request.args))

# ... (suspend_server and delete_server are unchanged)
@app.route('/suspend/<int:ptero_id>', methods=['POST'])
def suspend_server(ptero_id):
    server = Server.query.filter_by(ptero_server_id=ptero_id).first_or_404()
    action = 'unsuspend' if server.status == '已冻结' else 'suspend'
    action_text = '解冻' if action == 'unsuspend' else '冻结'
    api_url = f"{config_manager.get('PTERO_PANEL_URL').rstrip('/')}/api/application/servers/{ptero_id}/{action}"
    try:
        res = requests.post(api_url, headers=get_api_headers(), timeout=20); res.raise_for_status()
        server.status = None if action == 'unsuspend' else '已冻结'; db.session.commit()
        flash(f"服务器 '{server.server_name}' 已成功{action_text}。", "success")
    except requests.RequestException as e: handle_api_error(e, f"{action_text}服务器 '{server.server_name}'")
    return redirect(url_for('servers_list', **request.args))

@app.route('/delete/<int:ptero_id>', methods=['POST'])
def delete_server(ptero_id):
    server = Server.query.filter_by(ptero_server_id=ptero_id).first()
    server_name = server.server_name if server else f"ID {ptero_id}"
    api_url = f"{config_manager.get('PTERO_PANEL_URL').rstrip('/')}/api/application/servers/{ptero_id}"
    try:
        res = requests.delete(api_url, headers=get_api_headers(), timeout=20)
        if res.status_code not in [204, 404]: res.raise_for_status()
        if server: db.session.delete(server); db.session.commit()
        flash(f"服务器 '{server_name}' 已成功删除。", "success")
    except requests.RequestException as e: handle_api_error(e, f"删除服务器 '{server_name}'")
    return redirect(url_for('servers_list', **request.args))

@app.route('/batch_process', methods=['POST'])
def batch_process():
    action = request.form.get('action'); server_ids = [int(sid) for sid in request.form.getlist('server_ids')]; redirect_params = get_redirect_params(request.form); redirect_url = url_for('servers_list', **redirect_params)
    if not action or not server_ids: flash("未选择任何操作或服务器。", "error"); return redirect(redirect_url)
    panel_url = config_manager.get('PTERO_PANEL_URL').rstrip('/')
    if not panel_url: flash("Pterodactyl 面板地址未配置。", "error"); return redirect(redirect_url)
    success_count, error_count = 0, 0; headers = get_api_headers()
    
    if action == 'email':
        template_data = load_email_template()
        servers = db.session.query(Server).filter(Server.ptero_server_id.in_(server_ids)).all()
        all_users_data = get_ptero_data("users")
        if not all_users_data:
            flash("无法从API获取用户列表以发送邮件。", "error")
            return redirect(redirect_url)
        
        users_map = {u['attributes']['id']: u['attributes'] for u in all_users_data}
        panel_name = template_data.get('panel_name', '')

        for server in servers:
            user = users_map.get(server.owner_id)
            if not user or not user.get('email'):
                error_count += 1
                continue
            
            # 构建一个完整的上下文变量字典
            context = {
                '{{panel_name}}': panel_name,
                '{{username}}': user.get('username', '未知用户'),
                '{{email}}': user.get('email', ''),
                '{{server_name}}': server.server_name,
                '{{server_id}}': str(server.ptero_server_id),
                '{{expiration_date}}': server.expiration_date.strftime('%Y-%m-%d') if server.expiration_date else '永久'
            }
            
            # 从模板获取原始主题和正文
            final_subject = template_data.get('subject', '通知')
            final_body = template_data.get('body', '')
            
            # 在主题和正文中统一替换所有变量
            for key, value in context.items():
                final_subject = final_subject.replace(key, str(value))
                final_body = final_body.replace(key, str(value))

            sent, _ = send_email(
                recipient_email=user['email'],
                subject=final_subject,
                main_content_raw=final_body,
                greeting=f"您好, {user.get('username', '用户')}!",
                action_text="登录面板查看",
                action_url=panel_url
            )
            if sent:
                success_count += 1
            else:
                error_count += 1
            time.sleep(config_manager.get('EMAIL_SEND_DELAY', 2))
            
        flash(f"邮件任务完成：成功 {success_count} 封，失败 {error_count} 封。", "info")
    # ... (Other batch actions are unchanged)
    elif action in ['suspend', 'unsuspend']:
        action_text = '冻结' if action == 'suspend' else '解冻'
        for server_id in server_ids:
            try:
                res = requests.post(f"{panel_url}/api/application/servers/{server_id}/{action}", headers=headers, timeout=20); res.raise_for_status()
                server = Server.query.filter_by(ptero_server_id=server_id).first()
                if server: server.status = '已冻结' if action == 'suspend' else None
                success_count += 1
            except requests.RequestException: error_count += 1
        db.session.commit(); flash(f"批量{action_text}操作完成：成功 {success_count}，失败 {error_count}。", "info")

    elif action == 'renew':
        renew_days = request.form.get('renew_days', type=int)
        if not renew_days or renew_days <= 0: flash("请输入有效的续期天数。", "error"); return redirect(redirect_url)
        servers_to_renew = Server.query.filter(Server.ptero_server_id.in_(server_ids)).all()
        today = get_today()
        for server in servers_to_renew:
            new_date = (server.expiration_date or today) + timedelta(days=renew_days)
            if update_ptero_description(server.ptero_server_id, new_date):
                server.expiration_date = new_date; success_count +=1
            else: error_count += 1
        db.session.commit(); flash(f"批量续期操作完成：成功 {success_count}，失败 {error_count}。", "info")

    elif action == 'delete':
        for server_id in server_ids:
            try:
                res = requests.delete(f"{panel_url}/api/application/servers/{server_id}", headers=headers, timeout=20)
                if res.status_code not in [204, 404]: res.raise_for_status()
                server = Server.query.filter_by(ptero_server_id=server_id).first()
                if server: db.session.delete(server)
                success_count += 1
            except requests.RequestException: error_count += 1
        if success_count > 0: db.session.commit()
        flash(f"批量删除操作完成：成功 {success_count}，失败 {error_count}。", "info")

    return redirect(redirect_url)

@app.route('/batch_process_users', methods=['POST'])
def batch_process_users():
    app.logger.info("[DEBUG] Entering batch_process_users function.")
    action = request.form.get('action')
    user_ids_str = request.form.getlist('user_ids')
    if not user_ids_str:
        flash("没有选择任何用户。", "error")
        return redirect(url_for('users_list', **get_redirect_params(request.form)))
        
    user_ids = [int(uid) for uid in user_ids_str]
    redirect_params = get_redirect_params(request.form)
    redirect_url = url_for('users_list', **redirect_params)
    
    if not action or not user_ids:
        flash("未选择任何操作或用户。", "error")
        return redirect(redirect_url)
        
    panel_url = config_manager.get('PTERO_PANEL_URL').rstrip('/')
    if not panel_url:
        flash("Pterodactyl 面板地址未配置。", "error")
        return redirect(redirect_url)
        
    success_count, error_count = 0, 0
    headers = get_api_headers()
    
    app.logger.info(f"[DEBUG] Action: {action}, User IDs: {user_ids}")
    
    if action == 'email':
        try:
            app.logger.info("[DEBUG] Email action started.")
            template_data = load_email_template()
            app.logger.info(f"[DEBUG] Email template loaded: {template_data.get('subject')}")
            
            all_users_data = get_ptero_data("users")
            if not all_users_data:
                flash("无法从API获取用户列表以发送邮件。", "error")
                app.logger.error("[DEBUG] Failed to get user list from Pterodactyl API.")
                return redirect(redirect_url)
            
            selected_user_ids = set(user_ids)
            users_to_email = [u['attributes'] for u in all_users_data if u.get('attributes', {}).get('id') in selected_user_ids]
            app.logger.info(f"[DEBUG] Found {len(users_to_email)} users to email.")
            
            panel_name = template_data.get('panel_name', '')

            for i, user in enumerate(users_to_email):
                app.logger.info(f"[DEBUG] Processing user #{i+1}: {user.get('username')}")
                if not user.get('email'):
                    error_count += 1
                    app.logger.warning(f"[DEBUG] User {user.get('username')} has no email, skipping.")
                    continue
                
                context = {
                    '{{panel_name}}': panel_name,
                    '{{username}}': user.get('username', '未知用户'),
                    '{{email}}': user.get('email', ''),
                    '{{server_name}}': '(不适用)',
                    '{{server_id}}': '(不适用)',
                    '{{expiration_date}}': '(不适用)'
                }
                
                final_subject = template_data.get('subject', '通知')
                final_body = template_data.get('body', '')
                
                for key, value in context.items():
                    final_subject = final_subject.replace(key, str(value))
                    final_body = final_body.replace(key, str(value))
                
                app.logger.info(f"[DEBUG] Preparing to send email to {user['email']} with subject: {final_subject}")
                sent, msg = send_email(
                    recipient_email=user['email'],
                    subject=final_subject,
                    main_content_raw=final_body,
                    greeting=f"您好, {user.get('username', '用户')}!",
                    action_text="登录面板查看",
                    action_url=panel_url
                )
                
                if sent:
                    success_count += 1
                    app.logger.info(f"[DEBUG] Email sent successfully to {user['email']}.")
                else:
                    error_count += 1
                    app.logger.error(f"[DEBUG] Email failed to send to {user['email']}. Reason: {msg}")

                time.sleep(config_manager.get('EMAIL_SEND_DELAY', 2))

            flash(f"邮件任务完成：成功 {success_count} 封，失败 {error_count} 封。", "info")

        except Exception as e:
            app.logger.error("[CRITICAL] Unhandled exception in 'email' action block.", exc_info=True)
            # exc_info=True 将会把完整的错误堆栈打印到日志中
            flash("处理邮件任务时发生严重内部错误，请查看日志。", "error")

    elif action == 'delete':
        # (您的删除用户逻辑放在这里，之前已修复)
        for user_id in user_ids:
            try:
                servers_to_delete = Server.query.filter_by(owner_id=user_id).all()
                for server in servers_to_delete:
                    delete_url = f"{panel_url}/api/application/servers/{server.ptero_server_id}"
                    delete_res = requests.delete(delete_url, headers=headers, timeout=20)
                    if delete_res.status_code not in [204, 404]:
                        delete_res.raise_for_status()
                    db.session.delete(server)

                user_delete_url = f"{panel_url}/api/application/users/{user_id}"
                user_delete_res = requests.delete(user_delete_url, headers=headers, timeout=20)
                if user_delete_res.status_code not in [204, 404]:
                    user_delete_res.raise_for_status()
                
                success_count += 1
                db.session.commit()
            except requests.RequestException as e:
                db.session.rollback()
                handle_api_error(e, f"删除用户ID {user_id} 及其服务器时出错")
                error_count += 1
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"处理用户删除时发生未知错误: {e}", exc_info=True)
                error_count += 1
        flash(f"批量删除用户操作完成：成功 {success_count}，失败 {error_count}。", "info")

    return redirect(redirect_url)

# ... (All routes from edit_user to the end are mostly unchanged, but I provide them for completeness)
@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    redirect_url = url_for('users_list', **request.args); panel_url = config_manager.get('PTERO_PANEL_URL').rstrip('/')
    if not panel_url: flash("Pterodactyl 面板地址未配置。", "error"); return redirect(redirect_url)
    if request.method == 'POST':
        payload = {"username": request.form['username'], "email": request.form['email'], "first_name": request.form['first_name'], "last_name": request.form['last_name']}
        if request.form.get('password'): payload['password'] = request.form['password']
        try:
            res = requests.patch(f"{panel_url}/api/application/users/{user_id}", headers=get_api_headers(), json=payload, timeout=20); res.raise_for_status()
            flash(f"用户 {payload['username']} 的信息已成功更新。", "success")
            Server.query.filter_by(owner_id=user_id).update({'owner_username': payload['username']}); db.session.commit()
        except requests.RequestException as e: handle_api_error(e, f"更新用户 {request.form['username']}")
        return redirect(redirect_url)
    user_data = get_ptero_single_item(f"users/{user_id}")
    if not user_data: flash(f"无法获取 User ID: {user_id} 的信息。", "error"); return redirect(redirect_url)
    return render_template('edit_user.html', user=user_data)

@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        submit_action = request.form.get('submit_action')
        if not email or not username:
            flash("邮箱和用户名不能为空。", "error"); return redirect(url_for('create_user'))
        new_user = create_ptero_user(email, username)
        if new_user:
            if submit_action == 'create_and_server':
                return redirect(url_for('create_server_page', new_user_id=new_user['id']))
            else:
                return redirect(url_for('users_list'))
        return redirect(url_for('create_user'))
    return render_template('dashboard.html', page_title="创建新用户")

@app.route('/create_server', methods=['GET', 'POST'])
def create_server_page():
    if request.method == 'POST':
        try:
            cfg = config_manager.config
            user_id = int(request.form.get('user_id')); server_name = request.form.get('server_name', '').strip()
            egg_id = int(request.form.get('egg_id')); docker_image = request.form.get('docker_image', cfg.get('DOCKER_IMAGE')).strip()
            startup_command = request.form.get('startup_command', '').strip(); node_id = int(request.form.get('node_id'))
            allocation_id = int(request.form.get('allocation_id')); expiration_days = int(request.form.get('expiration_days'))
            environment = {key[len('environment['):-1]: value for key, value in request.form.items() if key.startswith('environment[')}
            cpu = int(request.form.get('cpu') or cfg.get('DEFAULT_CPU')); memory = int(request.form.get('memory') or cfg.get('DEFAULT_MEMORY'))
            disk = int(request.form.get('disk') or cfg.get('DEFAULT_DISK')); databases = int(request.form.get('databases') or cfg.get('DEFAULT_DATABASES'))
            backups = int(request.form.get('backups') or cfg.get('DEFAULT_BACKUPS')); allocations = int(request.form.get('allocations') or cfg.get('DEFAULT_ALLOCATIONS'))
            if not all([user_id, node_id, allocation_id, server_name, egg_id, startup_command]): raise ValueError("必填字段缺失")
        except (ValueError, TypeError):
            flash("所有必填字段均为必填项，且资源配置需为有效整数。", "error"); return redirect(url_for('create_server_page'))
        if create_ptero_server(user_id, server_name, expiration_days, node_id, allocation_id, egg_id, docker_image, startup_command, environment, cpu, memory, disk, databases, backups, allocations):
            flash(f"服务器 '{server_name}' 创建成功！", "success"); return redirect(url_for('servers_list'))
        return redirect(url_for('create_server_page'))
    
    new_user_id = request.args.get('new_user_id', type=int)
    all_users_data = get_ptero_data("users"); all_nodes_data = get_ptero_data("nodes"); all_nests_data = get_ptero_data("nests")
    defaults = {k.replace('DEFAULT_', '').lower(): v for k, v in config_manager.config.items() if k.startswith('DEFAULT_')}
    return render_template('dashboard.html', page_title="创建服务器", all_users=[u['attributes'] for u in all_users_data] if all_users_data else [], all_nodes=[n['attributes'] for n in all_nodes_data] if all_nodes_data else [], all_nests=[n['attributes'] for n in all_nests_data] if all_nests_data else [], defaults=defaults, new_user_id=new_user_id, **config_manager.config)

@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        old_url = config_manager.get('PTERO_PANEL_URL'); old_key = config_manager.get('PTERO_API_KEY')
        form_data = request.form.to_dict()
        settings_to_save = {key: value for key, value in form_data.items()}
        settings_to_save['SMTP_USE_SSL'] = 'SMTP_USE_SSL' in form_data
        if not form_data.get('PTERO_API_KEY'): settings_to_save.pop('PTERO_API_KEY', None)
        if not form_data.get('SMTP_PASSWORD'): settings_to_save.pop('SMTP_PASSWORD', None)
        if not form_data.get('ADMIN_PASSWORD'): settings_to_save.pop('ADMIN_PASSWORD', None)
        config_manager.save_config(settings_to_save)
        new_url = config_manager.get('PTERO_PANEL_URL'); new_key = config_manager.get('PTERO_API_KEY')
        if new_url != old_url or new_key != old_key:
            try:
                num_rows_deleted = db.session.query(Server).delete(); db.session.commit()
                if num_rows_deleted > 0: flash(f"检测到面板URL或API Key已更改，已清除 {num_rows_deleted} 条本地缓存。", "info")
            except Exception as e: db.session.rollback(); app.logger.error(f"清除本地数据时出错: {e}")
        flash("系统设置已成功保存！重启应用后生效。", "success")
        return redirect(url_for('settings_page'))
    settings_display = {k: ('********' if any(s in k for s in ['KEY', 'PASSWORD']) and v else v) for k, v in config_manager.config.items()}
    all_nests_data = get_ptero_data("nests"); all_nodes_data = get_ptero_data("nodes")
    all_nests = [n['attributes'] for n in all_nests_data] if all_nests_data else []
    all_nodes = [n['attributes'] for n in all_nodes_data] if all_nodes_data else []
    all_eggs = []
    if (current_nest_id_str := config_manager.get('DEFAULT_NEST_ID')):
        if (all_eggs_data := get_ptero_data(f"nests/{current_nest_id_str}/eggs")):
            all_eggs = [e['attributes'] for e in all_eggs_data]
    return render_template('dashboard.html', page_title="系统设置", settings=settings_display, all_nests=all_nests, all_nodes=all_nodes, all_eggs=all_eggs)
    
@app.route('/automation', methods=['GET', 'POST'])
def automation_page():
    if request.method == 'POST':
        automation_settings = {
            'AUTOMATION_RUN_HOUR': request.form.get('AUTOMATION_RUN_HOUR'), 'AUTOMATION_RUN_MINUTE': request.form.get('AUTOMATION_RUN_MINUTE'),
            'AUTOMATION_DELETE_DAYS': request.form.get('AUTOMATION_DELETE_DAYS'), 'AUTOMATION_EMAIL_RUN_HOUR': request.form.get('AUTOMATION_EMAIL_RUN_HOUR'),
            'AUTOMATION_EMAIL_RUN_MINUTE': request.form.get('AUTOMATION_EMAIL_RUN_MINUTE'), 'AUTOMATION_SUSPEND_ENABLED': 'AUTOMATION_SUSPEND_ENABLED' in request.form,
            'AUTOMATION_DELETE_ENABLED': 'AUTOMATION_DELETE_ENABLED' in request.form, 'AUTOMATION_EMAIL_ENABLED': 'AUTOMATION_EMAIL_ENABLED' in request.form
        }
        config_manager.save_config(automation_settings)
        flash("自动化设置已保存。请重启应用以使新计划生效。", "success")
        return redirect(url_for('automation_page'))
    return render_template('dashboard.html', page_title="自动化设置", settings=config_manager.config)
    
@app.route('/email_template', methods=['GET', 'POST'])
def email_template():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        if form_type == 'bulk':
            bulk_data = {'panel_name': request.form.get('panel_name'), 'subject': request.form.get('subject'), 'body': request.form.get('body')}
            save_email_template(bulk_data); flash("批量邮件模板已保存。", "success")
        elif form_type == 'reminder':
            reminder_data = {'subject': request.form.get('subject'), 'body': request.form.get('body')}
            save_reminder_template(reminder_data); flash("到期提醒模板已保存。", "success")
        elif form_type == 'create_user':
            create_user_data = {'subject': request.form.get('subject'), 'body': request.form.get('body')}
            save_create_user_template(create_user_data); flash("新用户通知模板已保存。", "success")
        return redirect(url_for('email_template'))
    return render_template('dashboard.html', page_title="邮件模板管理", template_data=load_email_template(), reminder_template_data=load_reminder_template(), create_user_template_data=load_create_user_template())

@app.route('/api/nodes/<int:node_id>/allocations')
def api_get_node_allocations(node_id):
    allocs = get_ptero_data(f"nodes/{node_id}/allocations")
    unassigned_allocs = [a['attributes'] for a in allocs if a.get('attributes') and not a['attributes'].get('assigned')] if allocs else []
    return jsonify({"allocations": unassigned_allocs})

@app.route('/api/nests/<int:nest_id>/eggs')
def api_get_nest_eggs(nest_id):
    eggs_data = get_ptero_data(f"nests/{nest_id}/eggs")
    return jsonify({"eggs": [e['attributes'] for e in eggs_data] if eggs_data else []})

@app.route('/api/nests/<int:nest_id>/eggs/<int:egg_id>/variables')
def api_get_nest_egg_variables(nest_id, egg_id):
    egg_data_list = get_ptero_data(f"nests/{nest_id}/eggs/{egg_id}?include=variables")
    if not egg_data_list: return jsonify({"error": "Egg not found"}), 404
    variables = egg_data_list[0].get('attributes', {}).get('relationships', {}).get('variables', {}).get('data', [])
    return jsonify({"variables": [v['attributes'] for v in variables]})

def automated_suspend_task():
    with app.app_context():
        try:
            yesterday = get_today() - timedelta(days=1)
            servers_to_suspend = Server.query.filter(Server.expiration_date == yesterday, or_(Server.status == None, Server.status != '已冻结')).all()
            if not servers_to_suspend: return
            headers = get_api_headers(); panel_url = config_manager.get('PTERO_PANEL_URL').rstrip('/')
            for server in servers_to_suspend:
                try:
                    res = requests.post(f"{panel_url}/api/application/servers/{server.ptero_server_id}/suspend", headers=headers, timeout=20); res.raise_for_status()
                    server.status = '已冻结'; db.session.commit()
                except requests.RequestException: db.session.rollback()
        except Exception as e: app.logger.error(f"[自动化任务] 冻结任务出错: {e}", exc_info=True)

def automated_delete_task():
    with app.app_context():
        try:
            delete_threshold_date = get_today() - timedelta(days=config_manager.get('AUTOMATION_DELETE_DAYS', 14))
            servers_to_delete = Server.query.filter(Server.expiration_date <= delete_threshold_date).all()
            if not servers_to_delete: return
            headers = get_api_headers(); panel_url = config_manager.get('PTERO_PANEL_URL').rstrip('/')
            for server in servers_to_delete:
                try:
                    res = requests.delete(f"{panel_url}/api/application/servers/{server.ptero_server_id}", headers=headers, timeout=20)
                    if res.status_code not in [204, 404]: res.raise_for_status()
                    db.session.delete(server); db.session.commit()
                except requests.RequestException: db.session.rollback()
        except Exception as e: app.logger.error(f"[自动化任务] 删除任务出错: {e}", exc_info=True)

def automated_email_task():
    with app.app_context():
        try:
            tomorrow = get_today() + timedelta(days=1)
            servers_to_notify = Server.query.filter(Server.expiration_date == tomorrow).all()
            if not servers_to_notify: return
            owners_map = {}; [owners_map.setdefault(s.owner_id, []).append(s) for s in servers_to_notify]
            all_users_data = get_ptero_data("users")
            if not all_users_data: return
            users_email_map = {u['attributes']['id']: u['attributes']['email'] for u in all_users_data if u.get('attributes')}
            reminder_template = load_reminder_template()
            panel_url = config_manager.get('PTERO_PANEL_URL')
            
            for owner_id, owner_servers in owners_map.items():
                if not (recipient_email := users_email_map.get(owner_id)): continue
                
                server_list_str = "\n".join([f"- {s.server_name} (ID: {s.ptero_server_id})" for s in owner_servers])
                body_raw = reminder_template.get('body', '')
                context_vars = {
                    '{{username}}': owner_servers[0].owner_username, '{{expiration_date}}': tomorrow.strftime('%Y-%m-%d'),
                    '{{server_count}}': str(len(owner_servers)), '{{server_list}}': server_list_str,
                    '{{panel_name}}': load_email_template().get('panel_name', 'Pterodactyl')
                }
                for key, value in context_vars.items(): body_raw = body_raw.replace(key, str(value))
                
                send_email(
                    recipient_email=recipient_email,
                    subject=reminder_template.get('subject'),
                    main_content_raw=body_raw,
                    greeting=f"您好, {owner_servers[0].owner_username}!",
                    action_text="登录面板处理",
                    action_url=panel_url
                )
                time.sleep(config_manager.get('EMAIL_SEND_DELAY', 2))
        except Exception as e: app.logger.error(f"[自动化任务] 邮件提醒任务出错: {e}", exc_info=True)

def initialize_scheduler(app_instance):
    with app_instance.app_context():
        db.create_all()
        scheduler.init_app(app_instance)
        cfg = config_manager.config
        if cfg.get('AUTOMATION_SUSPEND_ENABLED'):
            scheduler.add_job(id='auto_suspend_task', func=automated_suspend_task, trigger='cron', hour=cfg['AUTOMATION_RUN_HOUR'], minute=cfg['AUTOMATION_RUN_MINUTE'], replace_existing=True)
        if cfg.get('AUTOMATION_DELETE_ENABLED'):
            scheduler.add_job(id='auto_delete_task', func=automated_delete_task, trigger='cron', hour=cfg['AUTOMATION_RUN_HOUR'], minute=cfg['AUTOMATION_RUN_MINUTE'], replace_existing=True)
        if cfg.get('AUTOMATION_EMAIL_ENABLED'):
            scheduler.add_job(id='auto_email_task', func=automated_email_task, trigger='cron', hour=cfg['AUTOMATION_EMAIL_RUN_HOUR'], minute=cfg['AUTOMATION_EMAIL_RUN_MINUTE'], replace_existing=True)
        if scheduler.get_jobs() and not scheduler.running:
            scheduler.start()

initialize_scheduler(app)

# --- Gunicorn 日志集成 ---
# 如果在 gunicorn 环境下运行, 则使用 gunicorn 的 logger
if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    app.logger.info('Gunicorn logger integration successful.')

if __name__ == '__main__':
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance'), exist_ok=True)
    app.run(host='0.0.0.0', port=5000)