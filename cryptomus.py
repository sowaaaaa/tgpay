import json
import logging
from fastapi import FastAPI
from fastapi.requests import Request
from help import *
from texts import *
from bot import adminGroup, arhiveGroup
import uvicorn
import telebot

bot = telebot.TeleBot("6795473678:AAGGEVG9HnbQ__CQfrof7DtakplufZoipxQ")

app = FastAPI()

@app.get("/cryptomus/test")
async def test_get():
    return {"Hello": "World"}

@app.post("/cryptomus")
async def merchant_test(request: Request):
    response = await request.json()
    # bot.send_message(chat_id=944108539, text=f"{response}")
    json_data = json.loads(response["additional_data"])
    user_id = json_data["user_id"]
    price = json_data["price"]
    username = json_data["username"]
    currency = response["currency"]
    # bot.send_message(chat_id=944108539, text=f"{json_data}")
    if response['status'] in ('paid', 'paid_over'):
        bot.send_message(user_id, f"✅ Ваш платеж одобрен")
        try:
            with open("promocode.json", encoding="utf-8") as file:
                data = json.load(file)
            promocode = get_promocode(user_id)
            promocode_procent = data[promocode]['procent']
            procent = ((int(price)/100)*int(promocode_procent))
            promocode_summa = int(price) + procent
            add_deposit(user_id, str(promocode_summa))
            if currency == "RUB":
                bot.send_message(user_id, f"На ваш счет поступило {promocode_summa}")
                bot.send_message(arhiveGroup, f"Id пользователя: {user_id}\nПользователь: @{username}\nОплата через cryptomus на сумму: {price} с помощью RUB\nНомер заявки: {response['uuid']}")
                data[promocode]["wasted_user"].append(user_id)
                with open("promocode.json", "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                delete_promocode(user_id)
            else:
                bot.send_message(user_id, f"На ваш счет поступило {promocode_summa}")
                bot.send_message(arhiveGroup, f"Id пользователя: {user_id}\nПользователь: @{username}\nОплата через cryptomus на сумму: {price}\nНомер заявки: {response['uuid']}")
                data[promocode]["wasted_user"].append(user_id)
                with open("promocode.json", "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                delete_promocode(user_id)
        except:
            if currency == "RUB":
                add_deposit(user_id, price)
                bot.send_message(user_id, f"На ваш счет поступило {price}")
                bot.send_message(arhiveGroup, f"Id пользователя: {user_id}\nПользователь: @{username}\nОплата через cryptomus на сумму: {price} с помощью RUB\nНомер заявки: {response['uuid']}")
            else:
                add_deposit(user_id, price)
                bot.send_message(user_id, f"На ваш счет поступило {price}")
                bot.send_message(arhiveGroup, f"Id пользователя: {user_id}\nПользователь: @{username}\nОплата через cryptomus на сумму: {price}\nНомер заявки: {response['uuid']}")
    elif response["status"] == "wrong_amount":
        bot.send_message(user_id, f"❌ Вы отправили неправильную сумму")  
    elif response["status"] == "cancel":
        bot.send_message(user_id, f"❌ Ваш платеж отменен")  

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=8000)