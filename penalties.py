import sqlite3
import threading
import time
from datetime import datetime, timedelta
import pytz

MSK = pytz.timezone('Europe/Moscow')
PENALTIES_DB = 'files/penalties.db'
MODERATOR_ID = 1739548566
PENALTY_AMOUNT = 500  # рублей
PARTNER_ID = 800730615

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
    # Касса модератора
    cursor.execute('''CREATE TABLE IF NOT EXISTS moderator_cash (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        moderator_id INTEGER,
        type TEXT,
        amount REAL,
        comment TEXT,
        created_at TEXT,
        currency TEXT DEFAULT 'RUB'
    )''')
    # Миграция: добавить currency если таблица уже существовала без неё
    try:
        cursor.execute("ALTER TABLE moderator_cash ADD COLUMN currency TEXT DEFAULT 'RUB'")
    except Exception:
        pass
    # Выручка партнёра (5% с чистой прибыли)
    cursor.execute('''CREATE TABLE IF NOT EXISTS partner_earnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT,
        order_price REAL,
        net_profit REAL,
        partner_share REAL,
        service TEXT,
        created_at TEXT
    )''')
    db.commit()
    db.close()


CASH_CURRENCIES = {'RUB': '₽', 'USD': '$', 'UAH': '₴'}


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


def add_cash_transaction(moderator_id, trans_type, amount, comment='', currency='RUB'):
    """Добавить запись в кассу модератора. trans_type: 'income' или 'expense'"""
    now_msk = datetime.now(MSK)
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO moderator_cash (moderator_id, type, amount, comment, created_at, currency) VALUES (?, ?, ?, ?, ?, ?)',
        (moderator_id, trans_type, amount, comment, now_msk.isoformat(), currency)
    )
    db.commit()
    db.close()


def get_cash_stats(moderator_id):
    """Получить сводку по кассе по каждой валюте.
    Возвращает dict: {'RUB': {'total_issued', 'total_spent', 'balance'}, 'USD': ..., 'UAH': ...}
    """
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    result = {}
    for cur in CASH_CURRENCIES:
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM moderator_cash WHERE moderator_id=? AND type='income' AND currency=?",
            (moderator_id, cur)
        )
        issued = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM moderator_cash WHERE moderator_id=? AND type='expense' AND currency=?",
            (moderator_id, cur)
        )
        spent = cursor.fetchone()[0]
        result[cur] = {'total_issued': issued, 'total_spent': spent, 'balance': issued - spent}
    db.close()
    return result


def zero_cash_balance(moderator_id):
    """Списать весь остаток: добавляет расход по каждой валюте равный текущему балансу."""
    stats = get_cash_stats(moderator_id)
    now_msk = datetime.now(MSK)
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    zeroed = {}
    for cur, data in stats.items():
        bal = data['balance']
        if bal > 0:
            cursor.execute(
                'INSERT INTO moderator_cash (moderator_id, type, amount, comment, created_at, currency) VALUES (?, ?, ?, ?, ?, ?)',
                (moderator_id, 'expense', bal, 'Списание остатка', now_msk.isoformat(), cur)
            )
            zeroed[cur] = bal
    db.commit()
    db.close()
    return zeroed


def clear_cash_history(moderator_id):
    """Удалить все записи кассы модератора."""
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute('DELETE FROM moderator_cash WHERE moderator_id=?', (moderator_id,))
    db.commit()
    db.close()


def record_partner_earning(order_number, order_price, net_profit, partner_share, service=''):
    now_msk = datetime.now(MSK)
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO partner_earnings (order_number, order_price, net_profit, partner_share, service, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (str(order_number), float(order_price), float(net_profit), float(partner_share), service, now_msk.isoformat())
    )
    db.commit()
    db.close()


def get_partner_monthly_total(year, month):
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    month_start = f'{year:04d}-{month:02d}-01'
    month_end = f'{next_year:04d}-{next_month:02d}-01'
    cursor.execute(
        'SELECT COALESCE(SUM(partner_share), 0), COUNT(*) FROM partner_earnings WHERE created_at >= ? AND created_at < ?',
        (month_start, month_end)
    )
    row = cursor.fetchone()
    db.close()
    return {'total': row[0], 'count': row[1]}


