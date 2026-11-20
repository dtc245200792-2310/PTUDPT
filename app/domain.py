from datetime import datetime, timezone


ORDER_STAGES = ("pending", "processing", "completed")
ORDER_STATUSES = (*ORDER_STAGES, "failed")
STATUS_LABELS = {
    "pending": "Đang chờ",
    "processing": "Đang xử lý",
    "completed": "Hoàn thành",
    "failed": "Thất bại",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def calculate_total(items: list[dict]) -> float:
    return round(sum(item["quantity"] * item["unit_price"] for item in items), 2)


def advance_order(order: dict, status: str) -> dict:
    if status not in ORDER_STATUSES:
        raise ValueError(f"Trạng thái không hợp lệ: {status}")
    current = order["status"]
    transitions = {
        "pending": {"processing", "failed"},
        "processing": {"completed", "failed"},
        "completed": set(),
        "failed": set(),
    }
    if status not in transitions[current]:
        raise ValueError(f"Không thể chuyển từ {current} sang {status}")
    order["status"] = status
    order["updated_at"] = utc_now()
    order["timeline"].append({"status": status, "at": order["updated_at"]})
    return order