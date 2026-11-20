import unittest

from app.domain import advance_order, calculate_total


class OrderDomainTests(unittest.TestCase):
    def test_calculates_total_for_multiple_items(self):
        items = [
            {"quantity": 2, "unit_price": 12500},
            {"quantity": 1, "unit_price": 9900},
        ]
        self.assertEqual(calculate_total(items), 34900)

    def test_advancing_order_records_timestamped_timeline_entry(self):
        order = {"status": "pending", "timeline": [{"status": "pending", "at": "earlier"}]}
        updated = advance_order(order, "processing")
        self.assertEqual(updated["status"], "processing")
        self.assertEqual(updated["updated_at"], updated["timeline"][-1]["at"])
        self.assertEqual(updated["timeline"][-1]["status"], "processing")

    def test_rejects_skipping_required_status(self):
        with self.assertRaises(ValueError):
            advance_order({"status": "pending", "timeline": []}, "completed")

    def test_failed_is_terminal(self):
        order = {"status": "processing", "timeline": []}
        advance_order(order, "failed")
        with self.assertRaises(ValueError):
            advance_order(order, "completed")


if __name__ == "__main__":
    unittest.main()