def get_partner_daily_total(year, month, day):
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    day_start = f'{year:04d}-{month:02d}-{day:02d}'
    if day == 31 or (day == 30 and month in (4, 6, 9, 11)) or (day == 28 and month == 2):
        if month == 12:
            next_year, next_month, next_day = year + 1, 1, 1
        else:
            next_year, next_month, next_day = year, month + 1, 1
    else:
        next_year, next_month, next_day = year, month, day + 1
    day_end = f'{next_year:04d}-{next_month:02d}-{next_day:02d}'
    cursor.execute(
        'SELECT COALESCE(SUM(partner_share), 0), COUNT(*) FROM partner_earnings WHERE created_at >= ? AND created_at < ?',
        (day_start, day_end)
    )
    row = cursor.fetchone()
    db.close()
    return {'total': row[0], 'count': row[1]}


def format_cash_line(cash_stats, key):
    """Форматировать одну строку (issued/spent/balance) по всем валютам через пробел."""
    parts = []
    for cur, sym in CASH_CURRENCIES.items():
        val = cash_stats[cur][key]
        if val != 0:
            parts.append(f'{_fmt(val)}{sym}')
    return ' · '.join(parts) if parts else '0₽'


def _fmt(val):
    """Форматировать число: целое если без дроби, иначе 2 знака."""
    return str(int(val)) if val == int(val) else f'{val:.2f}'


def get_cash_history(moderator_id, limit=15):
    """Последние N транзакций кассы. Возвращает (type, amount, comment, created_at, currency)."""
    db = sqlite3.connect(PENALTIES_DB)
    cursor = db.cursor()
    cursor.execute(
        'SELECT type, amount, comment, created_at, COALESCE(currency, "RUB") FROM moderator_cash WHERE moderator_id=? ORDER BY id DESC LIMIT ?',
        (moderator_id, limit)
    )
    rows = cursor.fetchall()
    db.close()
    return rows


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
    last_daily_report = None

    def checker_loop():
        nonlocal last_monthly_reset, last_daily_report
        while True:
            try:
                now_msk = datetime.now(MSK)

                # Аннулирование штрафов каждое 1-е число месяца
                month_key = (now_msk.year, now_msk.month)
                if now_msk.day == 1 and last_monthly_reset != month_key:
                    reset_monthly_penalties()
                    # Ежемесячный отчёт партнёру
                    try:
                        if now_msk.month == 1:
                            prev_month, prev_year = 12, now_msk.year - 1
                        else:
                            prev_month, prev_year = now_msk.month - 1, now_msk.year
                        _month_names = {1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                                        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                                        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'}
                        stats = get_partner_monthly_total(prev_year, prev_month)
                        bot.send_message(
                            PARTNER_ID,
                            f'📊 Итоги за {_month_names[prev_month]} {prev_year}\n\n'
                            f'Закрытых заявок с прибылью: {stats["count"]}\n'
                            f'💵 Ваша выручка (5%): {stats["total"]:.2f} ₽'
                        )
                    except Exception as _pe:
                        print(f'[PARTNER] Ошибка месячного отчёта: {_pe}')
                    last_monthly_reset = month_key
                    try:
                        bot.send_message(
                            admin_group_id,
                            f'🔄 Штрафы аннулированы!\n'
                            f'Начало нового месяца — все штрафы обнулены.'
                        )
                    except Exception:
                        pass

                # Ежедневный отчёт партнёру в 00:00 МСК
                day_key = (now_msk.year, now_msk.month, now_msk.day)
                if now_msk.hour == 0 and last_daily_report != day_key:
                    last_daily_report = day_key
                    try:
                        from datetime import timedelta
                        prev_dt = now_msk - timedelta(days=1)
                        day_stats = get_partner_daily_total(prev_dt.year, prev_dt.month, prev_dt.day)
                        bot.send_message(
                            PARTNER_ID,
                            f'📅 Итоги за {prev_dt.strftime("%d.%m.%Y")}\n\n'
                            f'Закрытых заявок с прибылью: {day_stats["count"]}\n'
                            f'💵 Ваша выручка (5%): {day_stats["total"]:.2f} ₽'
                        )
                    except Exception as _de:
                        print(f'[PARTNER] Ошибка дневного отчёта: {_de}')

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