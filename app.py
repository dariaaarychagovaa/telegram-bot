import requests
import threading
import time
import random
import os
import json
import csv
import smtplib
from email.message import EmailMessage
from flask import Flask, jsonify, request
from telegram import Update, Bot, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ------------------- КОНФИГУРАЦИЯ -------------------
TOKEN = "8991597660:AAEFaAbWY-w8vHLl9UDvL_0vNT7c7MMrFQo"
CHAT_ID = "8991597660"
EMAIL_USER = "diplom.diplom.rch@gmail.com"
EMAIL_PASSWORD = "marysia2020"
EMAIL_TO = "diplom.diplom.rch@gmail.com"

# ------------------- РАССЫЛКА -------------------
def send_email(subject, message):
    try:
        msg = EmailMessage()
        msg.set_content(message)
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_TO
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Email отправлен")
    except Exception as e:
        print(f"Ошибка email: {e}")

def broadcast(message, subject="Уведомление от бота"):
    try:
        Bot(token=TOKEN).send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print(f"Ошибка Telegram: {e}")
    send_email(subject, message)

# ------------------- ДАННЫЕ И РОЛИ -------------------
DATA_FILE = "data.json"
ROLES_FILE = "user_roles.json"

def load_roles():
    if os.path.exists(ROLES_FILE):
        with open(ROLES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_roles(roles):
    with open(ROLES_FILE, "w") as f:
        json.dump(roles, f)

user_roles = load_roles()
def get_role(user_id):
    return user_roles.get(str(user_id), "designer")
def set_role(user_id, role):
    user_roles[str(user_id)] = role
    save_roles(user_roles)

def load_data():
    global projects, tasks, comments, issues, bim_collisions, contracts, schedule, workflow_rules
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            projects = data.get("projects", {})
            tasks = data.get("tasks", {})
            comments = data.get("comments", {})
            issues = data.get("issues", {})
            bim_collisions = data.get("bim_collisions", {})
            contracts = data.get("contracts", {})
            schedule = data.get("schedule", {})
            workflow_rules = data.get("workflow_rules", {})
    else:
        projects = {
            1: {"id": 1, "name": "Жилой комплекс 'Солнечный'", "status": "active", "deadline": "2026-09-01"},
            2: {"id": 2, "name": "Торговый центр 'Премьер'", "status": "review", "deadline": "2026-07-15"},
            3: {"id": 3, "name": "Офисное здание 'Интеграция'", "status": "planning", "deadline": "2026-12-01"}
        }
        tasks = {
            1: [
                {"id": 101, "title": "Разработка проекта организации строительства", "status": "done", "project_id": 1},
                {"id": 102, "title": "Устройство свайного поля", "status": "in_progress", "project_id": 1}
            ],
            2: [
                {"id": 201, "title": "Согласование фасадных решений", "status": "pending", "project_id": 2}
            ],
            3: [
                {"id": 301, "title": "Проверка BIM-модели на коллизии", "status": "pending", "project_id": 3}
            ]
        }
        comments = {}
        issues = {}
        bim_collisions = {
            1: [
                {"id": 401, "title": "Пересечение вентканалов", "location": "Секция 1, этаж 3", "status": "open"},
                {"id": 402, "title": "Несоответствие уровня пола", "location": "X=12.3 Y=45.6 Z=0.0", "status": "resolved"}
            ]
        }
        contracts = {
            1: {"project_id": 1, "contract_sum": 150_000_000, "paid": 45_000_000, "status": "active"},
            2: {"project_id": 2, "contract_sum": 80_000_000, "paid": 10_000_000, "status": "active"},
            3: {"project_id": 3, "contract_sum": 95_000_000, "paid": 0, "status": "draft"}
        }
        schedule = {
            1: {"milestones": ["Начало строительства", "Завершение монолита", "Сдача объекта"], "planned_dates": ["2026-03-01", "2026-06-15", "2026-09-01"]},
            2: {"milestones": ["Разработка КД", "Получение разрешения", "Открытие ТЦ"], "planned_dates": ["2026-01-10", "2026-04-20", "2026-07-15"]}
        }
        workflow_rules = {"default": ["pending", "in_progress", "review", "done"]}
    # Преобразование типов
    for pid in tasks:
        for t in tasks[pid]:
            t['id'] = int(t['id'])

def save_data():
    data = {
        "projects": projects, "tasks": tasks, "comments": comments, "issues": issues,
        "bim_collisions": bim_collisions, "contracts": contracts, "schedule": schedule,
        "workflow_rules": workflow_rules
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

load_data()
save_data()

def add_issue(project_id, title, description, location="", assigned_to=None):
    all_ids = []
    for pid, iss_list in issues.items():
        for iss in iss_list:
            all_ids.append(iss['id'])
    next_id = max(all_ids) + 1 if all_ids else 401
    new_issue = {"id": next_id, "title": title, "description": description, "location": location,
                 "status": "open", "project_id": project_id, "assigned_to": assigned_to}
    issues.setdefault(project_id, []).append(new_issue)
    save_data()
    broadcast(f"🏗️ Новое замечание по BIM-модели на объекте {project_id}: {title}\nЛокация: {location}", "Новое замечание (BIM)")
    return new_issue

def create_issues_from_csv(file_path, project_id, assigned_to=None):
    created = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get('title', 'Без названия')
            desc = row.get('description', '')
            loc = row.get('location', '')
            issue = add_issue(project_id, title, desc, loc, assigned_to)
            created.append(issue['id'])
    return created

def get_bim_report(project_id):
    collisions = bim_collisions.get(project_id, [])
    if not collisions:
        return "🏗️ Коллизий в BIM-модели не обнаружено."
    report = "📐 *Отчёт по коллизиям BIM:*\n"
    for c in collisions:
        report += f"• {c['title']} – {c['location']} (статус: {c['status']})\n"
    return report

def get_erp_summary(project_id):
    contract = contracts.get(project_id)
    if not contract:
        return "Договорная информация отсутствует."
    return (f"💰 *Данные договора строительного подряда (1С) по объекту {project_id}*\n"
            f"Сумма: {contract['contract_sum']} руб.\nОплачено: {contract['paid']} руб.\n"
            f"Статус: {contract['status']}\nОстаток: {contract['contract_sum'] - contract['paid']} руб.")

def get_schedule(project_id):
    sched = schedule.get(project_id)
    if not sched:
        return "График производства работ не загружен."
    milestones = sched.get("milestones", [])
    dates = sched.get("planned_dates", [])
    report = "📅 *График производства работ (MS Project):*\n"
    for i, (m, d) in enumerate(zip(milestones, dates), 1):
        report += f"{i}. {m} – {d}\n"
    return report

def get_dashboard(project_id):
    proj = projects.get(project_id, {})
    proj_tasks = tasks.get(project_id, [])
    total = len(proj_tasks)
    done = sum(1 for t in proj_tasks if t['status'] == 'done')
    in_progress = sum(1 for t in proj_tasks if t['status'] == 'in_progress')
    pending = total - done - in_progress
    issues_count = len(issues.get(project_id, []))
    return (f"📊 *Дашборд объекта {project_id}: {proj.get('name','')}*\n"
            f"📌 Рабочих заданий: всего {total}, выполнено {done}, в работе {in_progress}, ожидают {pending}\n"
            f"⚠️ Замечаний BIM: {issues_count}\n📅 Плановая дата сдачи: {proj.get('deadline', 'не указана')}")

# ------------------- FLASK ЭМУЛЯТОР -------------------
app_flask = Flask(__name__)
@app_flask.route('/projects', methods=['GET'])
def get_projects():
    return jsonify(list(projects.values()))
@app_flask.route('/projects/<int:pid>/tasks', methods=['GET'])
def get_tasks(pid):
    return jsonify(tasks.get(pid, []))
@app_flask.route('/tasks/<int:tid>', methods=['GET'])
def get_task(tid):
    for pid, tlist in tasks.items():
        for t in tlist:
            if t['id'] == tid:
                return jsonify(t)
    return jsonify({}), 404
@app_flask.route('/tasks/<int:tid>/comments', methods=['POST'])
def post_comment(tid):
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify({"error": "no text"}), 400
    comments.setdefault(tid, []).append({"id": len(comments.get(tid, []))+1, "text": text})
    save_data()
    broadcast(f"💬 Новый комментарий к заданию {tid}: {text}", f"Комментарий #{tid}")
    return jsonify({"status": "ok"})
@app_flask.route('/tasks/<int:tid>/status', methods=['PUT'])
def put_task_status(tid):
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['pending', 'in_progress', 'review', 'done']:
        return jsonify({"error": "invalid"}), 400
    for pid, tlist in tasks.items():
        for t in tlist:
            if t['id'] == tid:
                old = t['status']
                t['status'] = new_status
                save_data()
                broadcast(f"🔄 Статус задания {tid} изменён с '{old}' на '{new_status}'", f"Статус #{tid}")
                return jsonify({"status": "ok"})
    return jsonify({"error": "not found"}), 404
@app_flask.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "no file"}), 400
    file = request.files['file']
    filename = file.filename
    os.makedirs('uploads', exist_ok=True)
    file.save(os.path.join('uploads', filename))
    broadcast(f"📎 Загружен файл: {filename}", "Файл")
    return jsonify({"status": "ok", "filename": filename})
