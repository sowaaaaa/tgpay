import telebot
from telebot import types
import requests
import random
from datetime import datetime

TOKEN = "8693337615:AAE0BsseJ8z6y7sAUbHl6QtS5-8HOxGnHfI"
ARCHIVE_GROUP_ID = -5213973456
PRICE_PER_KM = 50

bot = telebot.TeleBot(TOKEN)

drivers = [
    "Михаил №1", "Алексей №2", "Дмитрий №3",
    "Сергей №4", "Андрей №5", "Иван №6", "Павел №7"
]

user_orders = {}  # межгород и город


# --- функции для расстояния ---
def get_coordinates(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json"}
    r = requests.get(url, params=params, headers={"User-Agent": "taxibot"})
    data = r.json()
    if not data:
        return None
    lat = data[0]["lat"]
    lon = data[0]["lon"]
    return lat, lon


def get_distance(address_from, address_to):
    coord1 = get_coordinates(address_from)
    coord2 = get_coordinates(address_to)
    if not coord1 or not coord2:
        return None
    url = f"http://router.project-osrm.org/route/v1/driving/{coord1[1]},{coord1[0]};{coord2[1]},{coord2[0]}?overview=false"
    r = requests.get(url)
    data = r.json()
    distance_km = data["routes"][0]["distance"] / 1000
    return distance_km


# --- стартовое меню ---
def start_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚖 Межгород", "🚕 Город")
    markup.add("🛟 Поддержка", "📜 Правила")
    return markup


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, "Добро пожаловать в такси 🚖\nВыберите услугу:", reply_markup=start_menu())


