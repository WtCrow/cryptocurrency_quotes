from exchanges.exchanges_connectors import *
from unittest.mock import patch, MagicMock
from collections.abc import Iterable
from unittest import TestCase, skip
import warnings
import asyncio

warnings.simplefilter("ignore", ResourceWarning)


class TestShading:

    class BaseExchangeTests(TestCase):
        """Test classes from exchanges_connectors"""

        def setUp(self):

            # Set await behavior for MagicMock
            async def async_magic():
                pass
            MagicMock.__await__ = lambda x: async_magic().__await__()

            # Test queue and variable for determine in child classes
            self.test_queue = 'test_queue'
            self.symbol = None
            self.time_out = 10

            self.is_print_result = False

            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        def tearDown(self):
            self.loop.close()

        def test_get_access_symbols(self):
            """Test method get_access_symbol

            Method should return list symbols in str format

            """
            task = self.loop.create_task(self.exchange.get_access_symbols())
            self.loop.run_until_complete(task)
            symbols = task.result()
            if self.is_print_result:
                print(symbols)

            self.assertTrue(isinstance(symbols, Iterable))

            self.assertTrue(len(symbols) > 0, 'Symbols count == 0')

            for symbol in symbols:
                self.assertEqual(type(symbol), str, f'symbol == {symbol}, type(symbol) == {type(symbol)}')
                self.assertTrue(symbol.isupper(), f'Symbol {symbol} not is upper')

        @patch('exchanges.abstract_exchange.BaseExchange._send_data_in_exchange')
        def test_get_starting_ticker(self, mock_func):
            """Test method get_starting_ticker

            Method needed return ticker data in format:
            [bid: str, ask: str]

            """
            task = self.loop.create_task(self.exchange.get_starting_ticker(self.test_queue, self.symbol))
            self.loop.run_until_complete(task)
            calls = [call[0] for call in mock_func.call_args_list]
            ticker = calls[0][1]
            if self.is_print_result:
                print(ticker)

            # Данные это строки
            self.assertEqual(type(ticker[0]), str, f'ticker[0] == {ticker[0]}, type == {type(ticker[0])}')
            self.assertEqual(type(ticker[1]), str, f'ticker[1] == {ticker[1]}, type == {type(ticker[1])}')

            # Данные можно преобразовать к float и цена предложения больше цены спроса
            bid, ask = float(ticker[0]), float(ticker[1])
            self.assertTrue(bid <= ask, f'{bid} > {ask}')

        @patch('exchanges.abstract_exchange.BaseExchange._send_data_in_exchange')
        def test_get_starting_candles(self, mock_func):
            """Test method get_starting_candles

            Method needed return candles data in format: [candle, candle, ...]
            candle: [open: str, high: str, low: str, close: str, time: int]

            """
            task = self.loop.create_task(self.exchange.get_starting_candles(self.test_queue, self.symbol,
                                                                            self.exchange.access_timeframes[0]))
            self.loop.run_until_complete(task)
            calls = [call[0] for call in mock_func.call_args_list]
            candles = calls[0][1]
            if self.is_print_result:
                print(candles)

            self.assertTrue(isinstance(candles, Iterable), f'candles == {candles}')

            self.assertTrue(len(candles) > 1, 'Candles count <= 1')

            for candle in candles:
                self._check_candle(candle)

        @patch('exchanges.abstract_exchange.BaseExchange._send_data_in_exchange')
        def test_get_starting_depth(self, mock_func):
            """Test method get_starting_depth

            Method needed return depth data in format:
            [
              bids->[[price: str, size: str], ...],
              asks->[[price: str, size: str], ...])
            ]

            """
            task = self.loop.create_task(self.exchange.get_starting_depth(self.test_queue, self.symbol))
            self.loop.run_until_complete(task)
            calls = [call[0] for call in mock_func.call_args_list]
            depth = calls[0][1]
            if self.is_print_result:
                print(depth)

            for bid in depth[0]:
                self._check_depth_item(bid)
            for ask in depth[1]:
                self._check_depth_item(ask)

            bids = [item[0] for item in depth[0]]
            self.assertTrue(all(bids[i] >= bids[i + 1] for i in range(len(bids) - 1)), f'bids == {bids}')

            asks = [item[0] for item in depth[1]]
            self.assertTrue(all(asks[i] >= asks[i + 1] for i in range(len(asks) - 1)), f'asks == {asks}')

        @patch('exchanges.abstract_exchange.BaseExchange._send_data_in_exchange')
        def test_subscribe_ticker(self, mock_send_data_in_queue):
            """Test method subscribe_ticker

            Method needed return in test_queue information in format:: [bid: str, ask: str]

            """
            task_for_test = self.loop.create_task(self.exchange.subscribe_ticker(self.test_queue, self.symbol))
            self.loop.create_task(self._stop_through(task_for_test))
            self.loop.run_forever()
            calls = [call[0] for call in mock_send_data_in_queue.call_args_list]
            if self.is_print_result:
                print(calls)

            self.assertTrue(len(calls) > 0, 'Calls count == 0')

            for arguments in calls:
                self.assertEqual(arguments[0], self.test_queue, f'{arguments[0]} != {self.test_queue}')

                self.assertEqual(type(arguments[1][0]), str, f'arguments[1][0] == {arguments[1][0]},'
                                 f'type == {type(arguments[1][0])}')
                self.assertEqual(type(arguments[1][1]), str, f'arguments[1][1] == {arguments[1][1]},'
                                 f'type == {type(arguments[1][1])}')

                bid, ask = float(arguments[1][0]), float(arguments[1][1])
                self.assertTrue(bid <= ask, f'{bid} > {ask}')
                self.assertTrue(bid >= 0 and ask >= 0, f'bid == {bid}, ask == {ask}')

        @patch('exchanges.abstract_exchange.BaseExchange._send_data_in_exchange')
        def test_subscribe_candles(self, mock_send_data_in_queue):
            """Test method subscribe_candles

            Method needed return in test_queue information in format:
            [open: str, high: str, low: str, close: str, time: int]

            """
            task_for_test = self.loop.create_task(self.exchange.subscribe_candles(self.test_queue, self.symbol,
                                                                                  self.exchange.access_timeframes[0]))
            self.loop.create_task(self._stop_through(task_for_test))
            self.loop.run_forever()

            calls = [call[0] for call in mock_send_data_in_queue.call_args_list]
            if self.is_print_result:
                print(calls)

            self.assertTrue(len(calls) > 0, 'Calls count == 0')

            for arguments in calls:
                self.assertEqual(arguments[0], self.test_queue, f'{arguments[0]} != {self.test_queue}')
                self._check_candle(arguments[1])

        @patch('exchanges.abstract_exchange.BaseExchange._send_data_in_exchange')
        def test_subscribe_depth(self, mock_send_data_in_queue):
            """Test method subscribe_ticker

            Method needed return in test_queue information in format:
            [
              bids->[[price: str, size: str], ...],
              asks->[[price: str, size: str], ...])
            ]

            """
            task_for_test = self.loop.create_task(self.exchange.subscribe_depth(self.test_queue, self.symbol))
            self.loop.create_task(self._stop_through(task_for_test))
            self.loop.run_forever()

            calls = [call[0] for call in mock_send_data_in_queue.call_args_list]
            if self.is_print_result:
                print(calls)

            self.assertTrue(len(calls) > 0, 'Calls count == 0')

            for arguments in calls:
                self.assertEqual(arguments[0], self.test_queue, f'{arguments[0]} != {self.test_queue}')

                for bid in arguments[1][0]:
                    self._check_depth_item(bid)
                for ask in arguments[1][1]:
                    self._check_depth_item(ask)

                bids = [item[0] for item in arguments[1][0]]
                self.assertTrue(all(bids[i] >= bids[i + 1] for i in range(len(bids) - 1)), f'bids == {bids}')

                asks = [item[0] for item in arguments[1][1]]
                self.assertTrue(all(asks[i] >= asks[i + 1] for i in range(len(asks) - 1)), f'bids == {bids}')

        def _check_candle(self, candle):
            self.assertTrue(isinstance(candle, Iterable), f'Candle not Iterable and contain: {candle}')
            self.assertTrue(len(candle) == 6, f'Candle len < 6 and contain {candle}')

            self.assertTrue(float(candle[4]) >= 0, f'Volume == {candle[4]}')

            self.assertTrue(type(candle[5]) == int and candle[5] >= 0, f'time == {candle[5]}')

            # o, h, l, c
            prices = candle[:4]
            for price in prices:
                self.assertEqual(type(price), str, f'type(price) == {type(price)}, price == {price}')
                float(price)

            prices = [float(price) for price in prices]
            max_price, low_price = max(prices), min(prices)

            self.assertEqual(max_price, prices[1], f'prices == {prices}, max_price == {max_price}, high == {prices[1]}')
            self.assertEqual(low_price, prices[2], f'prices == {prices}, low_price == {low_price}, high == {prices[2]}')

        def _check_depth_item(self, depth_item):
            self.assertEqual(type(depth_item[0]), str, f'type == {type(depth_item[0])},'
                                                       f' depth_item[0] =={depth_item[0]}')
            self.assertEqual(type(depth_item[1]), str, f'type == {type(depth_item[1])},'
                                                       f' depth_item[1] =={depth_item[1]}')

            self.assertTrue(float(depth_item[0]) >= 0, f'{float(depth_item[0])} < 0')
            self.assertTrue(float(depth_item[1]) >= 0, f'{float(depth_item[1])} < 0')

        async def _stop_through(self, task):
            await asyncio.sleep(self.time_out)
            task.cancel()
            self.loop.stop()