@app_flask.route('/webhook', methods=['POST'])
def webhook_handler():
    data = request.get_json()
    event_type = data.get('event', 'unknown')
    message = data.get('message', '')
    broadcast(f"🔔 Внешнее событие (webhook): {event_type}\n{message}", "Webhook")
    return jsonify({"status": "received"})

def run_flask():
    app_flask.run(host='0.0.0.0', port=5000)

# Фоновые события
def generate_event():
    event_types = ["status_change", "deadline_soon", "new_task", "bim_collision", "contract_update"]
    event = random.choice(event_types)
    pid = random.choice(list(projects.keys()))
    if event == "status_change":
        new_status = random.choice(["active", "review", "closed"])
        msg = f"🔔 Объект строительства '{projects[pid]['name']}' изменил статус на '{new_status}'."
    elif event == "deadline_soon":
        msg = f"⚠️ Плановая дата сдачи объекта '{projects[pid]['name']}' наступает {projects[pid]['deadline']}!"
    elif event == "new_task":
        new_id = max([t['id'] for tlist in tasks.values() for t in tlist], default=1000)+1
        new_task = {"id": new_id, "title": "Случайное задание", "status": "pending", "project_id": pid}
        tasks.setdefault(pid, []).append(new_task)
        save_data()
        msg = f"📌 Новое рабочее задание на объекте '{projects[pid]['name']}': {new_task['title']}"
    elif event == "bim_collision":
        msg = f"🏗️ BIM-коллизия в проекте '{projects[pid]['name']}': пересечение трубопроводов на отм. +3.45"
    else:
        msg = f"📄 Обновление договора по объекту '{projects[pid]['name']}': поступил акт КС-2"
    broadcast(msg, "Событие")

