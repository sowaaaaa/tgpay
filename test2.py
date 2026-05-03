import telebot

bot = telebot.TeleBot("6795473678:AAGGEVG9HnbQ__CQfrof7DtakplufZoipxQ")

@bot.message_handler()
def check_message(message):
    bot.send_message(944108539, "message")

bot.polling(none_stop=True, interval=0)