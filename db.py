import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).with_name("bot.sqlite3")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                locale TEXT,
                balance REAL NOT NULL DEFAULT 0,
                ton_wallet TEXT,
                card_number TEXT,
                sbp_phone TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        # Миграция для уже созданной таблицы (старые инсталлы)
        for stmt in (
            "ALTER TABLE users ADD COLUMN locale TEXT",
            "ALTER TABLE users ADD COLUMN balance REAL NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN ton_wallet TEXT",
            "ALTER TABLE users ADD COLUMN card_number TEXT",
            "ALTER TABLE users ADD COLUMN sbp_phone TEXT",
        ):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_stats (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_deals INTEGER NOT NULL,
                success_deals INTEGER NOT NULL,
                total_volume_usd REAL NOT NULL,
                avg_rating REAL NOT NULL,
                online_now INTEGER NOT NULL
            )
            """
        )

        # Инициализация дефолтной статистики, если пусто
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM platform_stats")
        row = cur.fetchone()
        if not row or row["cnt"] == 0:
            conn.execute(
                """
                INSERT INTO platform_stats (
                    id, total_deals, success_deals, total_volume_usd, avg_rating, online_now
                )
                VALUES (1, ?, ?, ?, ?, ?)
                """,
                (1277, 871, 48126, 4.6, 14912),
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
            SELECT id, tg_id, balance, ton_wallet, card_number, sbp_phone
            FROM users
            WHERE tg_id = ?
            """,
            (tg_id,),
        ).fetchone()


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