def notification_worker():
    while True:
        time.sleep(60)
        generate_event()

# ------------------- ТЕЛЕГРАМ БОТ -------------------
TITLE, DESCRIPTION, SELECT_PROJECT, ISSUE_LOCATION = range(4)

def get_keyboard(role):
    if role == "designer":
        return ReplyKeyboardMarkup([
            ["📁 Объекты", "📋 Задания"],
            ["🏗️ BIM-отчёт", "💰 Договор (1С)"],
            ["📅 График ППР", "📊 Дашборд"],
            ["⚠️ Создать замечание", "📂 Загрузить CSV"],
            ["🌐 Webhook тест", "❓ Помощь"]
        ], resize_keyboard=True)
    elif role == "engineer":
        return ReplyKeyboardMarkup([
            ["📁 Объекты", "📋 Задания"],
            ["⚠️ Все замечания", "📋 Мои замечания"],
            ["🏗️ BIM-отчёт", "💰 Договор (1С)"],
            ["📅 График ППР", "📊 Дашборд"],
            ["🌐 Webhook тест", "❓ Помощь"]
        ], resize_keyboard=True)
    elif role == "builder":
        return ReplyKeyboardMarkup([
            ["📁 Объекты", "📋 Задания"],
            ["📋 Мои замечания", "🏗️ BIM-отчёт"],
            ["💰 Договор (1С)", "📅 График ППР"],
            ["📊 Дашборд", "🌐 Webhook тест"],
            ["❓ Помощь"]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([["❓ Помощь"]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_role(user_id)
    await update.message.reply_text(
        f"🏗️ *Строительный помощник (интеграция SIGNAL DOCS)*\n\n"
        f"Ваша роль: {role}\n"
        f"Сменить роль: /role designer | engineer | builder\n\n"
        f"*Сценарий работы с замечаниями:*\n"
        f"1. Проектировщик загружает CSV с коллизиями BIM\n"
        f"2. ГИП (engineer) назначает ответственного\n"
        f"3. Строитель (builder) выполняет и меняет статус\n"
        f"4. ГИП проверяет и закрывает\n\n"
        f"Команда /issue <ID> – работа с замечанием по ID\n"
        f"Кнопка '🌐 Webhook тест' – имитация внешнего события",
        parse_mode="Markdown", reply_markup=get_keyboard(role)
    )

async def role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Укажите роль: /role designer, /role engineer, /role builder")
        return
    role = args[0].lower()
    if role not in ["designer", "engineer", "builder"]:
        await update.message.reply_text("Допустимые роли: designer, engineer, builder")
        return
    user_id = update.effective_user.id
    set_role(user_id, role)
    # Отправляем новое меню
    await update.message.reply_text(f"Роль изменена на {role}. Обновите меню командой /start", reply_markup=get_keyboard(role))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏗️ *Команды*\n"
        "/start – главное меню\n"
        "/role <роль> – смена роли\n"
        "/projects – объекты строительства\n"
        "/tasks – задания по объекту\n"
        "/new_issue – создать замечание вручную\n"
        "/upload_issues – загрузить CSV с коллизиями\n"
        "/my_issues – мои замечания\n"
        "/issue <id> – детали замечания и смена статуса\n"
        "/bim – отчёт по коллизиям BIM\n"
        "/erp – данные договора (1С)\n"
        "/schedule – график ППР\n"
        "/dashboard – дашборд объекта\n"
        "/webhook_test – отправить тестовое внешнее событие\n"
        "/workflow – статусная модель",
        parse_mode="Markdown"
    )

async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.get("http://localhost:5000/projects")
    if resp.status_code == 200:
        projs = resp.json()
        if projs:
            msg = "🏗️ *Объекты строительства:*\n\n"
            for p in projs:
                msg += f"• *{p['name']}* (ID: {p['id']})\n  Статус: {p['status']}\n  Плановая дата сдачи: {p['deadline']}\n\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("Нет объектов.")
    else:
        await update.message.reply_text("Ошибка получения данных.")

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.get("http://localhost:5000/projects")
    if resp.status_code != 200:
        await update.message.reply_text("Ошибка получения объектов.")
        return
    projs = resp.json()
    if not projs:
        await update.message.reply_text("Нет объектов.")
        return
    keyboard = [[InlineKeyboardButton(p['name'], callback_data=f"tasks_{p['id']}")] for p in projs]
    await update.message.reply_text("Выберите объект:", reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("tasks_"):
        pid = int(data.split('_')[1])
        resp = requests.get(f"http://localhost:5000/projects/{pid}/tasks")
        if resp.status_code == 200:
            task_list = resp.json()
            if task_list:
                msg = f"📋 *Рабочие задания на объекте {pid}:*\n\n"
                keyboard = []
                for t in task_list:
                    msg += f"• Задание {t['id']}: {t['title']} (статус: {t['status']})\n"
                    keyboard.append([InlineKeyboardButton(f"🔍 Задание {t['id']}", callback_data=f"task_{t['id']}")])
                await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.edit_message_text("Нет заданий.")
        else:
            await query.edit_message_text("Ошибка загрузки.")
    elif data.startswith("task_"):
        tid = int(data.split('_')[1])
        resp = requests.get(f"http://localhost:5000/tasks/{tid}")
        if resp.status_code != 200:
            await query.edit_message_text("Задание не найдено.")
            return
        task = resp.json()
        msg = f"📌 *Задание {task['id']}: {task['title']}*\nСтатус: {task['status']}"
        if task.get('description'):
            msg += f"\nОписание: {task['description']}"
        comms = comments.get(tid, [])
        if comms:
            msg += "\n\n💬 *Комментарии:*\n" + "\n".join([f"  - {c['text']}" for c in comms])
        else:
            msg += "\n\nНет комментариев."
        keyboard = [
            [InlineKeyboardButton("✏️ Добавить комментарий", callback_data=f"addcom_{tid}")],
            [InlineKeyboardButton("🔄 Изменить статус", callback_data=f"status_{tid}")]
        ]
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ----- Замечания (issue) -----
async def my_issues_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_role(user_id)
    my_list = []
    for pid, iss_list in issues.items():
        for iss in iss_list:
            if iss.get('assigned_to') == role:
                my_list.append(iss)
    if not my_list:
        await update.message.reply_text("У вас нет назначенных замечаний.")
        return
    msg = "📋 *Ваши замечания:*\n"
    for iss in my_list:
        msg += f"ID {iss['id']}: {iss['title']} – {iss['location']} (статус: {iss['status']})\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def issue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Укажите ID замечания: /issue <ID>")
        return
    try:
        issue_id = int(args[0])
    except ValueError:
        await update.message.reply_text("ID должно быть числом.")
        return
    found = None
    for pid, iss_list in issues.items():
        for iss in iss_list:
            if iss['id'] == issue_id:
                found = iss
                break
        if found:
            break
    if not found:
        await update.message.reply_text(f"Замечание с ID {issue_id} не найдено.")
        return
    msg = (f"🏗️ *Замечание BIM #{found['id']}*\n"
           f"Название: {found['title']}\n"
           f"Описание: {found['description']}\n"
           f"Локация: {found['location']}\n"
           f"Статус: {found['status']}\n"
           f"Назначено: {found.get('assigned_to', 'не назначено')}")
    keyboard = [[InlineKeyboardButton("🔄 Изменить статус", callback_data=f"issue_status_{found['id']}")]]
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def issue_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    issue_id = int(query.data.split('_')[2])
    keyboard = [
        [InlineKeyboardButton("⏳ Открыто", callback_data=f"issue_set_{issue_id}_open")],
        [InlineKeyboardButton("🔄 В работе", callback_data=f"issue_set_{issue_id}_in_progress")],
        [InlineKeyboardButton("✅ Исправлено", callback_data=f"issue_set_{issue_id}_done")],
        [InlineKeyboardButton("🔁 На проверке", callback_data=f"issue_set_{issue_id}_review")],
        [InlineKeyboardButton("❌ Закрыто", callback_data=f"issue_set_{issue_id}_closed")]
    ]
    await query.edit_message_text("Выберите новый статус замечания:", reply_markup=InlineKeyboardMarkup(keyboard))

async def issue_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, issue_id, status = query.data.split('_')
    issue_id = int(issue_id)
    for pid, iss_list in issues.items():
        for iss in iss_list:
            if iss['id'] == issue_id:
                old = iss['status']
                iss['status'] = status
                save_data()
                broadcast(f"🔄 Статус замечания #{issue_id} изменён с '{old}' на '{status}'", f"Замечание #{issue_id}")
                await query.edit_message_text(f"Статус замечания #{issue_id} изменён на '{status}'.")
                return
    await query.edit_message_text("Ошибка: замечание не найдено.")

# ----- Загрузка CSV -----
async def upload_issues_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправьте CSV-файл с колонками: title, description, location")
async def handle_issues_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith('.csv'):
        await update.message.reply_text("Отправьте CSV-файл.")
        return
    file = await doc.get_file()
    file_path = f"downloads/{doc.file_name}"
    os.makedirs('downloads', exist_ok=True)
    await file.download_to_drive(file_path)
    # Для простоты используем проект с ID=1
    pid = 1
    try:
        created = create_issues_from_csv(file_path, pid, assigned_to="builder")
        await update.message.reply_text(f"Создано замечаний: {len(created)}. ID: {', '.join(map(str, created))}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# ----- Вручную создать замечание -----
async def new_issue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название замечания:")
    return 1
async def issue_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['issue_title'] = update.message.text
    await update.message.reply_text("Введите описание:")
    return 2
async def issue_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['issue_desc'] = update.message.text
    await update.message.reply_text("Укажите локацию (X,Y,Z или чертёж):")
    return ISSUE_LOCATION
async def issue_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.text
    title = context.user_data.get('issue_title')
    desc = context.user_data.get('issue_desc')
    pid = 1
    add_issue(pid, title, desc, loc, assigned_to=None)
    await update.message.reply_text(f"⚠️ Замечание '{title}' зарегистрировано с локацией: {loc}")
    return ConversationHandler.END

# ----- Отчёты (BIM, ERP, Schedule, Dashboard) -----
async def bim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.get("http://localhost:5000/projects")
    if resp.status_code == 200:
        projs = resp.json()
        if projs:
            keyboard = [[InlineKeyboardButton(p['name'], callback_data=f"bim_{p['id']}")] for p in projs]
            await update.message.reply_text("Выберите объект:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("Нет объектов.")
    else:
        await update.message.reply_text("Ошибка API.")
async def bim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split('_')[1])
    report = get_bim_report(pid)
    await query.edit_message_text(report, parse_mode="Markdown")

async def erp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.get("http://localhost:5000/projects")
    if resp.status_code == 200:
        projs = resp.json()
        if projs:
            keyboard = [[InlineKeyboardButton(p['name'], callback_data=f"erp_{p['id']}")] for p in projs]
            await update.message.reply_text("Выберите объект:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("Нет объектов.")
    else:
        await update.message.reply_text("Ошибка API.")
async def erp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split('_')[1])
    data = get_erp_summary(pid)
    await query.edit_message_text(data, parse_mode="Markdown")

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.get("http://localhost:5000/projects")
    if resp.status_code == 200:
        projs = resp.json()
        if projs:
            keyboard = [[InlineKeyboardButton(p['name'], callback_data=f"sched_{p['id']}")] for p in projs]
            await update.message.reply_text("Выберите объект:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("Нет объектов.")
    else:
        await update.message.reply_text("Ошибка API.")
async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split('_')[1])
    data = get_schedule(pid)
    await query.edit_message_text(data, parse_mode="Markdown")

async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resp = requests.get("http://localhost:5000/projects")
    if resp.status_code == 200:
        projs = resp.json()
        if projs:
            keyboard = [[InlineKeyboardButton(p['name'], callback_data=f"dash_{p['id']}")] for p in projs]
            await update.message.reply_text("Выберите объект:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("Нет объектов.")
    else:
        await update.message.reply_text("Ошибка API.")
async def dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split('_')[1])
    data = get_dashboard(pid)
    await query.edit_message_text(data, parse_mode="Markdown")

async def workflow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wf = workflow_rules.get("default", ["pending","in_progress","review","done"])
    msg = "🔁 *Маршрут согласования:*\n" + " → ".join(wf)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def webhook_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Отправляем POST-запрос на эндпоинт /webhook эмулятора
    test_data = {"event": "external_update", "message": "Поступили новые данные от подрядчика (акт КС-2)"}
    try:
        resp = requests.post("http://localhost:5000/webhook", json=test_data, timeout=5)
        if resp.status_code == 200:
            await update.message.reply_text("✅ Внешнее событие отправлено. Уведомление будет доставлено в Telegram и на почту.")
        else:
            await update.message.reply_text("❌ Ошибка отправки события.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ----- Комментарии и статусы для заданий -----
async def add_comment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split('_')[1])
    context.user_data['comment_task_id'] = tid
    await query.edit_message_text(f"Введите текст комментария для задания {tid}:")
    context.user_data['awaiting_comment'] = True
async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_comment'):
        tid = context.user_data.get('comment_task_id')
        text = update.message.text
        if text:
            requests.post(f"http://localhost:5000/tasks/{tid}/comments", json={"text": text})
            await update.message.reply_text(f"Комментарий добавлен к заданию {tid}.")
        else:
            await update.message.reply_text("Текст не может быть пустым.")
        context.user_data.pop('awaiting_comment')
        context.user_data.pop('comment_task_id', None)
async def change_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = int(query.data.split('_')[1])
    keyboard = [
        [InlineKeyboardButton("⏳ В ожидании", callback_data=f"setstat_{tid}_pending")],
        [InlineKeyboardButton("🔄 В работе", callback_data=f"setstat_{tid}_in_progress")],
        [InlineKeyboardButton("🔁 На проверке", callback_data=f"setstat_{tid}_review")],
        [InlineKeyboardButton("✅ Выполнено", callback_data=f"setstat_{tid}_done")]
    ]
    await query.edit_message_text("Выберите статус задания:", reply_markup=InlineKeyboardMarkup(keyboard))
async def set_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, tid, status = query.data.split('_')
    tid = int(tid)
    resp = requests.put(f"http://localhost:5000/tasks/{tid}/status", json={"status": status})
    if resp.status_code == 200:
        await query.edit_message_text(f"Статус задания {tid} изменён на '{status}'.")
    else:
        await query.edit_message_text("Ошибка изменения статуса.")

# ----- Загрузка обычных файлов (не CSV) -----
async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправьте файл (документ или фото).")
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or (update.message.photo[-1] if update.message.photo else None)
    if not file:
        await update.message.reply_text("Отправьте файл.")
        return
    new_file = await file.get_file()
    os.makedirs('downloads', exist_ok=True)
    fname = file.file_name if hasattr(file, 'file_name') else f"photo_{file.file_id}.jpg"
    path = f"downloads/{file.file_id}_{fname}"
    await new_file.download_to_drive(path)
    with open(path, 'rb') as f:
        r = requests.post("http://localhost:5000/upload", files={'file': f})
        if r.status_code == 200:
            await update.message.reply_text(f"Файл {fname} загружен.")
        else:
            await update.message.reply_text("Ошибка загрузки.")

# ----- Текстовый обработчик (кнопки) -----
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_comment'):
        await receive_comment(update, context)
        return
    text = update.message.text
    if text == "📁 Объекты":
        await projects_command(update, context)
    elif text == "📋 Задания":
        await tasks_command(update, context)
    elif text == "⚠️ Создать замечание":
        await new_issue_command(update, context)
    elif text == "📂 Загрузить CSV":
        await upload_issues_command(update, context)
    elif text == "⚠️ Все замечания":
        await my_issues_command(update, context)
    elif text == "📋 Мои замечания":
        await my_issues_command(update, context)
    elif text == "🏗️ BIM-отчёт":
        await bim_command(update, context)
    elif text == "💰 Договор (1С)":
        await erp_command(update, context)
    elif text == "📅 График ППР":
        await schedule_command(update, context)
    elif text == "📊 Дашборд":
        await dashboard_command(update, context)
    elif text == "🌐 Webhook тест":
        await webhook_test(update, context)
    elif text == "🔁 Workflow":
        await workflow_command(update, context)
    elif text == "❓ Помощь":
        await help_command(update, context)
    else:
        await update.message.reply_text("Используйте кнопки или /help", reply_markup=get_keyboard(get_role(update.effective_user.id)))

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=notification_worker, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("role", role_command))
    app.add_handler(CommandHandler("projects", projects_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("my_issues", my_issues_command))
    app.add_handler(CommandHandler("issue", issue_command))
    app.add_handler(CommandHandler("bim", bim_command))
    app.add_handler(CommandHandler("erp", erp_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("dashboard", dashboard_command))
    app.add_handler(CommandHandler("workflow", workflow_command))
    app.add_handler(CommandHandler("webhook_test", webhook_test))
    app.add_handler(CommandHandler("upload", upload_cmd))
    app.add_handler(CommandHandler("upload_issues", upload_issues_command))
    app.add_handler(CommandHandler("new_issue", new_issue_command))
    # Conversation для ручного создания замечания
    conv_issue = ConversationHandler(
        entry_points=[CommandHandler("new_issue", new_issue_command)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, issue_title)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, issue_desc)],
            ISSUE_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, issue_location)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: u.message.reply_text("Отмена"))],
    )
    app.add_handler(conv_issue)
    # Callback handlers
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^(tasks_|task_)"))
    app.add_handler(CallbackQueryHandler(bim_callback, pattern="^bim_"))
    app.add_handler(CallbackQueryHandler(erp_callback, pattern="^erp_"))
    app.add_handler(CallbackQueryHandler(schedule_callback, pattern="^sched_"))
    app.add_handler(CallbackQueryHandler(dashboard_callback, pattern="^dash_"))
    app.add_handler(CallbackQueryHandler(issue_status_callback, pattern="^issue_status_"))
    app.add_handler(CallbackQueryHandler(issue_set_callback, pattern="^issue_set_"))
    app.add_handler(CallbackQueryHandler(add_comment_callback, pattern="^addcom_"))
    app.add_handler(CallbackQueryHandler(change_status_callback, pattern="^status_"))
    app.add_handler(CallbackQueryHandler(set_status_callback, pattern="^setstat_"))
    # Файлы
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.PHOTO, handle_issues_file))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("Бот успешно запущен. Строительная тематика, роли, команда /issue, webhook тест.")
    app.run_polling()

if __name__ == "__main__":
    main()