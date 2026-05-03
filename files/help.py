from calendar import month
import hashlib
import sqlite3
from datetime import datetime
import datetime as dt
import json
import os
from telebot import types
from hashlib import md5
import requests
import base64
import logging
import pytz

def check_time_active(data: json):
    now_time = datetime.now(pytz.timezone('Europe/Moscow')).time()

    start_time = dt.time(0, 30) 
    end_time = dt.time(6, 0) 

    if start_time <= now_time <= end_time:
        data["active"] = 0
        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)
    else:
        data["active"] = 1
        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)  

# Отчет об пополнениях/деньгах

# Получение отчета за день
def get_money_report_for_day():
    data = json.load(open("money_report.json", encoding="utf-8"))
    return data["day_report"]["money"]

# Получение отчета за месяц
def get_money_report_for_month():
    data = json.load(open("money_report.json", encoding="utf-8"))
    return data["month_report"]["money"]

# Обновление отчета за день
def update_money_report_for_day(money=0):
    logging.info("за день")
    data = json.load(open("money_report.json", encoding="utf-8"))
    if data["day_report"]["date"]:
        day_date = datetime.strptime(data["day_report"]["date"], "%Y-%m-%d %H:%M:%S")
        day_delta = dt.timedelta(days=1)
        if datetime.now() >= day_date + day_delta: # если прошел день
            data["day_report"]["date"] = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
            data["day_report"]["money"] = money
            with open("money_report.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
        else:
            now_money = data["day_report"]["money"]
            data["day_report"]["money"] = int(now_money) + int(money)
            with open("money_report.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
    else:
        data["day_report"]["date"] = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
        data["day_report"]["money"] = money
        with open("money_report.json", "w", encoding="utf-8") as file:
            json.dump(data, file) 
    logging.info(data)

# Обновление отчета за месяц
def update_money_report_for_month(money=0):
    logging.info("за мес")
    data = json.load(open("money_report.json", encoding="utf-8"))
    if data["month_report"]["date"]:
        month_date = datetime.strptime(data["month_report"]["date"], "%Y-%m-%d %H:%M:%S")
        month_delta = dt.timedelta(days=30)
        if datetime.now() >= month_date + month_delta: # если прошел месяц
            data["month_report"]["date"] = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
            data["month_report"]["money"] = money
            with open("money_report.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
        else:
            now_money = data["month_report"]["money"]
            data["month_report"]["money"] = int(now_money) + int(money)
            with open("money_report.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
    else:
        data["month_report"]["date"] = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
        data["month_report"]["money"] = money
        with open("money_report.json", "w", encoding="utf-8") as file:
            json.dump(data, file) 
    logging.info(data)

# Реф. система

# Получение баланса юзера
def get_ref_balance(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT referr_balance FROM users WHERE id = ?', (user_id,))
    data = cursor.fetchone()
    return data[0]

# Получение реферала
def get_ref_user(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT referr_id FROM users WHERE id = ?', (user_id,))
    data = cursor.fetchone()
    return data[0]

# Получение реферальных юзеров
def get_ref_users(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT COUNT(*) FROM users WHERE referr_id = ?', (user_id,))
    data = cursor.fetchone()
    return data[0]

# Снятие суммы для реферала
def minus_balance_ref(user_id, value):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    value = float(value)
    sql_query = "UPDATE users SET referr_balance = referr_balance - ? WHERE id = ?"
    cursor.execute(sql_query, (value , user_id))
    db.commit()
    db.close()

# Добавление суммы для реферала
def add_balance_ref(user_id, value):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    value = float(value)
    sql_query = "UPDATE users SET referr_balance = referr_balance + ? WHERE id = ?"
    cursor.execute(sql_query, (value , user_id))
    db.commit()
    db.close()

# Добавление реферала 
def add_ref(referr_id, user_id):
    regestry(user_id)
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    sql_query = f"UPDATE users SET referr_id = ? WHERE id = ?"
    cursor.execute(sql_query, (referr_id, user_id))
    db.commit()
    db.close()

# Юмани хелп функции
def get_requisites():
    data = json.load(open("yoomany_requisites.json", encoding="utf-8"))
    if data:
        return data
    return None

# MERCHANT

#Получение ссылки оплаты    
def get_merchant_link(price: str):
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJpYnRyOGx0QjVmZ0FNMjBXRkVIV1RCVlVPMDEzIiwiZGF0ZSI6IjIwMjQtMDctMDNUMTk6MzU6NTUuOTU1WiIsImlhdCI6MTcyMDAzNTM1NX0.gLKOo0JtnmOrYjasAopN1trppfusIo07jarD3-gzvnI",
        "Content-Type": "application/json"
    }
    data = {
        "isPartnerFee": "true",
        "pricing": {
            "local": {
            "amount": f"{price}",
            "currency": "RUB"
            }
        }
    }
    response = requests.post(url="https://api.merchant001.io/v1/transaction/merchant", headers=headers, data=json.dumps(data))
    return response.json()

#Получение ссылки оплаты payok
def get_link(amount: str):
    number = json.load(open("purchase_number.json"))
    payment = str(number["application_number"])
    shop = '12117'
    desc = 'Пополнение баланса'
    secret_key = "bcd206cf2a1c1752ff5a5cfb32269886"
    currency = 'RUB'

    # Формируем данные для подписи
    data = [amount, payment, shop, currency, desc, secret_key]
    sign = md5('|'.join(data).encode('utf-8')).hexdigest()

    # Формируем URL
    url = f'https://payok.io/pay?amount={amount}&payment={payment}&shop={shop}&desc={desc}&sign={sign}'

    # Обновляем номер заявки
    number["application_number"] += 1

    # Сохраняем обновленные данные обратно в JSON файл
    with open("purchase_number.json", "w", encoding="utf-8") as file:
        json.dump(number, file, indent=2, ensure_ascii=False)

    return url

# CRYPTOMUS

# #Получение ссылки оплаты cryptomus
def get_cryptomus_link(data: dict):
    api_key = "gGnc7sHMN3ZFTAauGEskARYSyGnZ928HbkP8nlmdhMdy6rPJaz5Mwari1Z7qieNNxm4Og8Xse8KYaBnAw16uf276upiwloKEYHsDniObrQbcRFFYUEPDXAHQrV8Ytr9j"
    merchant_id = "988f4211-6ec5-4bb0-976e-88dd365d9927"
    encoded_data = base64.b64encode(
        json.dumps(data).encode("utf-8")
    ).decode("utf-8")

    sign = hashlib.md5(f"{encoded_data}{api_key}".encode("utf-8")).hexdigest()

    headers = {
        "merchant": merchant_id,
        "sign": sign    
    }

    response = requests.post(url="https://api.cryptomus.com/v1/payment", json=data, headers=headers)

    return response.json()

# Nicepay
def get_nicepay_link(order_id: str, amount: int, currency: str, customer: str):
    nicepay_config = {
        "merchant_id": "66f9d2e88ae1fc689cdb0f93",
        "secret_key": "StYak-jgSCq-HVw4y-HuRPA-de39U"
    }

    data = {
        "merchant_id": nicepay_config["merchant_id"],
        "secret": nicepay_config["secret_key"],
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "customer": customer,
        "success_url": "https://olexandrapi.tw1.ru/nicepay"
    }

    response = requests.post(url="https://nicepay.io/public/api/payment", json=data)
    return response.json()

def check_nicepay_payment(payment_id : str):
    nicepay_config = {
        "merchant_id": "66f9d2e88ae1fc689cdb0f93",
        "secret_key": "StYak-jgSCq-HVw4y-HuRPA-de39U"
    }
    data = {
        "merchant_id": nicepay_config["merchant_id"],
        "secret": nicepay_config["secret_key"],
        "payment": payment_id,
    }
    response = requests.post(url="https://nicepay.io/public/api/h2hConfirmPaid", json=data)
    return response.json()
def get_payment_info(payment_id: str):
    nicepay_config = {
        "merchant_id": "66f9d2e88ae1fc689cdb0f93",
        "secret_key": "StYak-jgSCq-HVw4y-HuRPA-de39U"
    }
    data = {
        "merchant_id": nicepay_config["merchant_id"],
        "secret": nicepay_config["secret_key"],
        "payment": payment_id,
    }
    response = requests.post(url="https://nicepay.io/public/api/h2hPaymentInfo", json=data)
    return response.json()
def get_promocode(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT promocode FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        db.close()
        if data[0] != None:
            try:
                with open("promocode.json", encoding="utf-8") as file:
                    json_data = json.load(file)
                if json_data[data[0]]["procent"]:
                    pass
                return data[0]
            except:
                db = sqlite3.connect('files/users.db')
                cursor = db.cursor()
                cursor.fetchone()
                cursor.execute('UPDATE users SET promocode = ? WHERE id = ?', (None, chat_id,))
                db.commit()
                db.close()
        return None
    else:
        regestry(chat_id)
        return None

def delete_promocode(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute('UPDATE users SET promocode = ? WHERE id = ?', (None, chat_id,))
    db.commit()
    db.close()

def add_promocode(chat_id, promocode):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT date,balans FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        cursor.execute('UPDATE users SET promocode = ? WHERE id = ?', (promocode, chat_id,))
        db.commit()
        db.close()
    else:
        regestry(chat_id)
        cursor.execute('UPDATE users SET promocode = ? WHERE id = ?', (promocode, chat_id,))
        db.commit()
        db.close()

# Проверка наличия пользователя

def check_user(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT id FROM users WHERE id = ?', (user_id,))
    data = cursor.fetchone()
    return data

#Регистрация
def regestry(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT id FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if not data:
        date = datetime.now().date().strftime('%d.%m.%Y')
        sql_query = f"INSERT INTO users (id,date,balans) VALUES (?,?,?)"
        cursor.execute(sql_query, (
            chat_id,
            date,
            0
            ))
        db.commit()
    db.close()
#Кабинет
def update_balance(chat_id, amount):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()

    cursor.execute('SELECT balans FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()

    if data is not None:
        new_balance = data[0] + amount
        cursor.execute('UPDATE users SET balans = ? WHERE id = ?', (new_balance, chat_id))
        db.commit()
        db.close()
        return f'Баланс обновлен: {new_balance}₽'
    else:
        db.close()
def get_cabinet(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT date,balans,promocode FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        db.close()
        # promo_code = data[2] if data[2] is not None else "Нет"
        if data[2]:
            kabinet = f"""🖥 Кабинет\n🆔 {chat_id}\n💵Баланс: {data[1]}₽\n⏱Дата регистрации: {data[0]}\nДействующий промокод: {data[2]}"""
            return kabinet
        else:
            kabinet = f"""🖥 Кабинет\n🆔 {chat_id}\n💵Баланс: {data[1]}₽\n⏱Дата регистрации: {data[0]}"""
            return kabinet
    else:
        regestry(chat_id)
        cursor.execute(f'SELECT date,balans FROM users WHERE id = ?', (chat_id,))
        data = cursor.fetchone()
        if data:
            db.close()
            kabinet = f"""🖥 Кабинет\n🆔 {chat_id}\n💵Баланс: {data[1]}₽\n⏱Дата регистрации: {data[0]}"""
            return kabinet
            
#Отзыв в базу
def send_feedback(message):
    db = sqlite3.connect('files/otzivi.db')
    cursor = db.cursor()
    date = datetime.now().date().strftime('%d.%m.%Y')
    sql_query = f"INSERT INTO otzivi (id,date,otziv,name) VALUES (?,?,?,?)"
    cursor.execute(sql_query, (
        message.chat.id,
        date,
        message.text,
        message.chat.first_name
        ))
    db.commit()
    db.close()
#Возвращает все отзывы
def get_feedback(flag=0):
    print('flag', flag)
    db = sqlite3.connect('files/otzivi.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT name,otziv, id FROM otzivi')
    data = cursor.fetchall()
    text = ''
    feeds = []
    n = 1
    for item in reversed(data):
        if flag==0:
            text+=f'<b>{item[0]}</b>\n{item[1]}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
        else:
            text+=f'<b>{item[0]}</b>\n{item[2]}\n{item[1]}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
        if n == 5:
            feeds.append(text)
            text = ''
            n=0
        n+=1
    db.commit()
    db.close()
    return feeds


def send_long_message(chat_id, text, bot):

    # Разбиваем сообщение на части, если оно слишком длинное
    max_length = 4096
    for i in range(0, len(text), max_length):
        part = text[i:i + max_length]
        bot.send_message(chat_id, part, parse_mode='HTML')


def feed(id, all):
    markup = types.InlineKeyboardMarkup(row_width=3)
    if id == 32423:
        pass
    else:
        markup.add(types.InlineKeyboardButton(text='⏪', callback_data=f'feed_dec_{id}'),
                    types.InlineKeyboardButton(text=f'{id}/{all}', callback_data='pass'),
                    types.InlineKeyboardButton(text='⏩', callback_data=f'feed_inc_{id}'))
        markup.add(types.InlineKeyboardButton(text = "⬆️ Оставить отзыв", callback_data = 'send_feedback'))
    return markup
#Получение баланса
def get_balans(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT balans FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        db.close()
        return data[0]
    else:
        regestry(chat_id)
        cursor.execute(f'SELECT balans FROM users WHERE id = ?', (chat_id,))
        data = cursor.fetchone()
        db.close()
        return data[0]
#Работа с балансом
def update_balanse(chat_id, key):
    file = str(chat_id) + '.json'
    if os.path.exists('files/'+file):
        with open('files/'+file, encoding='utf-8') as json_file:
            file_data = json.load(json_file)
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT balans FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        value=data[0]-float(file_data[key])
        cursor.execute('UPDATE users SET balans = ? WHERE id = ?', (value,chat_id))
        db.commit()
        db.close()
        return True
#Пополнение баланса
def add_deposit(id, summ):
    if str(summ).replace('.', '').replace('-', '').isdigit():
        db = sqlite3.connect('files/users.db')
        cursor = db.cursor()
        cursor.execute(f'SELECT balans FROM users WHERE id = ?', (id,))
        data = cursor.fetchone()
        summ = float(summ)
        if data:
            if int(summ) == 0:
                value=0
            else:
                value=float(summ)+data[0]
            cursor.execute('UPDATE users SET balans = ? WHERE id = ?', (value, id))
            db.commit()
            db.close()
            return summ
        else:
            db.close()
            return 'user not found'
    else:
        return False
def change_deposit(id, summ):
    if summ.replace('.', '').isdigit():
        db = sqlite3.connect('files/users.db')
        cursor = db.cursor()
        cursor.execute(f'SELECT balans FROM users WHERE id = ?', (id,))
        data = cursor.fetchone()
        if data:
            value=float(summ)
            cursor.execute('UPDATE users SET balans = ? WHERE id = ?', (value, id))
            db.commit()
            db.close()
            return summ
        else:
            db.close()
            return 'user not found'
    else:
        return False
#Архив услуг
def to_arhiv(chat_id, usluga, summ):
    file = 'count.json'
    if os.path.exists('files/'+file):
        with open('files/'+file, encoding='utf-8') as json_file:
            file_data = json.load(json_file)

    db = sqlite3.connect('files/arhive.db')
    cursor = db.cursor()
    date = datetime.now().date().strftime('%d.%m.%Y')
    number = file_data['count']
    if number:
        id = number+1
    else:
        id = 100
    file_data['count'] = id
    with open('files/'+file, 'w', encoding='utf-8') as outfile:
        json.dump(file_data, outfile)
    sql_query = f"INSERT INTO uslugi (id,date,usluga,summa,number) VALUES (?,?,?,?,?)"
    cursor.execute(sql_query, (
        chat_id,
        date,
        usluga,
        float(summ),
        id
        ))
    db.commit()
    db.close()

    return id
#Отмена заявки
def cancel_request(text):
    number = text.split('Заявка №')[1].split('\n')[0]
    db = sqlite3.connect('files/arhive.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT number FROM uslugi WHERE number = ?', (int(number),))
    data = cursor.fetchone()
    if data:
        cursor.execute('DELETE FROM uslugi WHERE number = ?', (int(number),))
        db.commit()
        db.close()
        return True
    else:
        db.close()
        return False
#История профиля
def get_history(chat_id):
    db = sqlite3.connect('files/arhive.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT date,usluga,summa,number FROM uslugi WHERE id = ?', (chat_id,))
    data = cursor.fetchall()
    text = ''
    for item in reversed(data):
        text+=f'<b>Заказ №{item[3]}</b>\nДата: {item[0]}\nУслуга: {item[1]}\nСумма: {item[2]}\n➖➖➖➖➖➖➖\n'
    db.commit()
    db.close()
    return text
#Курс валют
def get_kurs(valuta):
    file = 'valuta.json'
    if os.path.exists('files/'+file):
        with open('files/'+file, encoding='utf-8') as json_file:
            file_data = json.load(json_file)
    if valuta == 'usd':
        return float(file_data[valuta])
    elif valuta == 'eur':
        return float(file_data[valuta])
    elif valuta == 'try':
        return float(file_data[valuta])
    elif valuta == 'uah':
        return float(file_data[valuta])

#Все юзеры
def get_all_users():
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT id FROM users')
    data = cursor.fetchall()
    db.close()
    chat_ids = []
    for chat_id in data:
        chat_ids.append(chat_id[0])
    return chat_ids
#Ротация карт
def get_cards():
    db = sqlite3.connect('files/cards.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT card FROM cards')
    data = cursor.fetchall()
    db.close()
    cards = []
    for card in data:
        cards.append(card[0])
    return cards


def rotaciya():
    file = 'cards.json'

    if os.path.exists('files/' + file):
        with open('files/' + file, encoding='utf-8') as json_file:
            file_data = json.load(json_file)

    cards = get_cards()

    if not cards:
        return "Нет карт для обработки"

    n = file_data.get('nom', 0)

    print(n, cards)
    if n >= len(cards):
        n = 0

    card = cards[n]

    n = (n + 1) % len(cards)

    file_data['nom'] = n
    with open('files/' + file, 'w', encoding='utf-8') as outfile:
        json.dump(file_data, outfile)

    return card

def check_and_get_denomination(code):
    database_name="files/codes.db"
    connection = sqlite3.connect(database_name)
    cursor = connection.cursor()

    # Проверяем наличие кода в базе
    cursor.execute("SELECT denomination FROM codes WHERE code=?", (code,))
    result = cursor.fetchone()

    if result is not None:
        denomination = result[0]
        # Удаляем ваучер из базы
        cursor.execute("DELETE FROM codes WHERE code=?", (code,))
        connection.commit()
        connection.close()
        return denomination
    else:
        connection.close()
        return None

def get_all_users_text():
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT id, balans FROM users')
    data = cursor.fetchall()
    db.close()
    texts = []
    text = ''
    summ = 0
    count = 0
    for id in data:
        text+=f'{id[0]} - {round(id[1],2)} р.\n'
        summ+=id[1]
        count+=len(text)
        if len(text)>4000:
            texts.append(text)
            text = f'{id[0]} - {round(id[1],2)} р.\n'
            count = 0
    texts.append(text)
    texts.append(f'Общаяя сумма: {round(summ,2)} р.')
    return texts