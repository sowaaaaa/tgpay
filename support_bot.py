import os
import json
import hmac
import hashlib
import sqlite3
import logging
import requests
import random
import pytz
from datetime import time as dtime, datetime

MSK = pytz.timezone('Europe/Moscow')
WORK_START = dtime(10, 0)  # 10:00 МСК
WORK_END = dtime(22, 0)    # 22:00 МСК

def is_working_time():
    now = datetime.now(MSK).time()
    return WORK_START <= now <= WORK_END
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
    CommandHandler,
    CallbackQueryHandler
)

# ================= CONFIG =================

BOT_TOKEN = "6872946471:AAFcSVgwtwsz-OB4ig8MhsmKbsdzNVx-dQE" #8624802558:AAEH_K6hUPvh5Qe4jWFEelX5kTgqwJoRHFo  6872946471:AAGVI968FryOJEvfVQlltnbaB492wosYZrc
GROUP_ID = -1002245553470  # ID вашей группы
ADMIN_IDS = [6732194898, 1539247342, 1739548566, 7131879634]

SHOP_ID = 'c503c42c-5289-4994-baf5-22b4766ed9f6'
SECRET_KEY = '92e5db53521a6d5c03221a1361715b34dd67dcb9'

MESSAGES_FILE = "messages.json"

# ===========================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if os.path.exists(MESSAGES_FILE):
    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        user_messages = {int(k): v for k, v in json.load(f).items()}
else:
    user_messages = {}

active_dialogs = {}
OPERATORS = ["Виктория", "Ирина"]
TIPS_FILE = "tips.json"

def check_invoice_status(order_id):
    payload = {
        "shopId": SHOP_ID,
        "orderId": order_id
    }

    json_data = json.dumps(payload, separators=(',', ':'))
    signature = hmac.new(
        SECRET_KEY.encode(),
        json_data.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Signature": signature
    }

    response = requests.post(
        "https://api.lava.ru/business/invoice/status",
        headers=headers,
        data=json_data
    )

    if response.status_code == 200:
        data = response.json().get("data", {})
        return data.get("status")  # created, paid, cancelled...
    else:
        return None
# ================= DB =================
def assign_operator():
    return random.choice(OPERATORS)
