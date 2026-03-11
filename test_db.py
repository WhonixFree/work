import sqlite3
from pathlib import Path

# Путь к базе данных (такой же, как у тебя)
db_path = Path(__file__).with_name("bot.sqlite3")

# НАСТРОЙКИ
user_id_to_update = 1  # ID пользователя
new_balance_value = 5000.0  # Новый баланс (число)

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row  # Чтобы обращаться к полям по имени
    cur = conn.cursor()

    print("=" * 50)
    print(f"🔄 Изменение баланса для user_id = {user_id_to_update}")
    print("=" * 50)

    # 1. Сначала проверим, существует ли пользователь и какой баланс был
    cur.execute("SELECT id, username, balance FROM users WHERE id = ?", (user_id_to_update,))
    user = cur.fetchone()

    if user:
        print(f"👤 Найдено: {user['username']} (TG_ID: {user['id']})")
        print(f"📉 Старый баланс: {user['balance']}")

        # 2. Выполняем обновление
        # Важно: используем ? для защиты от SQL-инъекций
        cur.execute(
            "UPDATE users SET balance = ? WHERE id = ?",
            (new_balance_value, user_id_to_update)
        )

        # 3. Обязательно сохраняем изменения (commit)
        conn.commit()

        # 4. Проверяем, что записалось
        cur.execute("SELECT balance FROM users WHERE id = ?", (user_id_to_update,))
        updated_user = cur.fetchone()

        print(f"📈 Новый баланс: {updated_user['balance']}")
        print("✅ Успешно сохранено в БД!")
    else:
        print(f"❌ Ошибка: Пользователь с ID {user_id_to_update} не найден в таблице users.")

    print("=" * 50)