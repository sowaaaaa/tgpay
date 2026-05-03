import sqlite3
import threading
import time
from datetime import datetime, timedelta
import pytz

MSK = pytz.timezone('Europe/Moscow')
PENALTIES_DB = 'files/penalties.db'
MODERATOR_ID = 1739548566
PENALTY_AMOUNT = 500  # рублей

def init_penalties_db():
    """Создать таблицы для штрафов"""
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    # Открытые заявки на контроле
    cursor.execute('''CREATE TABLE IF NOT EXISTS pending_requests (
        request_number INTEGER PRIMARY KEY,
        message_id INTEGER,
        chat_id INTEGER,
        created_at TEXT,
        deadline TEXT,
        reminded INTEGER DEFAULT 0
    )''')
    # Аналитика штрафов
    cursor.execute('''CREATE TABLE IF NOT EXISTS penalties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_number INTEGER,
        moderator_id INTEGER,
        penalty_amount REAL,
        created_at TEXT,
        request_created_at TEXT,
        deadline TEXT
    )''')
    db.commit()
    db.close()


def calculate_deadline(created_at_msk):
    """
    Рассчитать дедлайн:
    - Если заявка создана с 23:00 до 02:00 МСК → дедлайн 14:00 МСК того же дня (или следующего)
    - Иначе → +12 часов от создания
    """
    hour = created_at_msk.hour
    if hour >= 23 or hour < 2:
        # Определяем дату дедлайна
        if hour >= 23:
            # Создана после 23:00 → дедлайн 14:00 следующего дня
            deadline_date = created_at_msk.date() + timedelta(days=1)
        else:
            # Создана до 02:00 → дедлайн 14:00 этого же дня
            deadline_date = created_at_msk.date()
        deadline = MSK.localize(datetime.combine(deadline_date, datetime.strptime('14:00', '%H:%M').time()))
    else:
        deadline = created_at_msk + timedelta(hours=12)
    return deadline


def register_request(request_number, message_id, chat_id):
    """Зарегистрировать заявку Мобильный Украина для отслеживания"""
    now_msk = datetime.now(MSK)
    deadline = calculate_deadline(now_msk)
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO pending_requests (request_number, message_id, chat_id, created_at, deadline) VALUES (?, ?, ?, ?, ?)',
        (request_number, message_id, chat_id, now_msk.isoformat(), deadline.isoformat())
    )
    db.commit()
    db.close()
    print(f'[ШТРАФЫ] Заявка №{request_number} зарегистрирована, дедлайн: {deadline.strftime("%d.%m.%Y %H:%M")} МСК')


def close_request(request_number):
    """Снять заявку с контроля (закрыта вовремя)"""
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute('DELETE FROM pending_requests WHERE request_number = ?', (request_number,))
    db.commit()
    db.close()
    print(f'[ШТРАФЫ] Заявка №{request_number} закрыта, штраф не начислен')


def get_overdue_requests():
    """Получить просроченные заявки"""
    now_msk = datetime.now(MSK)
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute('SELECT request_number, message_id, chat_id, created_at, deadline FROM pending_requests')
    rows = cursor.fetchall()
    db.close()

    overdue = []
    for row in rows:
        deadline = datetime.fromisoformat(row[4])
        if now_msk >= deadline:
            overdue.append({
                'request_number': row[0],
                'message_id': row[1],
                'chat_id': row[2],
                'created_at': row[3],
                'deadline': row[4]
            })
    return overdue



def issue_penalty(request_number, created_at, deadline):
    """Записать штраф в аналитику"""
    now_msk = datetime.now(MSK)
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO penalties (request_number, moderator_id, penalty_amount, created_at, request_created_at, deadline) VALUES (?, ?, ?, ?, ?, ?)',
        (request_number, MODERATOR_ID, PENALTY_AMOUNT, now_msk.isoformat(), created_at, deadline)
    )
    # Удаляем из pending
    cursor.execute('DELETE FROM pending_requests WHERE request_number = ?', (request_number,))
    db.commit()
    db.close()
    print(f'[ШТРАФЫ] Штраф {PENALTY_AMOUNT}₽ начислен за заявку №{request_number}')


def get_penalties_stats(moderator_id):
    """Аналитика штрафов"""
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()

    # Кол-во штрафов
    cursor.execute('SELECT COUNT(*) FROM penalties WHERE moderator_id = ?', (moderator_id,))
    count = cursor.fetchone()[0]

    # Общая сумма штрафов (1 штраф = PENALTY_AMOUNT)
    total = count * PENALTY_AMOUNT

    # Штрафы за текущий месяц
    now_msk = datetime.now(MSK)
    month_start = now_msk.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cursor.execute(
        'SELECT COUNT(*) FROM penalties WHERE moderator_id = ? AND created_at >= ?',
        (moderator_id, month_start.isoformat())
    )
    month_count = cursor.fetchone()[0]
    month_total = month_count * PENALTY_AMOUNT

    # Последние 10 штрафов
    cursor.execute(
        'SELECT request_number, penalty_amount, created_at, request_created_at, deadline FROM penalties WHERE moderator_id = ? ORDER BY id DESC LIMIT 10',
        (moderator_id,)
    )
    recent = cursor.fetchall()

    db.close()
    return {
        'total': total,
        'count': count,
        'month_total': month_total,
        'month_count': month_count,
        'recent': recent
    }


