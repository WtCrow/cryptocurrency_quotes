import aio_pika
import asyncio
import json

connection_str = 'amqp://guest:guest@127.0.0.1/'
exchanger = 'topic_logs'
ms_queue = 'crypto_currency_ms'


async def send_message(data):
    """
    Отправляет сообщение data  в очередь queue_name
    """
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
    queue_listing = await channel.declare_queue('listing_info')
    await queue_topic.bind(topic_logs_exchange, routing_key=binding_mask)

    def callback(message):
        print(message.body)

    await queue_listing.consume(callback)
    await queue_topic.consume(callback)
    print('Start consuming queue "{0}"...'.format('*.*.*.#'))


async def main():
    await consume()
    # write message for MS
    message = json.dumps(
        dict(
            action='sub',
            data_id='ticker.Binance.BTCUSDT'
        )
    )
    await send_message(message)

asyncio.get_event_loop().create_task(main())
asyncio.get_event_loop().run_forever()
