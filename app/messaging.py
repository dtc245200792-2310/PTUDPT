import json

import aio_pika


ORDER_QUEUE = "orders"
NOTIFICATION_QUEUE = "notifications"
ORDER_EVENTS_EXCHANGE = "order.events"


async def declare_messaging(channel: aio_pika.abc.AbstractChannel) -> None:
    await channel.declare_queue(ORDER_QUEUE, durable=True)
    await channel.declare_exchange(
        ORDER_EVENTS_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
    )
    notifications = await channel.declare_queue(NOTIFICATION_QUEUE, durable=True)
    await notifications.bind(ORDER_EVENTS_EXCHANGE, routing_key="order.updated")


async def publish_order(channel: aio_pika.abc.AbstractChannel, order: dict) -> None:
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps({"order_id": order["id"]}).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=ORDER_QUEUE,
    )


async def publish_status(channel: aio_pika.abc.AbstractChannel, order: dict) -> None:
    exchange = await channel.get_exchange(ORDER_EVENTS_EXCHANGE)
    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(order, ensure_ascii=False).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key="order.updated",
    )