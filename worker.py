import asyncio
import json
import os

import aio_pika

from app.domain import ORDER_STAGES, advance_order
from app.messaging import ORDER_EVENTS_EXCHANGE, ORDER_QUEUE, declare_messaging, publish_status
from app.storage import get_order, initialize_database, save_order


DATABASE_PATH = os.getenv("DATABASE_PATH", "data/orders.db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
STAGE_DELAY = float(os.getenv("ORDER_STAGE_DELAY_SECONDS", "2"))


async def process_order(order_id: str, channel: aio_pika.abc.AbstractChannel) -> None:
    order = await asyncio.to_thread(get_order, DATABASE_PATH, order_id)
    if not order or order["status"] in {"completed", "failed"}:
        return

    try:
        next_stage = ORDER_STAGES.index(order["status"]) + 1
        for status in ORDER_STAGES[next_stage:]:
            if status == "completed":
                await asyncio.sleep(STAGE_DELAY)
            order = advance_order(order, status)
            await asyncio.to_thread(save_order, DATABASE_PATH, order)
            await publish_status(channel, order)
    except Exception:
        if order["status"] in {"pending", "processing"}:
            order = advance_order(order, "failed")
            await asyncio.to_thread(save_order, DATABASE_PATH, order)
            await publish_status(channel, order)
        raise


async def run_worker() -> None:
    initialize_database(DATABASE_PATH)
    connection = None
    for attempt in range(30):
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            break
        except Exception:
            if attempt == 29:
                raise
            await asyncio.sleep(1)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    await declare_messaging(channel)
    queue = await channel.get_queue(ORDER_QUEUE)
    print(f"Worker listening on {ORDER_QUEUE}; events use {ORDER_EVENTS_EXCHANGE}", flush=True)

    async with queue.iterator() as messages:
        async for message in messages:
            async with message.process(requeue=False):
                payload = json.loads(message.body)
                await process_order(payload["order_id"], channel)


if __name__ == "__main__":
    asyncio.run(run_worker())