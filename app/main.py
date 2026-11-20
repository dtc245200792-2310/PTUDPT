import os
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

import aio_pika
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.domain import advance_order, calculate_total, utc_now
from app.messaging import declare_messaging, publish_order
from app.storage import (
    get_order as read_order,
    initialize_database,
    list_orders as read_orders,
    save_order,
)


DATABASE_PATH = os.getenv("DATABASE_PATH", "data/orders.db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database(DATABASE_PATH)
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await declare_messaging(channel)
    app.state.rabbit_channel = channel
    yield
    await connection.close()


app = FastAPI(title="Mạch Đơn", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class OrderItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=999)
    unit_price: float = Field(ge=0, le=1_000_000_000)


class OrderRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    customer_email: str = Field(min_length=3, max_length=254)
    items: Annotated[list[OrderItem], Field(min_length=1, max_length=20)]


@app.get("/")
async def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/orders", status_code=201)
async def create_order(payload: OrderRequest, request: Request):
    now = utc_now()
    items = [item.model_dump() for item in payload.items]
    order = {
        "id": f"DH-{uuid4().hex[:8].upper()}",
        "customer_name": payload.customer_name.strip(),
        "customer_email": payload.customer_email.strip(),
        "items": items,
        "total": calculate_total(items),
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "timeline": [{"status": "pending", "at": now}],
    }
    await run_in_threadpool(save_order, DATABASE_PATH, order)
    try:
        await publish_order(request.app.state.rabbit_channel, order)
    except Exception as error:
        order = advance_order(order, "failed")
        await run_in_threadpool(save_order, DATABASE_PATH, order)
        raise HTTPException(status_code=503, detail="Không thể đưa đơn vào hàng đợi") from error
    return order


@app.get("/orders")
async def list_orders():
    return await run_in_threadpool(read_orders, DATABASE_PATH)


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = await run_in_threadpool(read_order, DATABASE_PATH, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    return order
