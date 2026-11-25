import json
import sqlite3
from contextlib import closing
from pathlib import Path


def initialize_database(database_path: str) -> None:
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS orders_created_at ON orders(created_at DESC)"
        )


def save_order(database_path: str, order: dict) -> None:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(
            """INSERT INTO orders (id, created_at, status, payload)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   status = excluded.status,
                   payload = excluded.payload""",
            (order["id"], order["created_at"], order["status"], json.dumps(order, ensure_ascii=False)),
        )


def get_order(database_path: str, order_id: str) -> dict | None:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        row = connection.execute(
            "SELECT payload FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
    return json.loads(row[0]) if row else None


def list_orders(database_path: str, search: str = "", status: str = "") -> list[dict]:
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT payload FROM orders ORDER BY created_at DESC"
        ).fetchall()

    normalized_search = search.strip().lower()
    normalized_status = status.strip().lower()
    orders = [json.loads(row[0]) for row in rows]

    if normalized_status:
        orders = [order for order in orders if order.get("status") == normalized_status]

    if normalized_search:
        filtered = []
        for order in orders:
            searchable = " ".join([
                str(order.get("id", "")),
                str(order.get("customer_name", "")),
                str(order.get("customer_email", "")),
            ]).lower()
            if normalized_search in searchable:
                filtered.append(order)
        orders = filtered

    return orders