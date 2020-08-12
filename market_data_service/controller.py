from exchanges.exchange_factory import ExchangeFactory
import aio_pika
import asyncio
import json
import os

DATA_TYPE_CANDLES = 'candles'
DATA_TYPE_DEPTH = 'depth'
DATA_TYPE_TICKER = 'ticker'
DATA_TYPE_LISTING = 'listing_info'


class Controller:
    """Main controller microservice. Consume RabbitMQ and respond on messages

    API doc:

    REQUEST:
    For use this microservice, you're need send JSON-message in queue QUEUE_THIS_SERVICE (env variable)

    JSON-message format:
        {
            action: <sub | unsub | get_starting>,
            data_id: <listing_info | data_type.exchange.pair[.time_frame]>
        }

    action:
        sub - start collecting market data task
        unsub - stop collecting market data task
        get_starting - if requested candlestick, be send several old candles, if requested depth or ticker be send
          current value
    data_id:
        listing_info - get information about exchanges, pairs and timeframes access
        Send only if 'action' == 'get_starting'

        About parts data_type.exchange.pair[.time_frame]:
            data_type:
                ticker - bid and ask prices
                candles - OHLCV candles
                depth - market depth
            exchange: some exchange from list, that send by 'data_id' == 'listing_info'
            pair: some cryptocurrency pair from list, that send by 'data_id' == 'listing_info'
            time_frame: timeframe candles for selected pairs. Using if 'data_type' == 'candles'

    RESPONSE:
    If requested listing_info, message be send in ROUTING_KEY_LISTING (env vars) queue
    If requested market, message be send in EXCHANGER rabbitmq exchange with specific routing_key,
        that equ (update | starting) + data_id from request message. Update - new value (action == 'sub'),
        starting - starting_data
    If request content bad information or exchange connector generate error, message be send in ERROR_QUEUE

    All message send in JSON
    Market data format is described at BaseExchange in module exchanges/abstract_exchange.py
    Error contain fields 'error_roting_key' and 'exception'
        error_place - data_id, that generate error or bad message ('unknown' if not data_id key)
        message - error message

    """

    # error messages
    ERR_BAD_DATA_TYPE = "Invalid 'data_type' value"
    ERR_BAD_EXCHANGE = "Invalid 'exchange' value"
    ERR_BAD_PAIR = "Invalid 'pair' value"
    ERR_BAD_TIME_FRAME = "Invalid 'time_frame' value"
    ERR_BAD_LISTING_MESSAGE = "Listing information only with 'action' == 'get_starting' requested"
    ERR_BAD_ACTION = "Invalid 'action' value"
    ERR_NOT_JSON = "Message isn't JSON"

    ACTION_TYPE_SUB = 'sub'
    ACTION_TYPE_UNSUB = 'unsub'
    ACTION_TYPE_STARTING = 'get_starting'

    def __init__(self):
        self._mq_connection_str = os.environ.get('RABBIT_MQ_STR_CONN')
        self._queue_for_consume = os.environ.get('QUEUE_THIS_SERVICE')
        self._exchanger_name = os.environ.get('EXCHANGER')
        self._queue_for_error = os.environ.get('ERROR_QUEUE')
        self._queue_for_listing = os.environ.get('ROUTING_KEY_LISTING')

        # ExchangeFactory change and create exchange object
        self._factory = None

        # Storage for async task
        self._futures = dict()

        # variable for rabbitMQ
        self._connection = None
        self._channel = None
        self._exchanger = None

        # Information about exchanges, time frames and pairs in format: {exchange:[[time_frames], [pairs], ...]}
        self._listing = None

    async def run(self):
        """Start consume message queue"""
        # declare queue, start consume
        self._connection = await aio_pika.connect(self._mq_connection_str, loop=asyncio.get_event_loop())
        self._channel = await self._connection.channel()
        queue = await self._channel.declare_queue(self._queue_for_consume, auto_delete=True)

        self._exchanger = await self._channel.declare_exchange(self._exchanger_name, aio_pika.ExchangeType.TOPIC)

        self._factory = ExchangeFactory(self._exchanger)
        self._listing = await self._get_listing_info()

        def callback(message):
            """Callback for process message"""

            try:
                body = json.loads(message.body.decode('utf-8'))
            except json.JSONDecodeError:
                asyncio.get_event_loop().create_task(
                    self._send_error_in_exchange(None, Controller.ERR_NOT_JSON)
                )
                return
            print(body)

            if self._is_not_valid(body):
                return

            loop = asyncio.get_event_loop()
            if body['action'] == Controller.ACTION_TYPE_STARTING:
                if body['data_id'] == DATA_TYPE_LISTING:
                    loop.create_task(self._send_listing_info())
                else:
                    loop.create_task(self._get_starting_data(body['data_id']))
            elif body['action'] == Controller.ACTION_TYPE_SUB:
                loop.create_task(self._subscribe(body['data_id']))
            elif body['action'] == Controller.ACTION_TYPE_UNSUB:
                self._unsubscribe(body['data_id'])

        await queue.consume(callback)
        print('Start consuming queue "{0}"...'.format(self._queue_for_consume))

    def _is_not_valid(self, message):
        """Validation message. If request not valid, then send error message and return True"""
        if 'action' not in message\
            or message['action'] not in (Controller.ACTION_TYPE_SUB, Controller.ACTION_TYPE_UNSUB,
                                         Controller.ACTION_TYPE_STARTING):
            error_place = message.get('data_id')
            asyncio.get_event_loop().create_task(self._send_error_in_exchange(error_place, Controller.ERR_BAD_ACTION))
            return True
        elif 'data_id' not in message:
            asyncio.get_event_loop().create_task(self._send_error_in_exchange('unknown', Controller.ERR_BAD_DATA_TYPE))
            return True
        else:
            # data_id validation
            fragments_id = message['data_id'].split('.')

            if fragments_id[0] not in (DATA_TYPE_DEPTH, DATA_TYPE_TICKER, DATA_TYPE_LISTING, DATA_TYPE_CANDLES):
                asyncio.get_event_loop().create_task(
                    self._send_error_in_exchange(message['data_id'], Controller.ERR_BAD_DATA_TYPE)
                )
                return True

            if fragments_id[0] == DATA_TYPE_LISTING:
                if message['action'] != Controller.ACTION_TYPE_STARTING:
                    asyncio.get_event_loop().create_task(
                        self._send_error_in_exchange(message['data_id'], Controller.ERR_BAD_LISTING_MESSAGE)
                    )
                    return True
                return False

            if fragments_id[0] == DATA_TYPE_CANDLES and len(fragments_id) < 4:
                asyncio.get_event_loop().create_task(
                    self._send_error_in_exchange(message['data_id'], Controller.ERR_BAD_TIME_FRAME)
                )
                return True

            exchange, pair = fragments_id[1], fragments_id[2]
            if exchange not in self._listing:
                asyncio.get_event_loop().create_task(self._send_error_in_exchange(message['data_id'],
                                                                                  Controller.ERR_BAD_EXCHANGE))
                return True
            elif pair not in self._listing[exchange][1]:
                asyncio.get_event_loop().create_task(self._send_error_in_exchange(message['data_id'],
                                                                                  Controller.ERR_BAD_PAIR))
                return True
            elif fragments_id[0] == DATA_TYPE_CANDLES and fragments_id[3] not in self._listing[exchange][0]:
                asyncio.get_event_loop()\
                    .create_task(self._send_error_in_exchange(message['data_id'], Controller.ERR_BAD_TIME_FRAME))
                return True

        return False

    async def _get_listing_info(self):
        """Return listing information as result coroutine

        Format:
        {
            exchange_name_1: [[access_timeframes], [access_pairs]],
            exchange_name_2: [[access_timeframes], [access_pairs]],
            ...
        }

        """
        names_access_exchanges = self._factory.get_all_exchanges_names()

        listing = dict()
        pairs_tasks = []

        for name in names_access_exchanges:
            current_exchange = self._factory.create_exchange(name)
            pairs_tasks.append(current_exchange.get_access_symbols())
            listing[name] = [current_exchange.access_timeframes, ]

        pairs = await asyncio.gather(*pairs_tasks)
        for ind, name in enumerate(names_access_exchanges):
            listing[name].append(pairs[ind])

        return listing

    async def _get_starting_data(self, data_id):
        """Send starting market data"""

        routing_key = f'starting.{data_id}'
        fragments_id = data_id.split('.')
        data_type, exchange, pair = fragments_id[0], fragments_id[1], fragments_id[2]
        exchange = self._factory.create_exchange(exchange)

        loop = asyncio.get_event_loop()
        if data_type == DATA_TYPE_CANDLES:
            time_frame = fragments_id[3]
            loop.create_task(exchange.get_starting_candles(routing_key, pair, time_frame))
        elif data_type == DATA_TYPE_DEPTH:
            loop.create_task(exchange.get_starting_depth(routing_key, pair))
        elif data_type == DATA_TYPE_TICKER:
            loop.create_task(exchange.get_starting_ticker(routing_key, pair))

    async def _subscribe(self, data_id):
        """Method for permanent get update specific market data"""

        routing_key = f'update.{data_id}'
        fragments_id = data_id.split('.')
        data_type, exchange, pair = fragments_id[0], fragments_id[1], fragments_id[2]
        exchange = self._factory.create_exchange(exchange)
        if data_id in self._futures:
            return

        loop = asyncio.get_event_loop()
        if data_type == DATA_TYPE_CANDLES:
            time_frame = fragments_id[3]
            self._futures[data_id] = loop.create_task(exchange.subscribe_candles(routing_key, pair, time_frame))
        elif data_type == DATA_TYPE_DEPTH:
            self._futures[data_id] = loop.create_task(exchange.subscribe_depth(routing_key, pair))
        elif data_type == DATA_TYPE_TICKER:
            self._futures[data_id] = loop.create_task(exchange.subscribe_ticker(routing_key, pair))

    def _unsubscribe(self, data_id):
        """Stop task for get update market data"""
        if data_id in self._futures:
            self._futures[data_id].cancel()
            del self._futures[data_id]

    async def _send_listing_info(self):
        """Update _listing and send new listing in exchange"""
        self._listing = await self._get_listing_info()
        await self._send_data_in_exchange(self._queue_for_listing, json.dumps(self._listing))

    async def _send_data_in_exchange(self, queue_name, data):
        """Send message to exchanger"""
        data = json.dumps(data)
        await self._exchanger.publish(aio_pika.Message(body=data.encode()), routing_key=queue_name)

    async def _send_error_in_exchange(self, error_place, message):
        """Send error to exchanger with error routing_key"""
        message = dict(
            error_place=error_place,
            message=message,
        )
        await self._send_data_in_exchange(queue_name=self._queue_for_error, data=message)
