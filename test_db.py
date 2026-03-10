import sqlite3
from pathlib import Path

db_path = Path(__file__).with_name("bot.sqlite3")

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 120)
    print("📊 ТАБЛИЦА DEALS")
    print("=" * 120)

    cur.execute("SELECT * FROM deals ORDER BY created_at DESC")
    rows = cur.fetchall()

    if not rows:
        print("⚠️ Таблица пуста")
    else:
        print(
            f"{'ID':<5} {'User':<12} {'Method':<10} {'Amount':<12} {'Curr':<6} {'Status':<12} {'Item':<40} {'Created':<25}")
        print("-" * 120)

        for row in rows:
            item = (row["item_description"] or "N/A")[:37] + "..." if len(row["item_description"] or "") > 40 else (
                        row["item_description"] or "N/A")
            print(
                f"{row['id']:<5} {row['user_id']:<12} {row['payment_method']:<10} {row['amount']:<12.2f} {row['currency']:<6} {row['status']:<12} {item:<40} {row['created_at']:<25}")

    print("=" * 120)
    print(f"Всего сделок: {len(rows)}")

    # Статистика по статусам
    print("\n📈 Статистика по статусам:")
    cur.execute("SELECT status, COUNT(*) as count, SUM(amount) as total FROM deals GROUP BY status")
    for row in cur.fetchall():
        print(
            f"  {row['status']:<12} → {row['count']} сделок на сумму {row['total']:.2f} {row['currency'] if row['currency'] else ''}")

    # Таблица USERS для сверки
    print("\n" + "=" * 120)
    print("👤 ТАБЛИЦА USERS")
    print("=" * 120)

    cur.execute("SELECT id, tg_id, username, balance, total_deals, success_deals FROM users")
    rows = cur.fetchall()

    print(f"{'ID':<5} {'TG_ID':<15} {'Username':<20} {'Balance':<12} {'Deals':<10} {'Success':<10}")
    print("-" * 120)

    for row in rows:
        print(
            f"{row['id']:<5} {row['tg_id']:<15} {row['username'] or 'N/A':<20} {row['balance']:<12.2f} {row['total_deals']:<10} {row['success_deals']:<10}")

    print("=" * 120)