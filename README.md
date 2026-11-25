# Mạch Đơn

Ứng dụng xử lý đơn hàng theo kiến trúc tối thiểu: FastAPI lưu dữ liệu vào SQLite và gửi tác vụ đến RabbitMQ; worker cập nhật trạng thái; notification service nhận sự kiện từ RabbitMQ và broadcast tới client bằng SignalR.

## Chạy hệ thống

Cần Docker Desktop và Docker Compose.

Khởi động nhanh bằng lệnh Windows:

```bat
start.bat
```

Hoặc chạy bằng Compose:

```bash
docker compose up -d --no-build --wait
```

Chỉ dùng `--build` khi thay đổi mã nguồn hoặc Dockerfile:

```bash
docker compose up --build -d --wait
```

Mở [http://localhost:8000](http://localhost:8000). SignalR hub chạy tại `http://localhost:8001/notifications`; RabbitMQ Management chạy tại [http://localhost:15672](http://localhost:15672) (tài khoản mẫu `orderapp` / `orderapp-dev`). SQLite được giữ trong volume `order-data`. Dừng bằng `Ctrl+C`; dùng `docker compose down` để gỡ container.

## Luồng xử lý

1. Client tạo đơn qua API; API lưu đơn trạng thái `pending` vào SQLite và gửi `order_id` vào RabbitMQ.
2. Worker đọc hàng đợi, cập nhật `pending → processing → completed` hoặc `failed`, lưu mỗi thay đổi vào SQLite và phát sự kiện `order.updated`.
3. Notification service nhận sự kiện RabbitMQ và gửi `OrderUpdated` tới các client đang kết nối SignalR.

## API

- `POST /orders`: tạo đơn hàng và đưa vào hàng đợi.
- `GET /orders`: lấy danh sách đơn hàng.
- `GET /orders/{id}`: lấy chi tiết và timeline của đơn.

Tài liệu OpenAPI có tại `/docs`.

## Kiểm thử

```bash
python -m unittest discover -s tests
```

Độ trễ trước trạng thái hoàn tất mặc định là 2 giây; chỉnh bằng `ORDER_STAGE_DELAY_SECONDS` trên worker.