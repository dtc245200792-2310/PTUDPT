import tempfile
import unittest
from pathlib import Path

from app.domain import advance_order
from app.storage import get_order, initialize_database, list_orders, save_order


class OrderStorageTests(unittest.TestCase):
    def test_saves_and_updates_order(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = str(Path(directory) / "orders.db")
            initialize_database(database_path)
            order = {
                "id": "DH-TEST",
                "status": "pending",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "timeline": [{"status": "pending", "at": "2026-01-01T00:00:00+00:00"}],
            }
            save_order(database_path, order)

            advance_order(order, "processing")
            save_order(database_path, order)

            self.assertEqual(get_order(database_path, "DH-TEST")["status"], "processing")
            self.assertEqual([item["id"] for item in list_orders(database_path)], ["DH-TEST"])

    def test_filters_orders_by_status_and_search(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = str(Path(directory) / "orders.db")
            initialize_database(database_path)
            for order_id, name, email, status in (
                ("DH-MOT", "Nguyễn An", "an@example.com", "pending"),
                ("DH-HAI", "Trần Bình", "binh@example.com", "completed"),
            ):
                save_order(database_path, {
                    "id": order_id,
                    "customer_name": name,
                    "customer_email": email,
                    "status": status,
                    "created_at": "2026-01-01T00:00:00+00:00",
                })

            self.assertEqual([item["id"] for item in list_orders(database_path, status="completed")], ["DH-HAI"])
            self.assertEqual([item["id"] for item in list_orders(database_path, search="nguyễn")], ["DH-MOT"])
            self.assertEqual(list_orders(database_path, search="khong-ton-tai"), [])


if __name__ == "__main__":
    unittest.main()