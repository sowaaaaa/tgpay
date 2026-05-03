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

config = {
    "merchant_id": "66f9d2e88ae1fc689cdb0f93",
    "secret_key": "StYak-jgSCq-HVw4y-HuRPA-de39U"
}

app = FastAPI()

@app.get("/nicepay/test")
async def test_get():
    logging.info(f"gewgew")
    return {"Hello": "World"}

@app.get("/nicepay")
async def payment_notification(
        result: str,
        payment_id: str,
        merchant_id: str,
        order_id: str,
        amount: float,
        amount_currency: str,
        profit: float,
        profit_currency: str,
        method: str,
        hash: str
    ):
    # logging.info(f"{result}\n{payment_id}\n{order_id}\n{amount}")
    user_data = order_id.split("_")
    user_id = user_data[0]
    price = str(amount)[:-4]
    # logging.info(str(amount))
    # logging.info(price)
    username = user_data[1]
    # bot.send_message(chat_id=944108539, text=f"{json_data}")
    if result == "success":
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
            bot.send_message(arhiveGroup, f"Id пользователя: {user_id}\nПользователь: @{username}\nОплата через nicepay на сумму: {price}\nНомер заявки: {payment_id}")
            data[promocode]["wasted_user"].append(user_id)
            with open("promocode.json", "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            delete_promocode(user_id)

        except:
            add_deposit(user_id, price)
            bot.send_message(user_id, f"На ваш счет поступило {price}")
            bot.send_message(arhiveGroup, f"Id пользователя: {user_id}\nПользователь: @{username}\nОплата через nicepay на сумму: {price}\nНомер заявки: {payment_id}")
    
    # elif response["status"] == "wrong_amount":
    #     bot.send_message(user_id, f"❌ Вы отправили неправильную сумму")  
    elif result == "error":
        bot.send_message(user_id, f"❌ Ваш платеж отменен")  

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=8001)