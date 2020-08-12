import aio_pika
import logging
import asyncio
import json
import os

TYPE_TICKER = 'ticker'
TYPE_CANDLES = 'candles'
TYPE_CUP = 'cup'
TYPE_LISTING = 'listing_info'

logger = logging.getLogger('cryptocurrency_error_log')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class CryptoCurrencyAggregator:
    """Consume and send message to micro service crypto_currency"""

    ERR_SECOND_SUB = 'You already subscribed to this data'

    def __init__(self):
        # ws, that wait first data
        self.waiters_first_msg = dict()
        # after getting message, ws move to subscribers and will getting update data
        self.subscribers = dict()

        # rabbitMQ variables
        self.connection = None
        self.channel = None

        self.mq_connection_str = os.environ.get('RABBIT_MQ_STR_CONN')
        self.queue_crypto_quotes_service = os.environ.get('QUEUE_SERVICE_CRYPTO_QUOTES')
        self.exchanger = os.environ.get('EXCHANGER')
        self.name_queue_for_error = os.environ.get('ERROR_QUEUE')
        self.name_queue_for_listing = os.environ.get('ROUTING_KEY_LISTING')

    async def run(self):
        """Function for start consume queue"""

        self.connection = await aio_pika.connect(self.mq_connection_str, loop=asyncio.get_event_loop())
        self.channel = await self.connection.channel()

        # connect to exchanger market data
        # market data send with routing key format: message_type.data_type.exchange.pair[.time_frame]
        # message_type == update | starting, data_type == ticker | candles | depth,
        # exchange, pair, time_frame - sending by listing_info
        binding_mask = '*.*.*.#'
        topic_logs_exchange = await self.channel.declare_exchange(self.exchanger, aio_pika.ExchangeType.TOPIC)
        queue_topic = await self.channel.declare_queue('', auto_delete=True)
        await queue_topic.bind(topic_logs_exchange, routing_key=binding_mask)

        # listener queue for listing information
        queue_for_listing = await self.channel.declare_queue('', auto_delete=True)
        await queue_for_listing.bind(topic_logs_exchange, routing_key=self.name_queue_for_listing)

        # listener queue for error
        queue_for_error = await self.channel.declare_queue('', auto_delete=True)
        await queue_for_error.bind(topic_logs_exchange, routing_key=self.name_queue_for_error)

        def callback_crypto_currency_market_data(message):
            """Callback for consume market data"""
            body = json.loads(message.body.decode('utf-8'))
            
            # routing_key have view: message_type.data_type.exchange.pair[.time_frame]
            # message_type == update | starting, data_type == ticker | candles | depth,
            # exchange, pair, time_frame - sending by listing_info
            # mask: *.*.*.#
            message_type = message.routing_key.split('.')[0]
            data_id = '.'.join(message.routing_key.split('.')[1:])

            if message_type == 'update':
                for observer in self.subscribers.get(data_id):
                    asyncio.get_event_loop().create_task(observer.update(
                        dict(
                            data_id=message.routing_key,
                            data=body
                        )
                    ))
            elif message_type == 'starting':
                # if exist waiters, send data and move waiters in subscribers
                if not self.waiters_first_msg.get(data_id):
                    return

                new_subscribers = []
                while self.waiters_first_msg[data_id]:
                    observer = self.waiters_first_msg[data_id].pop()
                    asyncio.get_event_loop().create_task(observer.update(
                        dict(
                            data_id=message.routing_key,
                            data=body
                        )
                    ))
                    new_subscribers.append(observer)

                # if not subscribers on this data_id, init new dict-value, else append to exist array
                subscribers = self.subscribers.get(data_id, None)
                if not subscribers and new_subscribers:
                    self.subscribers[data_id] = new_subscribers
                    asyncio.get_event_loop().create_task(self._send_message_for_subscribe(data_id))
                else:
                    for new_subscriber in new_subscribers:
                        if new_subscriber not in self.subscribers[data_id]:
                            self.subscribers[data_id].append(new_subscriber)

        def callback_crypto_currency_listing(message):
            """Callback for consume information about access pairs, exchanges and timeframes"""
            body = json.loads(message.body.decode('utf-8'))
            data_id = TYPE_LISTING

            if not self.waiters_first_msg.get(data_id):
                return

            while self.waiters_first_msg[data_id]:
                observer = self.waiters_first_msg[data_id].pop()
                asyncio.get_event_loop().create_task(observer.update(
                    dict(
                        data_id=data_id,
                        data=body
                    )
                ))

        def callback_crypto_currency_error(message):
            """Callback for consume error queue"""
            logger.error(message.body.decode('utf-8'))

            body = json.loads(message.body.decode('utf-8'))

            # validation
            error_place = body.get('error_place')
            message = 'Sorry! Error on server'
            if not message or not error_place:
                return

            # send information to ws, that wait or subscribe on error_place
            waiters = self.waiters_first_msg.get(error_place, ())
            for observer in waiters:
                asyncio.get_event_loop().create_task(observer.update(
                    dict(
                        data_id=error_place,
                        error=message
                    )
                ))

            subscribers = self.subscribers.get(error_place, ())
            for observer in subscribers:
                asyncio.get_event_loop().create_task(observer.update(
                    dict(
                        data_id=error_place,
                        data=message
                    )
                ))

        await queue_topic.consume(callback_crypto_currency_market_data)
        await queue_for_listing.consume(callback_crypto_currency_listing)
        await queue_for_error.consume(callback_crypto_currency_error)

    async def attach(self, observer, data_id):
        """Append observer in waiters and send message for get starting data"""
        # init table for waiters if need
        self.waiters_first_msg.setdefault(data_id, [])

        # if user want get information, that user already wait (in subscribers), send error
        if observer in self.waiters_first_msg[data_id]:
            asyncio.get_event_loop().create_task(observer.update(
                dict(
                    data_id=data_id,
                    error=CryptoCurrencyAggregator.ERR_SECOND_SUB
                )
            ))

        self.waiters_first_msg[data_id].append(observer)
        await self._send_message_for_get_starting_data(data_id)

    async def detach(self, observer, data_id=None):
        """Remove observer from specific data thread or from all data thread"""
        if data_id:
            if self.subscribers.get(data_id) and observer in self.subscribers[data_id]:
                self.subscribers[data_id].remove(observer)

                # If all subscribers unsubscribe, than stop task in microservice
                if not self.subscribers[data_id]:
                    await self._send_message_for_unsubscribe(data_id)

            # check waiters
            if self.waiters_first_msg.get(data_id) and observer in self.waiters_first_msg[data_id]:
                self.waiters_first_msg[data_id].remove(observer)

        else:  # if not data_id, delete from all data threads
            # check subscribers
            keys = list(self.subscribers.keys())
            for key in keys:
                if observer in self.subscribers.get(key, []):
                    self.subscribers[key].remove(observer)

                    # If all subscribers unsubscribe, than stop task in microservice
                    if not self.subscribers[key]:
                        await self._send_message_for_unsubscribe(key)

            # check waiters
            keys = list(self.waiters_first_msg.keys())
            for key in keys:
                if observer in self.waiters_first_msg[key]:
                    self.waiters_first_msg[key].remove(observer)

    async def _send_message_for_unsubscribe(self, data_id):
        """Send message to microservice for stop task"""
        body = json.dumps(
            dict(
                action='unsub',
                data_id=data_id
            )
        ).encode('utf-8')
        await self._send_message_in_queue(self.queue_crypto_quotes_service, body)

    async def _send_message_for_subscribe(self, data_id):
        """Send message to microservice for start task"""
        body = json.dumps(
            dict(
                action='sub',
                data_id=data_id
            )
        ).encode('utf-8')
        await self._send_message_in_queue(self.queue_crypto_quotes_service, body)

    async def _send_message_for_get_starting_data(self, data_id):
        """Send message to microservice for get starting data"""
        body = json.dumps(
            dict(
                action='get_starting',
                data_id=data_id
            )
        ).encode('utf-8')
        await self._send_message_in_queue(self.queue_crypto_quotes_service, body)

    async def _send_message_in_queue(self, queue_name, body, reply_to=None):
        """Method for send some message to microservice queue"""
        message = aio_pika.Message(body=body, reply_to=reply_to)
        await self.channel.default_exchange.publish(message, routing_key=queue_name)
