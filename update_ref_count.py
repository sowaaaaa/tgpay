import sqlite3

db = sqlite3.connect('files/users.db')
cursor = db.cursor()

cursor.execute('SELECT id FROM users')
users = cursor.fetchall()

updated = 0
for (user_id,) in users:
    cursor.execute('SELECT COUNT(*) FROM users WHERE referr_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    cursor.execute('UPDATE users SET ref_count = ? WHERE id = ?', (count, user_id))
    if count > 0:
        print(f'{user_id}: {count} рефералов')
        updated += 1

db.commit()
db.close()
print(f'\nГотово. Обновлено {updated} пользователей с рефералами')