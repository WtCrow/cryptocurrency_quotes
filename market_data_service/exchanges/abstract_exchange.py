from abc import ABCMeta, abstractmethod
import aio_pika
import asyncio
import json
import os


class BaseExchange:
    """Base class for exchanges-connectors"""

    __metaclass__ = ABCMeta

    def __init__(self, exchanger):
        self.exchanger = exchanger

    async def get_access_symbols(self):
        """Return access pair in unit view

        Pairs not contains symbols - _ \\ // etc...
        All pairs in upper register
        :return: [str, ...]

        """
        try:
            return await self._get_access_symbols()
        except (asyncio.CancelledError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            if type(e).__name__ != asyncio.CancelledError.__name__:
                return []

    async def get_starting_ticker(self, symbol):
        """Return starting ticker

        :return: [bid: str, ask: str]

        """
        try:
            return await self._get_starting_ticker(symbol)
        except (asyncio.CancelledError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            if type(e).__name__ != asyncio.CancelledError.__name__:
                return [0, 0]

    async def get_starting_candles(self, symbol, time_frame):
        """Return max access count candles

        :return: [candle, candle, ...]
        candle format: [time: int (unix_time), open: str, high: str, low: str, close: str]

        """
        try:
            return await self._get_starting_candles(symbol, time_frame)
        except (asyncio.CancelledError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            if type(e).__name__ != asyncio.CancelledError.__name__:
                return []

    async def get_starting_depth(self, symbol):
        """Return current depth

        bids[i][0] >= bids[i + 1][0]
        asks[i][0] >= asks[i + 1][0]
        :return: [bids: [[price, volume], [price, volume], ...], asks: [[price, volume], [price, volume], ...]]

        """
        try:
            return await self._get_starting_depth(symbol)
        except (asyncio.CancelledError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            if type(e).__name__ != asyncio.CancelledError.__name__:
                return [[], []]

    async def subscribe_ticker(self, queue_name, symbol):
        """Send update about current best bid and ask

        :param queue_name: str name queue for send data
        :param symbol: str pair for listener
        :return: None, data send in queue in format: [bid: str, ask: str]

        """
        try:
            await self._subscribe_ticker(queue_name, symbol)
        except (asyncio.CancelledError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            if type(e).__name__ != asyncio.CancelledError.__name__:
                await self._send_error_message(queue_name, e)

    async def subscribe_candles(self, queue_name, symbol, time_frame):
        """Send update candle

        :param queue_name: str name queue for send data
        :param symbol: str pair for listener
        :param time_frame: str time frame for listener
        :return: None, data send in queue in format:
        [time: int (unix_time), open: str, high: str, low: str, close: str]

        """
        try:
            await self._subscribe_candles(queue_name, symbol, time_frame)
        except (asyncio.CancelledError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            if type(e).__name__ != asyncio.CancelledError.__name__:
                await self._send_error_message(queue_name, e)

    async def subscribe_depth(self, queue_name, symbol):
        """Send update about depth

        :param queue_name: str name queue for send data
        :param symbol: str pair for listener
        :return: None, data send in queue in format:
        [bids: [[price, volume], [price, volume], ...], asks: [[price, volume], [price, volume], ...]]
        bids[i][0] >= bids[i + 1][0]
        asks[i][0] >= asks[i + 1][0]

        """
        try:
            await self._subscribe_depth(queue_name, symbol)
        except (asyncio.CancelledError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            if type(e).__name__ != asyncio.CancelledError.__name__:
                await self._send_error_message(queue_name, e)

    # patterns methods
    @abstractmethod
    async def _get_access_symbols(self):
        pass

    @abstractmethod
    async def _get_starting_ticker(self, symbol):
        pass

    @abstractmethod
    async def _get_starting_candles(self, symbol, time_frame):
        pass

    @abstractmethod
    async def _get_starting_depth(self, symbol):
        pass

    @abstractmethod
    async def _subscribe_ticker(self, queue_name, symbol):
        pass

    @abstractmethod
    async def _subscribe_candles(self, queue_name, symbol, time_frame):
        pass

    @abstractmethod
    async def _subscribe_depth(self, queue_name, symbol):
        pass

    async def _send_data_in_exchange(self, queue_name, data):
        """Send message in queue"""
        data = json.dumps(data)
        await self.exchanger.publish(aio_pika.Message(body=data.encode()), routing_key=queue_name)

    async def _send_error_message(self, queue_name, exception=None):
        """Send error in queue"""
        err_queue = os.environ.get('ERROR_QUEUE')
        await self._send_data_in_exchange(err_queue, {"error": queue_name, "exception": exception})