def deduct_penalties(moderator_id, amount_to_leave):
    """
    Списать штрафы так, чтобы у модератора осталась нужная сумма.
    amount_to_leave округляется до кратного PENALTY_AMOUNT.
    Возвращает dict: {'deleted': N, 'remaining_count': M, 'remaining_total': X}
    """
    # Округляем до кратного 500
    amount_to_leave = round(amount_to_leave / PENALTY_AMOUNT) * PENALTY_AMOUNT

    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()

    cursor.execute('SELECT COUNT(*) FROM penalties WHERE moderator_id = ?', (moderator_id,))
    current_count = cursor.fetchone()[0]
    current_total = current_count * PENALTY_AMOUNT

    to_delete = max(0, current_total - amount_to_leave)
    deleted_count = 0

    if to_delete > 0:
        # Удаляем самые старые штрафы
        penalties_to_remove = int(to_delete / PENALTY_AMOUNT)
        cursor.execute(
            'SELECT id FROM penalties WHERE moderator_id = ? ORDER BY id ASC LIMIT ?',
            (moderator_id, penalties_to_remove)
        )
        ids = [row[0] for row in cursor.fetchall()]
        if ids:
            cursor.execute(f'DELETE FROM penalties WHERE id IN ({",".join("?" * len(ids))})', ids)
            deleted_count = len(ids)

    db.commit()

    cursor.execute('SELECT COUNT(*) FROM penalties WHERE moderator_id = ?', (moderator_id,))
    remaining_count = cursor.fetchone()[0]
    db.close()

    return {
        'deleted': deleted_count,
        'remaining_count': remaining_count,
        'remaining_total': remaining_count * PENALTY_AMOUNT
    }


def add_manual_penalty(moderator_id, count):
    """Вручную добавить N штрафов модератору"""
    now_msk = datetime.now(MSK)
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    for _ in range(count):
        cursor.execute(
            'INSERT INTO penalties (request_number, moderator_id, penalty_amount, created_at, request_created_at, deadline) VALUES (?, ?, ?, ?, ?, ?)',
            (None, moderator_id, PENALTY_AMOUNT, now_msk.isoformat(), now_msk.isoformat(), now_msk.isoformat())
        )
    db.commit()
    db.close()
    return count * PENALTY_AMOUNT


def reset_monthly_penalties():
    """Аннулировать все штрафы в начале нового месяца"""
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute('DELETE FROM penalties')
    db.commit()
    db.close()
    print('[ШТРАФЫ] Все штрафы аннулированы (1-е число месяца)')


def start_penalty_checker(bot, admin_group_id):
    """Запустить фоновый поток проверки дедлайнов"""
    init_penalties_db()
    last_monthly_reset = None

    def checker_loop():
        nonlocal last_monthly_reset
        while True:
            try:
                now_msk = datetime.now(MSK)

                # Аннулирование штрафов каждое 1-е число месяца
                month_key = (now_msk.year, now_msk.month)
                if now_msk.day == 1 and last_monthly_reset != month_key:
                    reset_monthly_penalties()
                    last_monthly_reset = month_key
                    try:
                        bot.send_message(
                            admin_group_id,
                            f'🔄 Штрафы аннулированы!\n'
                            f'Начало нового месяца — все штрафы обнулены.'
                        )
                    except Exception:
                        pass

                # Проверка просроченных → штраф
                overdue = get_overdue_requests()
                for req in overdue:
                    issue_penalty(req['request_number'], req['created_at'], req['deadline'])
                    deadline_dt = datetime.fromisoformat(req['deadline'])
                    try:
                        bot.send_message(
                            admin_group_id,
                            f'⚠️ ШТРАФ {PENALTY_AMOUNT}₽\n'
                            f'Заявка №{req["request_number"]} не закрыта вовремя!\n'
                            f'Дедлайн был: {deadline_dt.strftime("%d.%m.%Y %H:%M")} МСК\n'
                            f'Модератор: {MODERATOR_ID}',
                            reply_to_message_id=req['message_id']
                        )
                    except Exception as e:
                        bot.send_message(
                            admin_group_id,
                            f'⚠️ ШТРАФ {PENALTY_AMOUNT}₽\n'
                            f'Заявка №{req["request_number"]} не закрыта вовремя!\n'
                            f'Дедлайн был: {deadline_dt.strftime("%d.%m.%Y %H:%M")} МСК\n'
                            f'Модератор: {MODERATOR_ID}'
                        )
            except Exception as e:
                print(f'[ШТРАФЫ] Ошибка проверки: {e}')
            time.sleep(300)  # Проверяем каждые 5 минут

    thread = threading.Thread(target=checker_loop, daemon=True)
    thread.start()
    print('[ШТРАФЫ] Фоновый поток проверки дедлайнов запущен')