import sqlite3
import telebot

bot = telebot.TeleBot("6795473678:AAGGEVG9HnbQ__CQfrof7DtakplufZoipxQ")

db = sqlite3.connect('files/users.db')
cursor = db.cursor()
cursor.execute('SELECT id FROM users WHERE username IS NULL')
rows = cursor.fetchall()
if not rows:
    print("Все пользователи уже имеют username")
    db.close()
else:
    print(f"Миграция username: {len(rows)} пользователей без username")
    count = 0
    for (user_id,) in rows:
        print("...")
        try:
            user = bot.get_chat(user_id)
            if user.username:
                cursor.execute('UPDATE users SET username = ? WHERE id = ?', (user.username, user_id))
                count += 1
                print(f"{user_id} -> @{user.username}")
        except Exception as e:
            print(e)
    db.commit()
    db.close()
    print(f"Миграция username завершена: обновлено {count} из {len(rows)}")