class BinanceTests(TestShading.BaseExchangeTests):

    def setUp(self):
        super().setUp()

        self.symbol = 'BTCUSDT'
        self.exchange = Binance(None)
        self.is_print_result = True


class BittrexTests(TestShading.BaseExchangeTests):

    def setUp(self):
        super().setUp()

        self.symbol = 'BTCUSDT'
        self.exchange = Bittrex(None)
        self.is_print_result = True


class HitBTCTests(TestShading.BaseExchangeTests):

    def setUp(self):
        super().setUp()

        self.symbol = 'BTCUSD'
        self.exchange = HitBTC(None)
        self.is_print_result = True


class HuobiGlobalTests(TestShading.BaseExchangeTests):

    def setUp(self):
        super().setUp()

        self.symbol = 'BTCUSDT'
        self.exchange = HuobiGlobal(None)
        self.is_print_result = True
        # TODO pong message raise error


class OkCoinTests(TestShading.BaseExchangeTests):

    def setUp(self):
        super().setUp()

        self.symbol = 'BTCUSD'
        self.exchange = OkCoin(None)
        self.is_print_result = True
        self.time_out = 20


class OkExTests(TestShading.BaseExchangeTests):

    def setUp(self):
        super().setUp()

        self.symbol = 'BTCUSDT'
        self.exchange = OkEx(None)
        self.is_print_result = True
        self.time_out = 20
