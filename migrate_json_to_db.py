import os
import json
import sqlite3
import re

# ========== НАСТРОЙКИ ==========
JSON_FOLDER = "files"
DB_PATH = "files/user_data.db"
# ================================

def parse_filename(filename):
    name = filename.replace(".json", "")
    match = re.match(r'^(\d+)_(.+)$', name)
    if match:
        return match.group(1), f"user_data_{match.group(2)}"
    match = re.match(r'^(\d+)$', name)
    if match:
        return match.group(1), "user_data"
    return None, None


def sanitize_column(name):
    name = re.sub(r'[^\w]', '_', str(name))
    if name[0].isdigit():
        name = "col_" + name
    # если ключ называется user_id — переименовываем чтобы не конфликтовал
    if name.lower() == "user_id":
        name = "data_user_id"
    return name


def create_table(cursor, table_name, keys):
    sanitized = {}
    seen_columns = set()
    seen_columns.add("user_id")  # резервируем user_id

    for k in keys:
        safe = sanitize_column(k)
        # если имя столбца уже занято — добавляем суффикс
        original_safe = safe
        counter = 1
        while safe in seen_columns:
            safe = f"{original_safe}_{counter}"
            counter += 1
        seen_columns.add(safe)
        sanitized[k] = safe

    columns = ["user_id TEXT PRIMARY KEY"]
    for safe in sanitized.values():
        columns.append(f'"{safe}" TEXT')

    sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)})'
    cursor.execute(sql)
    return sanitized


def migrate():
    if not os.path.exists(JSON_FOLDER):
        print(f"Папка {JSON_FOLDER} не найдена!")
        return

    table_keys = {}
    file_map = []

    for filename in os.listdir(JSON_FOLDER):
        if not filename.endswith(".json"):
            continue
        user_id, table_name = parse_filename(filename)
        if user_id is None:
            continue
        file_map.append((filename, user_id, table_name))
        if table_name not in table_keys:
            table_keys[table_name] = set()

    for filename, user_id, table_name in file_map:
        filepath = os.path.join(JSON_FOLDER, filename)
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                table_keys[table_name].update(data.keys())
        except Exception as e:
            print(f"Ошибка чтения {filename}: {e}")

    print(f"Найдено таблиц: {len(table_keys)}")
    for t, keys in table_keys.items():
        print(f"  {t}: {len(keys)} уникальных ключей — {keys}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    table_mappings = {}
    for table_name, keys in table_keys.items():
        mapping = create_table(cursor, table_name, keys)
        table_mappings[table_name] = mapping
        print(f"Таблица '{table_name}' создана.")

    conn.commit()

    success = 0
    errors = 0

    for filename, user_id, table_name in file_map:
        filepath = os.path.join(JSON_FOLDER, filename)
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                print(f"Пропускаем {filename} — не словарь")
                continue

            mapping = table_mappings[table_name]

            col_names = ["user_id"]
            values = [user_id]

            for original_key, value in data.items():
                safe_col = mapping.get(original_key)
                if safe_col:
                    col_names.append(f'"{safe_col}"')
                    if isinstance(value, (dict, list)):
                        values.append(json.dumps(value, ensure_ascii=False))
                    else:
                        values.append(str(value) if value is not None else None)

            placeholders = ", ".join(["?" for _ in values])
            cols_str = ", ".join(col_names)
            sql = f'INSERT OR REPLACE INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'
            cursor.execute(sql, values)
            success += 1

        except Exception as e:
            print(f"Ошибка при обработке {filename}: {e}")
            errors += 1

    conn.commit()
    conn.close()

    print(f"\n✅ Готово!")
    print(f"  Успешно: {success} файлов")
    print(f"  Ошибок:  {errors} файлов")
    print(f"  БД сохранена: {DB_PATH}")


if __name__ == "__main__":
    migrate()
