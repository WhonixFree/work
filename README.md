# p2p_bot (guarant)

Минимальный Telegram-бот на Python для гаранта.

## Запуск

1) Создай виртуальное окружение и поставь зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Укажи токен бота:

- Скопируй `.env.example` в `.env` и вставь токен, или просто экспортируй переменную:

```bash
export BOT_TOKEN="123456:ABCDEF..."
```

3) Запусти:

```bash
python main.py
```

## Что уже есть

- `/start`: создаёт пользователя в SQLite (`bot.sqlite3`) и показывает главное меню кнопками:
  - Профиль
  - Создать сделку
  - Реквизиты
  - Подробнее
  - Язык
  - Поддержка