# --- межгород ---
@bot.message_handler(func=lambda m: m.text == "🚖 Межгород")
def intercity(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Ростов → Краснодар", callback_data="route_Ростов-на-Дону|Краснодар"))
    markup.add(types.InlineKeyboardButton("Донецк → Ростов", callback_data="route_Донецк|Ростов-на-Дону"))
    markup.add(types.InlineKeyboardButton("Луганск → Ростов", callback_data="route_Луганск|Ростов-на-Дону"))
    markup.add(types.InlineKeyboardButton("✏ Ввести свой маршрут", callback_data="custom"))
    bot.send_message(message.chat.id, "Выберите маршрут:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📜 Правила")
def rules(message):
    bot.send_message(message.chat.id, """
Правила сервиса такси «Маяк»
1. Как заказать поездку
1.1. Вы указываете маршрут, мы называем цену. Если цена устраивает — подтверждаете заказ.
1.2. После подтверждения мы присылаем машину. Водитель свяжется с вами или сразу поедет на адрес.

2. Ожидание водителя
2.1. Водитель ждет 5 минут бесплатно с момента прибытия на место.
2.2. Если опаздываете — предупредите. Дальнейшее ожидание оплачивается отдельно (по договоренности с водителем).

3. Отмена поездки
3.1. Отменить можно в любой момент. Но если водитель уже выехал и потратил время, может взиматься небольшая компенсация (обычно 50–100 ₽). Сумма показывается при отмене.
3.2. Если водитель опаздывает больше чем на 10 минут или не приехал — отмена бесплатная.

4. Возврат денег
4.1. Вернем деньги, если:
— Водитель не приехал
— Поездка сорвалась по нашей вине
— Списались лишние средства
4.2. Для возврата напишите нам в Telegram. Обычно решаем вопрос в течение нескольких часов.

5. Животные
5.1. Можно ехать с животным, если предупредить заранее.
5.2. Если питомец испачкал салон — возможна компенсация за химчистку (обсуждается с водителем).

6. Дети
6.1. Если ребенок до 7 лет — сообщите об этом при заказе. Нужно детское кресло? Решим вопрос индивидуально.

7. Забытые вещи
7.1. Забыли что-то в машине? Напишите нам — поможем связаться с водителем.

8. Важные моменты
8.1. В машине нельзя курить, распивать алкоголь и вести себя агрессивно. Водитель имеет право остановить поездку.
8.2. Если возник спор — пишите нам. Разберемся по-человечески.

Поддержка «Маяк» [@TaxiMayakBot]
    """)

@bot.message_handler(func=lambda m: m.text == "🛟 Поддержка")
def support(message):
    bot.send_message(message.chat.id, """
Служба Поддержки работает с 06:00 до 23:00

@TaxiMayakBot
    """)
# --- городское такси ---
@bot.message_handler(func=lambda m: m.text == "🚕 Город")
def city_taxi(message):
    msg = bot.send_message(message.chat.id, "Введите адрес отправления (улица, район или город):")
    bot.register_next_step_handler(msg, city_from)


def city_from(message):
    user_orders[message.chat.id] = {"from": message.text.strip(), "type": "city"}
    msg = bot.send_message(message.chat.id, "Введите адрес назначения (улица, район или город):")
    bot.register_next_step_handler(msg, city_to)


def city_to(message):
    order = user_orders[message.chat.id]

    order["to"] = message.text.strip()

    distance = get_distance(order["from"], order["to"])

    if distance is None:
        bot.send_message(message.chat.id, "Не удалось найти маршрут, попробуйте другой адрес.")
        return

    order["distance"] = distance
    order["price"] = int(distance * PRICE_PER_KM)
    order["driver"] = random.choice(drivers)

    # добавляем маршрут как в межгороде
    order["route"] = f"{order['from']} → {order['to']}"

    request_contact_to_user(message)


# --- выбор маршрута межгорода ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("route_"))
def route_selected(call):
    data = call.data.replace("route_", "")
    if data == "custom":
        msg = bot.send_message(call.message.chat.id, "Введите маршрут через '-' (пример: Ростов-на-Дону - Москва):")
        bot.register_next_step_handler(msg, custom_route)
        return
    parts = data.split("|")
    if len(parts) != 2:
        bot.send_message(call.message.chat.id, "Ошибка маршрута")
        return
    city1, city2 = parts
    bot.edit_message_text("⏳ Рассчитываем расстояние...", call.message.chat.id, call.message.message_id)
    distance = get_distance(city1, city2)
    if distance is None:
        bot.send_message(call.message.chat.id, "Не удалось найти маршрут")
        return
    price = int(distance * PRICE_PER_KM)
    driver = random.choice(drivers)
    route_text = f"{city1} → {city2}"
    user_orders[call.message.chat.id] = {"route": route_text, "price": price, "driver": driver}
    request_contact_to_user(call.message)


def custom_route(message):
    try:
        city1, city2 = map(str.strip, message.text.split("-"))
    except:
        bot.send_message(message.chat.id, "Неверный формат. Попробуйте снова.")
        return
    distance = get_distance(city1, city2)
    if distance is None:
        bot.send_message(message.chat.id, "Не удалось найти маршрут")
        return
    price = int(distance * PRICE_PER_KM)
    driver = random.choice(drivers)
    route_text = f"{city1} → {city2}"
    user_orders[message.chat.id] = {"route": route_text, "price": price, "driver": driver}
    request_contact_to_user(message)


# --- запрос контакта с отменой ---
# --- запрос контакта с показом информации о поездке ---
def request_contact_to_user(message):
    order = user_orders.get(message.chat.id)

    if not order:
        return

    route = order.get("route")
    price = order.get("price")
    driver = order.get("driver")
    distance = order.get("distance")

    distance_text = f"{int(distance)} км" if distance else "неизвестно"

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

    contact_btn = types.KeyboardButton("📞 Отправить телефон", request_contact=True)
    cancel_btn = types.KeyboardButton("❌ Отменить")

    markup.add(contact_btn, cancel_btn)

    bot.send_message(
        message.chat.id,
        f"""
Маршрут: {route}
Расстояние: {distance_text}
Стоимость: {price} ₽
Водитель: {driver}

Оставьте контакт для связи с водителем:
""",
        reply_markup=markup
    )
# --- обработка контакта с отменой ---
@bot.message_handler(content_types=["contact", "text"])
def handle_contact(message):
    if message.text == "❌ Отменить":
        if message.chat.id in user_orders:
            user_orders.pop(message.chat.id)
        bot.send_message(message.chat.id, "✅ Заказ отменён.", reply_markup=start_menu())
        return

    if message.chat.id not in user_orders:
        return

    order = user_orders[message.chat.id]

    if message.contact:
        order["contact"] = message.contact.phone_number
    else:
        order["contact"] = f"Telegram: @{message.from_user.username}"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Картой", callback_data="pay_lava"))
    markup.add(types.InlineKeyboardButton("💵 Наличными", callback_data="pay_cash"))
    bot.send_message(message.chat.id, "Выберите способ оплаты:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "custom")
def custom_route_handler(call):

    msg = bot.send_message(
        call.message.chat.id,
        "Введите маршрут через '-' \n\nПример:\nРостов-на-Дону - Москва"
    )

    bot.register_next_step_handler(msg, custom_route)
# --- обработка оплаты ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def payment(call):
    if call.data == "pay_cash":
        bot.send_message(call.message.chat.id, "✅ Заказ оформлен (наличные)", reply_markup=start_menu())
        user_orders.pop(call.message.chat.id, None)
        return

    if call.message.chat.id not in user_orders:
        return

    order = user_orders.pop(call.message.chat.id)

    bot.send_message(call.message.chat.id, f"💳 Оплата через карту прошла успешно!\nВаш заказ принят.", reply_markup=start_menu())

    date = datetime.now().strftime("%d.%m.%Y")
    text = f"""
    {date}

    Новая заявка 🚖

    Пользователь: @{call.from_user.username}
    ID: {call.from_user.id}
    Маршрут: {order.get('route') or (order.get('from') + ' → ' + order.get('to'))}
    Стоимость: {order['price']} ₽
    Водитель: {order['driver']}
    Контакт: {order['contact']}
    """
    bot.send_message(ARCHIVE_GROUP_ID, text)


bot.infinity_polling()