def load_tips():
    if os.path.exists(TIPS_FILE):
        with open(TIPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {op: 0 for op in OPERATORS}

def save_tips(tips):
    with open(TIPS_FILE, "w", encoding="utf-8") as f:
        json.dump(tips, f, ensure_ascii=False, indent=4)

def add_tips(operator, amount):
    tips = load_tips()
    tips[operator] += amount
    save_tips(tips)

def get_balance(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute("SELECT balans FROM users WHERE id = ?", (user_id,))
    data = cursor.fetchone()
    db.close()
    return data[0] if data else 0
async def tips_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    tips = load_tips()
    text = "💎 Чаевые операторов:\n\n"
    for op, amount in tips.items():
        text += f"{op}: {amount} ₽\n"

    await update.message.reply_text(text)
DB_PATH = "files/users.db"
def get_total_spent(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT total_spent FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else 0
def get_user_rank(user_id):
    total = get_total_spent(user_id)
    print(user_id)
    if str(user_id) == "7131879634":
        return "⚙️🛠️"
    if total == 0:
        return "❌"
    elif total <= 1000:
        return "✅"
    elif total <= 10000:
        return "💎"
    elif total <= 100000:
        return "🐳"
    else:
        return "🕶"
def add_deposit(user_id, summ):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()

    cursor.execute("SELECT balans FROM users WHERE id = ?", (user_id,))
    data = cursor.fetchone()

    if not data:
        db.close()
        return False

    new_balance = data[0] + summ
    cursor.execute("UPDATE users SET balans = ? WHERE id = ?", (new_balance, user_id))
    db.commit()
    db.close()
    return True


# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_working_time():
        await update.message.reply_text(
            "🚀 Это служба поддержки TGPay!\n\n"
            "Вы написали нам в нерабочее время. Мы обязательно ответим на ваше сообщение, как только начнём работать 🕒\n\n"
            "⏰ Наш график работы: с 10:00 до 22:00 (по МСК)."
        )
        return
    await update.message.reply_text(
        "👋 Салют!\n\nTGPay слушает. Чем помочь?"
    )


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    if not is_working_time():
        await update.message.reply_text(
            "🚀 Это служба поддержки TGPay!\n\n"
            "Вы написали нам в нерабочее время. Мы обязательно ответим на ваше сообщение, как только начнём работать 🕒\n\n"
            "⏰ Наш график работы: с 10:00 до 22:00 (по МСК)."
        )
        return

    user = update.effective_user
    message = update.message

    # Автоподключение оператора
    if user.id not in active_dialogs:
        await context.bot.send_message(
            user.id,
            "👩‍💼 Оператор Виктория подключилась к диалогу."
        )
        active_dialogs[user.id] = True

    # ===== Профиль =====
    if user.username:
        profile_link = f"https://t.me/{user.username}"
        username_text = f"@{user.username}"
    else:
        profile_link = f"tg://user?id={user.id}"
        username_text = "Нет username"

    # ===== Ранг =====
    rank = get_user_rank(user.id)

    caption_text = (
        f"📩 <b>Сообщение от {user.full_name}</b>\n\n"
        f"👤 <b>Username:</b> {username_text}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
        f"🏆 <b>Ранг:</b> {rank}\n\n"
        f"🔗 <a href=\"{profile_link}\">Перейти в профиль</a>\n\n"
        f"💬 <b>Сообщение:</b>\n"
        f"{message.text or message.caption or ''}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Завершить диалог",
                              callback_data=f"close:{user.id}")]
    ])

    # ===== Определяем тип сообщения =====

    if message.photo:
        sent = await context.bot.send_photo(
            chat_id=GROUP_ID,
            photo=message.photo[-1].file_id,
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif message.video:
        sent = await context.bot.send_video(
            chat_id=GROUP_ID,
            video=message.video.file_id,
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif message.document:
        sent = await context.bot.send_document(
            chat_id=GROUP_ID,
            document=message.document.file_id,
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif message.voice:
        sent = await context.bot.send_voice(
            chat_id=GROUP_ID,
            voice=message.voice.file_id,
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif message.video_note:
        sent = await context.bot.send_video_note(
            chat_id=GROUP_ID,
            video_note=message.video_note.file_id
        )
        # отдельным сообщением подпись (у video_note нет caption)
        sent = await context.bot.send_message(
            GROUP_ID,
            caption_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif message.animation:
        sent = await context.bot.send_animation(
            chat_id=GROUP_ID,
            animation=message.animation.file_id,
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    else:
        # обычный текст
        sent = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=caption_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    # ===== Сохраняем ID =====
    user_messages[sent.message_id] = user.id

    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in user_messages.items()}, f)


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    if not update.message.reply_to_message:
        return

    if update.effective_chat.id != GROUP_ID:
        return

    replied_id = update.message.reply_to_message.message_id
    user_id = user_messages.get(replied_id)

    if not user_id:
        return

    await context.bot.copy_message(
        chat_id=user_id,
        from_chat_id=GROUP_ID,
        message_id=update.message.message_id
    )


# ================= CALLBACK =================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # === Закрытие диалога ===
    if data.startswith("close:"):
        user_id = int(data.split(":")[1])

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Поставить оценку", callback_data="rate")],
            [InlineKeyboardButton("📲 Поблагодарить чаевыми", callback_data="tips")],
            [InlineKeyboardButton("📍 Завершить диалог", callback_data="tips_no")]
        ])

        await context.bot.send_message(
            user_id,
            """
✨ Ваш вопрос решил оператор Ирина

Помогли быстро и качественно? Поддержите оператора 👇""",
            reply_markup=keyboard
        )

        active_dialogs.pop(user_id, None)
        await query.edit_message_reply_markup(None)

    # === Отказ ===
    elif data == "tips_no":
        await query.edit_message_text("Спасибо за обращение ❤️")

    # === Начало чаевых ===
    elif data == "tips":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("100 ₽", callback_data="sum:100"),
                InlineKeyboardButton("200 ₽", callback_data="sum:200"),
                InlineKeyboardButton("300 ₽", callback_data="sum:300"),
            ]
        ])
        await query.edit_message_text(
            "Выберите сумму чаевых:",
            reply_markup=keyboard
        )
    # === Начало оценки ===
    elif data == "rate":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐", callback_data="star:1"),
                InlineKeyboardButton("⭐", callback_data="star:2"),
                InlineKeyboardButton("⭐", callback_data="star:3"),
                InlineKeyboardButton("⭐", callback_data="star:4"),
                InlineKeyboardButton("⭐", callback_data="star:5"),
            ]
        ])

        await query.edit_message_text(
            "Оцените работу оператора:",
            reply_markup=keyboard
        )
    # === Нажатие на звезду ===
    elif data.startswith("star:"):
        stars = int(data.split(":")[1])

        # Просто визуальное подтверждение
        text = "⭐" * stars + "☆" * (5 - stars)

        await query.edit_message_text(
            f"Спасибо за оценку!\n\nВаша оценка:\n{text}\n\n"
        )
    # === Выбор суммы ===
    elif data.startswith("sum:"):
        amount = int(data.split(":")[1])
        context.user_data["tips_amount"] = amount

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Внутренний баланс", callback_data="pay_balance")],
            [InlineKeyboardButton("⚡ СБП", callback_data="pay_sbp")]
        ])

        await query.edit_message_text(
            f"Сумма: {amount} ₽\n\nВыберите способ оплаты:",
            reply_markup=keyboard
        )

    # === Баланс ===
    elif data == "pay_balance":
        user_id = query.from_user.id
        amount = context.user_data.get("tips_amount", 0)
        balance = get_balance(user_id)

        if balance < amount:
            await query.edit_message_text("❌ Недостаточно средств.")
            return

        add_deposit(user_id, -amount)

        operator = assign_operator()
        add_tips(operator, amount)  # сохраняем чаевые

        await query.edit_message_text(
            f"✅ Спасибо за чаевые!\n\nНаши операторы всегда на связи и рады вам помочь ❤️"
        )

    # === СБП (Lava) ===
    elif data == "pay_sbp":
        user_id = query.from_user.id
        amount = context.user_data.get("tips_amount")

        order_id = f"TIPS_{user_id}_{int(datetime.now().timestamp())}"

        payload = {
            "shopId": SHOP_ID,
            "sum": amount,
            "orderId": order_id,
            "expire": 300,
            "customFields": f"telegram_id:{user_id}",
            "comment": "Оплата в боте",
            "includeService": ["sbp"]
        }

        json_data = json.dumps(payload, separators=(',', ':'))
        signature = hmac.new(
            SECRET_KEY.encode(),
            json_data.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "Signature": signature
        }

        response = requests.post(
            "https://api.lava.ru/business/invoice/create",
            headers=headers,
            data=json_data
        )

        data_response = response.json()

        if response.status_code == 200 and "url" in data_response.get("data", {}):
            pay_url = data_response["data"]["url"]

            await query.edit_message_text(
                f"🔗 Оплатите по ссылке:\n\n{pay_url}\n\nОжидаем подтверждение оплаты..."
            )

            # Асинхронная проверка каждые 5 секунд, максимум 60 секунд
            import asyncio
            operator = assign_operator()

            for _ in range(12):
                await asyncio.sleep(5)
                status = check_invoice_status(order_id)
                if status.lower() == "success":
                    add_tips(operator, amount)
                    await context.bot.send_message(
                        user_id,
                        f"✅ Оплата прошла успешно!\nНаши операторы всегда на связи и рады вам помочь ❤️"
                    )
                    break
            else:
                await context.bot.send_message(
                    user_id,
                    "❌ Оплата не была подтверждена"
                )
        else:
            await query.edit_message_text("Ошибка создания счёта.")


# ================= MAIN =================

def main():
    from telegram.request import HTTPXRequest
    proxy_request = HTTPXRequest(proxy='socks5://127.0.0.1:10808')
    app = ApplicationBuilder().token(BOT_TOKEN).request(proxy_request).get_updates_request(proxy_request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tip", tips_report))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, handle_user_message))
    app.add_handler(MessageHandler(
        filters.ALL & filters.REPLY & filters.Chat(GROUP_ID),
        handle_admin_reply
    ))
    app.add_handler(CallbackQueryHandler(callbacks))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()