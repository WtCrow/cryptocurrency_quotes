from abc import abstractmethod
import aio_pika
import asyncio
import json
import os


def _catch_error_decorator_factory(empty_data=None):
    """Decorator on collect-methods for catch errors

    If method raise exception (server not access, changed API etc...), send error to error queue
        and send/return empty_data

    """
    def catch_error_decorator(target):
        async def wrapper(*args, **kwargs):
            try:
                return await target(*args, **kwargs)
            except (asyncio.CancelledError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
                if type(e).__name__ != asyncio.CancelledError.__name__:
                    if len(args) > 1:
                        await args[0]._send_data_in_exchange(args[1], empty_data)
                        await args[0]._send_error_message(error_place=args[1], exception=type(e).__name__)
                    else:
                        await args[0]._send_error_message(error_place='get_access_symbols', exception=type(e).__name__)
                        return []
        return wrapper
    return catch_error_decorator


class BaseExchange:

    def __init__(self, mq_exchanger):
        self.exchanger = mq_exchanger
        self.time_out = 2
        self.request_candles = 1000

    @_catch_error_decorator_factory(empty_data=[])
    async def get_access_symbols(self):
        """Return list access pairs

        All connectors return pairs in upper case without specific symbols, such as - _ // \\ etc...

        """
        return await self._get_access_symbols()

    @abstractmethod
    def _get_access_symbols(self):
        """Implementation get_access_symbols"""
        pass

    @_catch_error_decorator_factory(empty_data=[0, 0])
    async def get_starting_ticker(self, queue_name, symbol):
        """Send current ticker (bid and ask prices) to exchanger with routing_key == queue_name

        send array with 2 string numbers bid and ask (best price for sale/buy by market)

        """
        await self._get_starting_ticker(queue_name, symbol)

    @abstractmethod
    def _get_starting_ticker(self, queue_name, symbol):
        """Implementation get_starting_ticker"""
        pass

    @_catch_error_decorator_factory(empty_data=[])
    async def get_starting_candles(self, queue_name, symbol, time_frame):
        """Send array OHLCV-candles to exchanger with routing_key == queue_name

        Candle format: [open: : str(float), high: : str(float), low: str(float), close: str(float), volume: str(float),
                        time: int (unix_time)]

        """
        await self._get_starting_candles(queue_name, symbol, time_frame)

    @abstractmethod
    async def _get_starting_candles(self, queue_name, symbol, time_frame):
        """Implementation get_starting_candles"""
        pass

    @_catch_error_decorator_factory(empty_data=[[], []])
    async def get_starting_depth(self, queue_name, symbol):
        """Send current depth to exchanger with routing_key == queue_name

        array, that contain 2 arrays
        [bid_arr, ask_arr]
        [ [[price: str(float), volume: str(float)], [price, volume], ...], [[price, volume], [price, volume], ...]]

        prices sorted
        bids[i][0] > bids[i + 1][0]
        asks[i][0] > asks[i + 1][0]

        """
        await self._get_starting_depth(queue_name, symbol)

    @abstractmethod
    async def _get_starting_depth(self, queue_name, symbol):
        """Implementation get_starting_depth"""
        pass

    @_catch_error_decorator_factory(empty_data=[0, 0])
    async def subscribe_ticker(self, queue_name, symbol):
        """Send update about ticker (bid and ask prices) to exchanger with routing_key == queue_name

        send array with 2 string numbers bid and ask (best price for sale/buy by market)

        """
        await self._subscribe_ticker(queue_name, symbol)

    @abstractmethod
    async def _subscribe_ticker(self, queue_name, symbol):
        """Implementation subscribe_ticker"""
        pass

    @_catch_error_decorator_factory([])
    async def subscribe_candles(self, queue_name, symbol, time_frame):
        """Send update candle to exchanger with routing_key == queue_name

        candle is array:
            [open: str(float), high: str(float), low: str(float), close: str(float), volume: str(float),
             time: int (unix_time)]

        """
        await self._subscribe_candles(queue_name, symbol, time_frame)

    async def _subscribe_candles(self, queue_name, symbol, time_frame):
        """Implementation subscribe_candles"""
        pass

    @_catch_error_decorator_factory(empty_data=[[], []])
    async def subscribe_depth(self, queue_name, symbol):
        """Send update about depth to exchanger with routing_key == queue_name

        array, that contain 2 arrays
        [bid_arr, ask_arr]
        [ [[price: str(float), volume: str(float)], [price, volume], ...], [[price, volume], [price, volume], ...]]

        prices sorted
        bids[i][0] > bids[i + 1][0]
        asks[i][0] > asks[i + 1][0]

        """
        await self._subscribe_depth(queue_name, symbol)

    async def _subscribe_depth(self, queue_name, symbol):
        """Implementation subscribe_depth"""
        pass

    async def _send_data_in_exchange(self, queue_name, data):
        """Send message in queue"""
        data = json.dumps(data)
        await self.exchanger.publish(aio_pika.Message(body=data.encode()), routing_key=queue_name)

    async def _send_error_message(self, error_place, exception=None):
        """Send error in queue"""
        print('error')
        err_queue = os.environ.get('ERROR_QUEUE')
        await self._send_data_in_exchange(err_queue, {"error_place": error_place, "message": exception})
