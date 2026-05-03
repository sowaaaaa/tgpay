import sqlite3

ADMIN_ID = 6732194898
DB_PATH = 'files/users.db'

db = sqlite3.connect(DB_PATH)
cursor = db.cursor()

# 1. Считаем сумму неактивных балансов
cursor.execute("""
    SELECT COALESCE(SUM(balans), 0)
    FROM users
    WHERE balans > 0
      AND last_activity <= datetime('now', '-1 year')
      AND id != ?
""", (ADMIN_ID,))

total_amount = cursor.fetchone()[0]

if total_amount > 0:
    # 2. Начисляем админу
    cursor.execute("""
        UPDATE users
        SET admin_balance = COALESCE(admin_balance, 0) + ?
        WHERE id = ?
    """, (total_amount, ADMIN_ID))

    # 3. Обнуляем балансы пользователей
    cursor.execute("""
        UPDATE users
        SET balans = 0
        WHERE balans > 0
          AND last_activity <= datetime('now', '-1 year')
          AND id != ?
    """, (ADMIN_ID,))

    db.commit()
    print(f"✅ Переведено админу: {total_amount}")
else:
    print("ℹ️ Неактивных балансов нет")

db.close()
