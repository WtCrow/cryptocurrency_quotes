import aio_pika
import asyncio
import json

"""
export RABBIT_MQ_STR_CONN=amqp://guest:guest@172.17.0.2:5672/
export ROUTING_KEY_LISTING=crypto_currency_ms_listing
export ERROR_QUEUE=crypto_currency_ms_err
export QUEUE_THIS_SERVICE=crypto_currency_ms
export EXCHANGER=topic

RABBIT_MQ_STR_CONN=amqp://guest:guest@172.17.0.2:5672/
ROUTING_KEY_LISTING=crypto_currency_ms_listing
ERROR_QUEUE=crypto_currency_ms_err
QUEUE_THIS_SERVICE=crypto_currency_ms
EXCHANGER=topic
"""

connection_str = 'amqp://guest:guest@172.17.0.2:5672/'
exchanger = 'topic'
ms_queue = 'crypto_currency_ms'


async def send_message(data):
    """Send message to queue_name"""
    conn = await aio_pika.connect(connection_str, loop=asyncio.get_event_loop())
    async with await conn.channel() as chn:
        message = aio_pika.Message(data.encode())
        await chn.default_exchange.publish(message, routing_key=ms_queue)
    await conn.close()

connection = None
channel = None


async def consume():
    global connection, channel
    connection = await aio_pika.connect(connection_str, loop=asyncio.get_event_loop())
    channel = await connection.channel()

    binding_mask = '*.*.*.#'
    topic_logs_exchange = await channel.declare_exchange(exchanger, aio_pika.ExchangeType.TOPIC)
    queue_topic = await channel.declare_queue('', auto_delete=True)
    queue_error = await channel.declare_queue('error', auto_delete=True)
    queue_listing = await channel.declare_queue('error', auto_delete=True)
    await queue_topic.bind(topic_logs_exchange, routing_key=binding_mask)
    await queue_error.bind(topic_logs_exchange, routing_key='crypto_currency_ms_err')
    await queue_listing.bind(topic_logs_exchange, routing_key='crypto_currency_ms_listing')

    def callback(message):
        print(message.body)

    await queue_topic.consume(callback)
    await queue_error.consume(callback)
    await queue_listing.consume(callback)


async def main():
    await consume()

    test_action, test_data_id = 'sub', 'candles.Binance.BTCUSDT.H1'

    message = json.dumps(
        dict(
            action=test_action,
            data_id=test_data_id
        )
    )
    await send_message(message)

    if test_action == 'sub':
        await asyncio.sleep(3)
        message = json.dumps(
            dict(
                action='unsub',
                data_id=test_data_id
            )
        )
        await send_message(message)


asyncio.get_event_loop().create_task(main())
asyncio.get_event_loop().run_forever()
