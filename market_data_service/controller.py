from exchanges.exchange_factory import ExchangeFactory
from pathlib import Path
import aio_pika
import asyncio
import yaml
import json

DATA_TYPE_CANDLES = 'candles'
DATA_TYPE_DEPTH = 'depth'
DATA_TYPE_TICKER = 'ticker'
DATA_TYPE_LISTING = 'listing_info'


class Controller:
    """Consumer message from RabbitMQ

    API for micro service:

    in queue queue_this_node from config file (current queue: 'crypto_currency_ms') send json message with format:
        {
            action: {sub | unsub | get_starting_data},
            data_id: {data_type.exchange.pair[.time_frame] | listing_info}
        }

    action:
    sub - start task, for get updates
    unsub - stop update data task
    get_starting_data - get starting data

    data_id:
    listing_info - get information about exchange, pair and time frames access.
    Send only with 'get_starting_data' action

    data_type: ticket | candles | depth
    Good fragments data_id (exchange, pair and time_frame) can get if use listing_info

    Information send in queue with name:

    market_data: (update | starting).data_type.exchange.pair[.time_frame]
    All queue names equals data_id from your request with pre 'update' | 'starting'
    With 'update' send information about snapshot
    With 'starting' send information about starting data
    With time_frame send information about candles

    listing: actual name listing storage in config. Current: crypto_currency_ms_listing

    errors: actual name listing storage in config. Current: crypto_currency_ms_err

    """

    IS_DEBUG = False

    ERR_BAD_DATA_TYPE = "Bad 'data_type' value"
    ERR_BAD_EXCHANGE = "Invalid 'exchange' value"
    ERR_BAD_PAIR = "Invalid 'pair' value"
    ERR_BAD_TIME_FRAME = "Invalid 'time_frame' value"
    ERR_BAD_LISTING_MESSAGE = "Listing information send only if 'action' = 'get_starting_data'"
    ERR_BAD_ACTION = "Invalid 'action' value"
    ERR_NOT_ACTION = "Not 'action' value"
    ERR_NOT_DATA_ID = "Not 'data_id' value"
    ERR_NOT_JSON = "Message not is JSON"

    ACTION_TYPE_SUB = 'sub'
    ACTION_TYPE_UNSUB = 'unsub'
    ACTION_TYPE_STARTING = 'get_starting'

    def __init__(self):
        # read config
        path_to_config = Path(__file__).parents[0] / 'configs'
        with open(path_to_config / 'config.yaml', 'r') as f:
            config = yaml.safe_load(f)
            self._mq_connection_str = config['connection_str']
            self._queue_for_consume = config['queue_this_node']
            self._exchanger_name = config['exchanger_name']
            self._queue_for_error = config['queue_error']
            self._queue_for_listing = config['queue_listing']

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
        # get listing for validation message
        self._listing = await self._get_listing_info()

        def callback(message):
            """Callback for process message"""
            if Controller.IS_DEBUG:
                print(message.body)

            try:
                body = json.loads(message.body.decode('utf-8'))

                # call validation
                if self._is_not_valid(body):
                    return

                # get action and call specific command
                if body['action'] == Controller.ACTION_TYPE_STARTING:
                    if body['data_id'] == DATA_TYPE_LISTING:
                        asyncio.get_event_loop().create_task(self._send_listing_info())
                    else:
                        asyncio.get_event_loop().create_task(self._get_starting_data(body['data_id']))
                elif body['action'] == Controller.ACTION_TYPE_SUB:
                    asyncio.get_event_loop().create_task(self._subscribe(body['data_id']))
                elif body['action'] == Controller.ACTION_TYPE_UNSUB:
                    self._unsubscribe(body['data_id'])
            except json.JSONDecodeError:
                asyncio.get_event_loop().create_task(self._send_error_in_exchange(
                    Controller.ERR_NOT_JSON, message.body))
                return

        await queue.consume(callback)
        print('Start consuming queue "{0}"...'.format(self._queue_for_consume))

    def _is_not_valid(self, message):
        """Validation message"""
        if 'action' not in message.keys():
            asyncio.get_event_loop().create_task(self._send_error_in_exchange(Controller.ERR_NOT_ACTION, message))
            return True
        elif 'data_id' not in message.keys():
            asyncio.get_event_loop().create_task(self._send_error_in_exchange(Controller.ERR_NOT_DATA_ID, message))
            return True
        elif message['action'] not in (Controller.ACTION_TYPE_SUB, Controller.ACTION_TYPE_UNSUB,
                                       Controller.ACTION_TYPE_STARTING):
            asyncio.get_event_loop().create_task(self._send_error_in_exchange(Controller.ERR_BAD_ACTION, message))
            return True
        else:
            # data_id validation
            fragments_id = message['data_id'].split('.')

            # if listing, fragments_id contain only one item
            if fragments_id[0] == DATA_TYPE_LISTING:
                if message['action'] != Controller.ACTION_TYPE_STARTING:
                    asyncio.get_event_loop().create_task(self._send_error_in_exchange(
                        Controller.ERR_BAD_LISTING_MESSAGE, message))
                return False

            # need 3 items (data_type.exchange.pair) and if data_type candles, need 4 item time_frame
            if (((fragments_id[0] == DATA_TYPE_TICKER or fragments_id[0] == DATA_TYPE_DEPTH) and len(fragments_id) != 3)
                    or (fragments_id[0] == DATA_TYPE_CANDLES and len(fragments_id) != 4)):
                asyncio.get_event_loop().create_task(self._send_error_in_exchange(
                    Controller.ERR_BAD_DATA_TYPE, message))
                return True

            # check message and last listing
            exchange, pair = fragments_id[1], fragments_id[2]
            if exchange not in self._factory.get_all_exchanges_names():
                asyncio.get_event_loop().create_task(
                    self._send_error_in_exchange(Controller.ERR_BAD_EXCHANGE, message))
                return True
            elif pair not in self._listing[exchange][1]:
                asyncio.get_event_loop().create_task(
                    self._send_error_in_exchange(Controller.ERR_BAD_PAIR, message))
                return True
            elif fragments_id[0] == DATA_TYPE_CANDLES and fragments_id[3] not in self._listing[exchange][0]:
                asyncio.get_event_loop().create_task(
                    self._send_error_in_exchange(Controller.ERR_BAD_TIME_FRAME, message))
                return True

        return False

    async def _send_listing_info(self):
        """Send listing information in queue and update variable in controller object

        Format: {exchange=[access_time_frames, access_pairs]}

        """
        self._listing = await self._get_listing_info()
        await self._send_data_in_exchange(self._queue_for_listing, json.dumps(self._listing))

    async def _get_starting_data(self, data_id):
        """Send starting market data"""

        routing_key = f'starting.{data_id}'

        # type_task.exchange.pair[.time_frame]
        task_params = data_id.split('.')

        data_type, exchange, pair = task_params[0], task_params[1], task_params[2]
        exchange = self._factory.create_exchange(exchange)

        if data_type == DATA_TYPE_CANDLES:
            time_frame = task_params[3]
            await self._send_data_in_exchange(routing_key, await exchange.get_starting_candles(pair, time_frame))
        elif data_type == DATA_TYPE_DEPTH:
            await self._send_data_in_exchange(routing_key, await exchange.get_starting_depth(pair))
        elif data_type == DATA_TYPE_TICKER:
            await self._send_data_in_exchange(routing_key, await exchange.get_starting_ticker(pair))

    async def _subscribe(self, data_id):
        """Method for permanent get update specific market data"""

        loop = asyncio.get_event_loop()

        # type_task.exchange.pair[.time_frame]
        task_params = data_id.split('.')
        task_type, exchange, pair = task_params[0], task_params[1], task_params[2]
        exchange = self._factory.create_exchange(exchange)
        routing_key = f'update.{data_id}'

        if task_type == DATA_TYPE_CANDLES:
            time_frame = task_params[3]
            self._futures[data_id] = loop.create_task(exchange.subscribe_candles(routing_key, pair, time_frame))
        elif task_type == DATA_TYPE_DEPTH:
            self._futures[data_id] = loop.create_task(exchange.subscribe_depth(routing_key, pair))
        elif task_type == DATA_TYPE_TICKER:
            self._futures[data_id] = loop.create_task(exchange.subscribe_ticker(routing_key, pair))

    def _unsubscribe(self, data_id):
        """Stop task for get update market data"""
        if data_id in self._futures.keys():
            self._futures[data_id].cancel()
            del self._futures[data_id]

    async def _get_listing_info(self):
        """Return listing information as result coroutine"""
        names_access_exchanges = self._factory.get_all_exchanges_names()

        # need format: {exchange=[access_time_frames, access_pairs]}
        listing = dict()
        pairs_tasks = []

        for name in names_access_exchanges:
            current_exchange = self._factory.create_exchange(name)
            pairs_tasks.append(current_exchange.get_access_symbols())
            listing[name] = [current_exchange.access_time_frames, ]

        pairs = await asyncio.gather(*pairs_tasks)
        for ind, name in enumerate(names_access_exchanges):
            listing[name].append(pairs[ind])

        return listing

    async def _send_data_in_exchange(self, queue_name, data):
        """Send message in queue"""
        data = json.dumps(data)
        await self._exchanger.publish(aio_pika.Message(body=data.encode()), routing_key=queue_name)

    async def _send_error_in_exchange(self, error, bad_message):
        """Send error in queue"""
        message = dict(
            error=error,
            message=bad_message,
        )
        await self._send_data_in_exchange(queue_name=self._queue_for_error, data=message)
