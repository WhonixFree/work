import sqlite3
import secrets
import string
from pathlib import Path


DB_PATH = Path(__file__).with_name("bot.sqlite3")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with _connect() as conn:
        # === Таблица users ===
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                first_name TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                locale TEXT,
                balance REAL NOT NULL DEFAULT 0,
                ton_wallet TEXT,
                card_number TEXT,
                sbp_phone TEXT,
                total_deals INTEGER NOT NULL DEFAULT 0,
                success_deals INTEGER NOT NULL DEFAULT 0,
                total_volume_usd REAL NOT NULL DEFAULT 0,
                avg_rating REAL NOT NULL DEFAULT 0,
                online_now INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # Миграции для users — добавляем колонки, если их нет
        for stmt in (
            "ALTER TABLE users ADD COLUMN locale TEXT",
            "ALTER TABLE users ADD COLUMN balance REAL NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN ton_wallet TEXT",
            "ALTER TABLE users ADD COLUMN card_number TEXT",
            "ALTER TABLE users ADD COLUMN sbp_phone TEXT",
            "ALTER TABLE users ADD COLUMN total_deals INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN success_deals INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN total_volume_usd REAL NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN avg_rating REAL NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN online_now INTEGER NOT NULL DEFAULT 0",
        ):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Колонка уже существует

        # === Таблица deals (исправлено: одна таблица, все нужные колонки) ===
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT UNIQUE,
                user_id INTEGER NOT NULL,
                buyer_id INTEGER,
                payment_method TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                item_description TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(tg_id)
            )
            """
        )

        # Миграции для deals — добавляем новые колонки в существующие инсталляции
        for stmt in (
            "ALTER TABLE deals ADD COLUMN public_id TEXT",
            "ALTER TABLE deals ADD COLUMN buyer_id INTEGER",
            "ALTER TABLE deals ADD COLUMN item_description TEXT",
            "ALTER TABLE deals ADD COLUMN updated_at TEXT",
        ):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Колонка уже существует

        # === Таблица platform_stats ===
        conn.execute("DROP TABLE IF EXISTS platform_stats")
        conn.execute(
            """
            CREATE TABLE platform_stats (
                id INTEGER PRIMARY KEY,
                total_deals INTEGER NOT NULL DEFAULT 0,
                success_deals INTEGER NOT NULL DEFAULT 0,
                total_volume_usd REAL NOT NULL DEFAULT 0,
                avg_rating REAL NOT NULL DEFAULT 0,
                online_now INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        # Вычисляем агрегаты по users
        cur = conn.execute(
            """
            SELECT
                SUM(total_deals) AS total_deals,
                SUM(success_deals) AS success_deals,
                SUM(total_volume_usd) AS total_volume_usd,
                AVG(NULLIF(avg_rating, 0)) AS avg_rating_avg,
                SUM(online_now) AS online_now
            FROM users
            """
        )
        row = cur.fetchone()

        total_deals = int(row[0] or 0)
        success_deals = int(row[1] or 0)
        total_volume_usd = float(row[2] or 0.0)
        avg_rating = float(row[3] or 0.0)
        online_now = int(row[4] or 0)

        # Вставляем агрегированную строку (UPSERT для безопасности)
        conn.execute(
            """
            INSERT INTO platform_stats (id, total_deals, success_deals, total_volume_usd, avg_rating, online_now)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                total_deals = excluded.total_deals,
                success_deals = excluded.success_deals,
                total_volume_usd = excluded.total_volume_usd,
                avg_rating = excluded.avg_rating,
                online_now = excluded.online_now
            """,
            (1, total_deals, success_deals, total_volume_usd, avg_rating, online_now),
        )

        conn.commit()

def upsert_user(
    *,
    tg_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language_code: str | None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (tg_id, username, first_name, last_name, language_code)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                language_code=excluded.language_code
            """,
            (tg_id, username, first_name, last_name, language_code),
        )
        conn.commit()


def get_user_locale(tg_id: int) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT locale FROM users WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        if not row:
            return None
        return row["locale"]


def set_user_locale(tg_id: int, locale: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET locale = ? WHERE tg_id = ?",
            (locale, tg_id),
        )
        conn.commit()


def get_user_profile(tg_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE tg_id = ?
            """,
            (tg_id,),
        ).fetchone()


def credit_user_balance(tg_id: int, amount: float) -> float | None:
    """
    Увеличивает баланс пользователя на amount.
    Возвращает новый баланс или None, если пользователь не найден.
    """
    if amount <= 0:
        raise ValueError("amount must be positive")
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE tg_id = ?
            """,
            (amount, tg_id),
        )
        if cursor.rowcount <= 0:
            return None
        row = conn.execute(
            "SELECT balance FROM users WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        conn.commit()
        return float(row["balance"]) if row else None


def debit_user_balance(tg_id: int, amount: float) -> float | None:
    """
    Atomically subtracts amount from user balance if sufficient.
    Returns new balance on success, or None if insufficient funds / user not found.
    """
    if amount <= 0:
        raise ValueError("amount must be positive")
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE users
            SET balance = balance - ?
            WHERE tg_id = ? AND balance >= ?
            """,
            (amount, tg_id, amount),
        )
        if cursor.rowcount <= 0:
            return None
        row = conn.execute(
            "SELECT balance FROM users WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        conn.commit()
        return float(row["balance"]) if row else None


def set_user_ton_wallet(tg_id: int, ton_wallet: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET ton_wallet = ? WHERE tg_id = ?",
            (ton_wallet, tg_id),
        )
        conn.commit()


def set_user_card_number(tg_id: int, card_number: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET card_number = ? WHERE tg_id = ?",
            (card_number, tg_id),
        )
        conn.commit()


def set_user_sbp_phone(tg_id: int, sbp_phone: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET sbp_phone = ? WHERE tg_id = ?",
            (sbp_phone, tg_id),
        )
        conn.commit()


def get_platform_stats() -> sqlite3.Row:
    with _connect() as conn:
        row = conn.execute(
            "SELECT total_deals, success_deals, total_volume_usd, avg_rating, online_now FROM platform_stats WHERE id = 1"
        ).fetchone()
        return row

_ALPHABET = string.ascii_lowercase + string.digits


def _gen_public_id(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def create_deal(tg_id: int, payment_method: str, amount: float, currency: str, item_description: str) -> tuple[int, str]:
    with _connect() as conn:
        public_id = _gen_public_id()
        for _ in range(10):
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO deals (public_id, user_id, payment_method, amount, currency, item_description, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                    """,
                    (public_id, tg_id, payment_method, amount, currency, item_description),
                )
                conn.commit()
                return cursor.lastrowid, public_id
            except sqlite3.IntegrityError:
                public_id = _gen_public_id()
        raise RuntimeError("Не удалось сгенерировать уникальный public_id для сделки")

def get_deal(deal_id: int, tg_id: int | None = None) -> sqlite3.Row | None:
    with _connect() as conn:
        if tg_id:
            return conn.execute(
                "SELECT * FROM deals WHERE id = ? AND user_id = ?",
                (deal_id, tg_id),
            ).fetchone()
        else:
            return conn.execute(
                "SELECT * FROM deals WHERE id = ?",
                (deal_id,),
            ).fetchone()


def get_deal_by_public_id(public_id: str) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM deals WHERE public_id = ?",
            (public_id,),
        ).fetchone()


def attach_buyer_to_deal(public_id: str, buyer_tg_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE deals
            SET buyer_id = COALESCE(buyer_id, ?), updated_at = CURRENT_TIMESTAMP
            WHERE public_id = ?
            """,
            (buyer_tg_id, public_id),
        )
        conn.commit()
        return cursor.rowcount > 0

def update_deal_status(deal_id: int, status: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE deals SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, deal_id),
        )
        conn.commit()
        return cursor.rowcount > 0

def update_user_stats(tg_id: int, deal_id: int) -> None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT amount, currency FROM deals 
            WHERE id = ? AND user_id = ?
            """,
            (deal_id, tg_id),
        ).fetchone()

        if not row:
            raise ValueError(f"Сделка #{deal_id} не найдена для пользователя {tg_id}")

        amount = float(row["amount"])
        currency = row["currency"]

        EXCHANGE_RATES = {
            "TON": 2.50,  # 1 TON = 2.50 USD
            "RUB": 0.011,  # 1 RUB = 0.011 USD (~90 RUB = 1 USD)
        }

        rate = EXCHANGE_RATES.get(currency, 0.011)
        amount_usd = amount * rate

        conn.execute(
            """
            UPDATE users 
            SET total_deals = total_deals + 1,
                total_volume_usd = total_volume_usd + ?
            WHERE tg_id = ?
            """,
            (amount_usd, tg_id),
        )

        conn.commit()
