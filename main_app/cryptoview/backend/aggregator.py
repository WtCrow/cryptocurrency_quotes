from pathlib import Path
import aio_pika
import asyncio
import json
import yaml

TYPE_TICKER = 'ticker'
TYPE_CANDLES = 'candles'
TYPE_CUP = 'cup'
TYPE_LISTING = 'listing_info'


class CryptoCurrencyAggregator:
    """Consume and send message to micro service crypto_currency"""

    ERR_SECOND_SUB = 'You already subscribed to this data'

    def __init__(self):
        # waiters get one message and move to subscribers tables (exception: listing_info)
        self.waiter_tables = dict()
        # get market data
        self.subscribers_table = dict()

        # rabbitMQ variables
        self.connection = None
        self.channel = None

        # read config
        path_to_config = Path(__file__).parents[1] / 'configs'
        with open(path_to_config / 'rabbit_mq_config.yaml', 'r') as f:
            config = yaml.safe_load(f)
            self.mq_connection_str = config['connection_str']
            self.name_queue_for_listing = config['queue_for_listing']
            self.name_queue_for_error = config['queue_for_error']
            self.exchanger = config['exchanger_name']
            self.queue_crypto_currency = config['crypto_currency_queue_name']

    async def run(self):
        """Function for start consume queue"""

        self.connection = await aio_pika.connect(self.mq_connection_str, loop=asyncio.get_event_loop())
        self.channel = await self.connection.channel()

        # connect to exchanger market data
        # market data send with routing key format: message_type.data_type.exchange.pair[.time_frame]
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
            """Function for consume market data"""

            body = json.loads(message.body.decode('utf-8'))
            
            # routing_key have view: message_type.data_type.exchange.pair[.time_frame]
            # First value mask *.*.*.# should have view 'update' or 'starting'
            message_type = message.routing_key.split('.')[0]
            
            # Next part mask this data_id, that defines data: data_type.exchange.pair[.time_frame]
            data_id = '.'.join(message.routing_key.split('.')[1:])

            if message_type == 'update':
                # If exist observers, get observers and send update data
                observers = self.subscribers_table.get(data_id, None)
                if observers:
                    for observer in observers:
                        asyncio.get_event_loop().create_task(observer.update(
                            dict(
                                data_id=message.routing_key,
                                data=body
                            )
                        ))
            elif message_type == 'starting':
                # if exist waiters, send data and move waiters in observers
                if not self.waiter_tables.get(data_id, None):
                    return

                new_subscribers = []
                while self.waiter_tables[data_id]:
                    observer = self.waiter_tables[data_id].pop()
                    asyncio.get_event_loop().create_task(observer.update(
                        dict(
                            data_id=message.routing_key,
                            data=body
                        )
                    ))
                    new_subscribers.append(observer)

                # init subscribers array if need
                subscribers = self.subscribers_table.get(data_id, None)
                if not subscribers and new_subscribers:
                    self.subscribers_table[data_id] = new_subscribers
                    asyncio.get_event_loop().create_task(self._send_message_for_subscribe(data_id))
                else:
                    for new_subscriber in new_subscribers:
                        if new_subscriber not in self.subscribers_table[data_id]:
                            self.subscribers_table[data_id].append(new_subscriber)

        def callback_crypto_currency_listing(message):
            """Function for consume information about access pairs, exchanges and timeframes"""

            body = json.loads(message.body.decode('utf-8'))
            data_id = TYPE_LISTING
            
            if not self.waiter_tables.get(data_id, None):
                return

            while self.waiter_tables[data_id]:
                observer = self.waiter_tables[data_id].pop()
                asyncio.get_event_loop().create_task(observer.update(
                    dict(
                        data_id=data_id,
                        data=body
                    )
                ))

        def callback_crypto_currency_error(message):
            """listing for consume message about error"""

            body = json.loads(message.body.decode('utf-8'))

            # validation
            error = body.get('error', '')
            if not error:
                return

            message = body.get('message', '')
            data_id = ''
            if message:
                data_id = message.get('data_id', '')
                if not data_id:
                    return
            else:
                return

            # send information to waiter (for example, subscribe to bad data)
            if data_id in self.waiter_tables.keys():
                for observer in self.waiter_tables[data_id]:
                    asyncio.get_event_loop().create_task(observer.update(
                        dict(
                            data_id=data_id,
                            error=error
                        )
                    ))

            if data_id in self.subscribers_table.keys():
                for observer in self.subscribers_table[data_id]:
                    asyncio.get_event_loop().create_task(observer.update(
                        dict(
                            data_id=data_id,
                            data=error
                        )
                    ))

        await queue_topic.consume(callback_crypto_currency_market_data)
        await queue_for_listing.consume(callback_crypto_currency_listing)
        await queue_for_error.consume(callback_crypto_currency_error)

    async def attach(self, observer, data_id):
        """Append observer in waiters and send message for get starting data"""

        # init table for waiters if need
        if data_id not in self.waiter_tables.keys():
            self.waiter_tables[data_id] = []

        # if user want get information, that user already wait, send error
        if observer not in self.waiter_tables[data_id]:
            self.waiter_tables[data_id].append(observer)
            # get starting data
            await self._send_message_for_get_starting_data(data_id)
        else:
            # send information about error
            asyncio.get_event_loop().create_task(observer.update(
                dict(
                    data_id=data_id,
                    error=CryptoCurrencyAggregator.ERR_SECOND_SUB
                )
            ))

    async def detach(self, observer, data_id=None):
        """Remove observer from specific data thread or from all data thread"""
        if data_id:
            # check subscribers
            subscribers = self.subscribers_table.get(data_id, None)
            if subscribers and observer in self.subscribers_table[data_id]:
                self.subscribers_table[data_id].remove(observer)

                # If all subscribers unsubscribe, than stop task in microservice
                if not self.subscribers_table[data_id]:
                    await self._send_message_for_unsubscribe(data_id)

            # check waiters
            if data_id in self.waiter_tables.keys() and observer in self.waiter_tables[data_id]:
                self.waiter_tables[data_id].remove(observer)

        else:  # if not data_id, delete from all data threads
            # check subscribers
            keys = list(self.subscribers_table.keys())
            for key in keys:
                if observer in self.subscribers_table[key]:
                    self.subscribers_table[key].remove(observer)

                    # If all subscribers unsubscribe, than stop task in microservice
                    if not self.subscribers_table[key]:
                        await self._send_message_for_unsubscribe(key)

            # check waiters
            keys = list(self.waiter_tables.keys())
            for key in keys:
                if observer in self.waiter_tables[key]:
                    self.waiter_tables[key].remove(observer)

    async def _send_message_for_unsubscribe(self, data_id):
        """Send message to microservice for stop task"""
        body = json.dumps(
            dict(
                action='unsub',
                data_id=data_id
            )
        ).encode('utf-8')
        await self._send_message_in_queue(self.queue_crypto_currency, body)

    async def _send_message_for_subscribe(self, data_id):
        """Send message to microservice for start task"""
        body = json.dumps(
            dict(
                action='sub',
                data_id=data_id
            )
        ).encode('utf-8')
        await self._send_message_in_queue(self.queue_crypto_currency, body)

    async def _send_message_for_get_starting_data(self, data_id):
        """Send message to microservice for get starting data"""
        body = json.dumps(
            dict(
                action='get_starting',
                data_id=data_id
            )
        ).encode('utf-8')
        await self._send_message_in_queue(self.queue_crypto_currency, body)

    async def _send_message_in_queue(self, queue_name, body, reply_to=None):
        """Method for send message to microservice queue"""
        message = aio_pika.Message(body=body, reply_to=reply_to)
        await self.channel.default_exchange.publish(message, routing_key=queue_name)
