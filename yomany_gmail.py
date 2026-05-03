import base64
from email.header import decode_header
import imaplib
import email
import json
from bs4 import BeautifulSoup
import pytz
from datetime import datetime, timedelta
import random
import asyncio
from help import *
from bot import bot, adminGroup, arhiveGroup

async def gmail_parsing():
    imap_server = "imap.rambler.ru"

    sender = "swwgzhshcb@rambler.ru"
    password = "3449070z9bLH4"

    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(sender, password)

    mail.select("inbox")

    while True:

        # print("gmail_parsing_go")

        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()

        if email_ids:
            for email_id in email_ids:
                # Выбрать последнее письмо
                # email_id = int(email_id.decode())
                # latest_email_id = email_ids[email_id-1]

                # Получение самого письма
                status, msg_data = mail.fetch(email_id, "(RFC822)")

                # Анализ и декодирование письма
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Получение заголовков
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            # Декодирование темы, если она закодирована
                            subject = subject.decode(encoding or 'utf-8')

                        # print("Subject:", subject)

                        if "пришли деньги" in subject:
                            
                            # Получение отправителя
                            from_ = msg.get("From")
                            if "yoomoney" in from_:
                                
                                # print("From:", from_)
                                # Проверка, является ли письмо многосоставным (например, текст и вложения)
                                if msg.is_multipart():
                                    # Проходим по каждой части
                                    for part in msg.walk():
                                        content_type = part.get_content_type()
                                        content_disposition = str(part.get("Content-Disposition"))

                                        # Извлечение текста письма
                                        if "attachment" not in content_disposition:
                                            if content_type == "text/plain":
                                                # Извлекаем текст
                                                body = part.get_payload(decode=True).decode()
                                                # print("Body:", body)

                                else:
                                    # Для непакетного письма
                                    content_type = msg.get_content_type()
                                    # print(content_type)
                                    if content_type == "text/html":
                                        body = msg.get_payload(decode=True).decode()
                                        # print("Body:", body)
                                
                                soup = BeautifulSoup(body, 'html.parser')
                                body_text = soup.get_text()
                                amount = body_text.split("Пришло")[1].split("₽")[0].strip()
                                date_and_time = body_text.split("Дата и время")[0].split("мск")[0].strip().split(" ")[-1]
                                # print(datetime.strptime("19:00", "%H:%M").time() > datetime.now(pytz.timezone('Europe/Moscow')).time())
                                payment_data = {f"{random.randint(10000, 100000)}_{amount.replace(' ', '')}": date_and_time}

                                with open("Yoomoney/payments.json", "r", encoding="utf-8") as file:
                                    data = json.load(file)
                                    if data:
                                        with open("Yoomoney/payments.json", "w", encoding="utf-8") as file:
                                            data.update(payment_data)
                                            json.dump(data, file, indent=4, ensure_ascii=False)
                                    else:
                                        with open("Yoomoney/payments.json", "w", encoding="utf-8") as file:
                                            json.dump(payment_data, file, indent=4, ensure_ascii=False)
        await asyncio.sleep(5)  

async def check_payments():
    while True:
        # print("check_payments_go")
        payments_data = json.load(open("Yoomoney/payments.json"))

        pending_applications = json.load(open("Yoomoney/pending_applications.json"))

        payment_del_keys = []
        pending_del_keys = []

        if payments_data and pending_applications:
            for payment_key, payment_value in payments_data.items():
                
                # Извлекаем часть после _
                suffix1 = payment_key.split('_')[1]

                # Проходим по ключам второго словаря
                for pending_key, pending_value in pending_applications.items():
                    
                    # Извлекаем часть после _ во втором словаре
                    suffix2 = pending_value["amount"].split('_')[1]
                    
                    # Если совпали суффиксы, добавляем запись в результирующий словарь
                    if suffix1 == suffix2:
                    
                        # Переменные для счета времени
                        time_delta = timedelta(minutes=10)

                        # Получаем время платежа и время заявки
                        payment_date = datetime.strptime(payment_value, "%H:%M")
                        pending_date = datetime.strptime(pending_value["date"], "%H:%M")

                        if payment_date >= pending_date and payment_date <= pending_date+time_delta:
                            payment_del_keys.append(payment_key)
                            pending_del_keys.append(pending_key)

                            user_id = pending_key.split("_")[1]
                            price = pending_value["amount"].split('_')[1]
                            username = pending_value["username"]
                            application_number = pending_value["application_number"]
                            bot.send_message(user_id, f"✅ Ваш платеж одобрен")
                            try:
                                with open("promocode.json", encoding="utf-8") as file:
                                    data = json.load(file)
                                promocode = get_promocode(user_id)
                                promocode_procent = data[promocode]['procent']
                                procent = ((int(price)/100)*int(promocode_procent))
                                promocode_summa = int(price) + procent
                                add_deposit(user_id, str(promocode_summa))
                                bot.send_message(user_id, f"На ваш счет поступило {promocode_summa}")
                                bot.send_message(arhiveGroup, f"Номер заявки {application_number}\nId пользователя: {user_id}\nПользователь: @{username}\nОплата через ЮMoney на сумму: {price}")
                                data[promocode]["wasted_user"].append(user_id)
                                with open("promocode.json", "w", encoding="utf-8") as file:
                                    json.dump(data, file, ensure_ascii=False, indent=4)
                                delete_promocode(user_id)
                            except:
                                add_deposit(user_id, price)
                                bot.send_message(user_id, f"На ваш счет поступило {price}")
                                bot.send_message(arhiveGroup, f"Номер заявки {application_number}\nId пользователя: {user_id}\nПользователь: @{username}\nОплата через ЮMoney на сумму: {price}")

            if payment_del_keys and pending_del_keys:
                
                for key in payment_del_keys:
                    del payments_data[key]
                    
                for key in pending_del_keys:
                    del pending_applications[key]

                # print(payments_data)
                # print(pending_applications)

                with open("Yoomoney/payments.json", "w", encoding="utf-8") as file:
                    json.dump(payments_data, file, ensure_ascii=False, indent=4)
                with open("Yoomoney/pending_applications.json", "w", encoding="utf-8") as file:
                    json.dump(pending_applications, file, ensure_ascii=False, indent=4)
        
        # Удаляем просроченные заявки
        if pending_applications:
            for pending_key, pending_value in pending_applications.items():
                # Переменные для счета времени
                now_time = datetime.now(pytz.timezone('Europe/Moscow')).strftime("%H:%M")
                time_delta = timedelta(minutes=10)

                # Получаем время заявки
                pending_date = datetime.strptime(pending_value["date"], "%H:%M")

                # Проверка на то прошло ли 10 минут с создания заявки
                if now_time >= (pending_date+time_delta).strftime("%H:%M"): # Преобразуем для удачного сравнения без ошибок
                    bot.send_message(chat_id=pending_key.split("_")[1], text=f"Ваша заявка ***{pending_value['application_number']}*** просрочена❌", parse_mode="MARKDOWN")
                    pending_del_keys.append(pending_key)
        # print(pending_del_keys)
        if pending_del_keys:  
            for key in pending_del_keys:
                del pending_applications[key]
            with open("Yoomoney/pending_applications.json", "w", encoding="utf-8") as file:
                json.dump(pending_applications, file, ensure_ascii=False, indent=4)

        await asyncio.sleep(5)  

async def main():
    tasks = []
    gmail_task = asyncio.create_task(gmail_parsing())
    check_task = asyncio.create_task(check_payments())
    tasks.append(gmail_task)
    tasks.append(check_task)
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())