from exchanges.abstract_exchange import BaseExchange
from aiohttp import ClientSession
import datetime
import asyncio
import json
import zlib


class BaseOkExchange(BaseExchange):
    """API OkCoin and OkEx

    API okcoin and okex differ only in endpoints, so i create one base class

    """

    def __init__(self, ws_url, rest_url, exchanger):
        super().__init__(exchanger)
        self._max_candle = 200

        self._endpoint_ws = ws_url
        self._endpoint_rest = rest_url

        # Key this unification view for this MS, value dict this variable for API exchange
        self._time_frame_translate = dict([('M1', '60'), ('M3', '180'), ('M5', '300'), ('M15', '900'),
                                           ('M30', '1800'), ('H1', '3600'), ('H2', '7200'), ('H4', '14400'),
                                           ('H12', '43200'), ('D1', '86400'), ('1W', '604800')])
        self.access_time_frames = list(self._time_frame_translate.keys())

        # Time for repeat if use polling
        self._time_out = 3

    async def _get_access_symbols(self):
        async with ClientSession() as session:
            url_rest = f'{self._endpoint_rest}/instruments/ticker'
            async with session.get(url_rest) as response:
                response = await response.text()
                response = json.loads(response)

                # Data format
                """
                [
                    {
                        "base_currency":"BTC",
                        "instrument_id":"BTC-USDT",
                        "min_size":"0.001",
                        "quote_currency":"USDT",
                        "size_increment":"0.00000001",
                        "tick_size":"0.1"
                    },
                    {
                        "base_currency":"OKB",
                        "instrument_id":"OKB-USDT",
                        "min_size":"1",
                        "quote_currency":"USDT",
                        "size_increment":"0.0001",
                        "tick_size":"0.0001"
                    }
                ]
                """

                try:
                    symbols = [item['instrument_id'].replace('-', '') for item in response]
                except KeyError and TypeError and json.JSONDecodeError:
                    return []

                return symbols

    async def _get_starting_ticker(self, symbol):
        async with ClientSession() as session:
            url_rest = f'{self._endpoint_rest}/instruments/{(await self._symbol_translate(symbol, session))}/ticker'
            async with session.get(url_rest) as response:
                response = await response.text()

                # Data format
                """
                [
                    {
                        "best_ask":"3995.4",
                        "best_bid":"3995.3",
                        "instrument_id":"BTC-USDT",
                        "product_id":"BTC-USDT",
                        "last":"3995.3",
                        "ask":"3995.4",
                        "bid":"3995.3",
                        "open_24h":"3989.7",
                        "high_24h":"4031.9",
                        "low_24h":"3968.9",
                        "base_volume_24h":"31254.359231295",
                        "timestamp":"2019-03-20T04:07:07.912Z",
                        "quote_volume_24h":"124925963.3459723295"
                    },
                    {
                        "best_ask":"1.3205",
                        "best_bid":"1.3204",
                        "instrument_id":"OKB-USDT",
                        "product_id":"OKB-USDT",
                        "last":"1.3205",
                        "ask":"1.3205",
                        "bid":"1.3204",
                        "open_24h":"1.0764",
                        "high_24h":"1.44",
                        "low_24h":"1.0601",
                        "base_volume_24h":"183010468.2062",
                        "timestamp":"2019-03-20T04:07:05.878Z",
                        "quote_volume_24h":"233516598.011530085"
                    }
                ]
                """

                data = json.loads(response)
                bid_ask = (data['best_bid'], data['best_ask'])
                return bid_ask

    async def _get_starting_candles(self, symbol, time_frame):
        async with ClientSession() as session:
            url_rest = f'{self._endpoint_rest}/instruments/{(await self._symbol_translate(symbol, session))}' \
                f'/candles?granularity={self._time_frame_translate[time_frame]}'
            async with session.get(url_rest) as response:
                response = await response.text()
                data = json.loads(response)

                # Data format
                """
                [
                    [
                        "2019-03-19T16:00:00.000Z",
                        "3997.3",
                        "4031.9",
                        "3982.5",
                        "3998.7",
                        "26175.21141385"
                    ],
                    [
                        "2019-03-18T16:00:00.000Z",
                        "3980.6",
                        "4014.6",
                        "3968.9",
                        "3997.3",
                        "33053.48725643"
                    ]
                ]
                """

                candles = []
                for item in data:
                    time = int(datetime.datetime.strptime(item[0], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp())
                    candles.append((item[1], item[2], item[3], item[4], item[5], time))
                candles.reverse()

                return candles

    async def _get_starting_depth(self, symbol):
        async with ClientSession() as session:
            url_rest = f'{self._endpoint_rest}/instruments/{(await self._symbol_translate(symbol, session))}' \
                f'/book?size=20&'
            async with session.get(url_rest) as response:
                response = await response.text()
                bid_ask = json.loads(response)

                # Data format
                """
                {
                    "asks":[
                        [
                            "3993.2",
                            "0.41600068",
                            "1"
                        ],
                        [
                            "3993.4",
                            "1.24807818",
                            "3"
                        ],
                        [
                            "3993.6",
                            "0.03",
                            "1"
                        ],
                        [
                            "3993.8",
                            "0.03",
                            "1"
                        ]
                    ],
                    "bids":[
                        [
                            "3993",
                            "0.15149658",
                            "2"
                        ],
                        [
                            "3992.8",
                            "1.19046818",
                            "1"
                        ],
                        [
                            "3992.6",
                            "0.20831389",
                            "1"
                        ],
                        [
                            "3992.4",
                            "0.01669446",
                            "2"
                        ]
                    ],
                    "timestamp":"2019-03-20T03:55:37.888Z"
                }
                """

                asks = [(item[0], item[1]) for item in bid_ask['asks']]
                bids = [(item[0], item[1]) for item in bid_ask['bids']]
                asks.reverse()
                return bids, asks

    async def _subscribe_ticker(self, queue_name, symbol):
        ping_task = None
        response = None
        try:
            async with ClientSession() as session:
                async with session.ws_connect(self._endpoint_ws) as ws:

                    json_params = {"op": "subscribe",
                                   "args": [f"spot/ticker:{await self._symbol_translate(symbol, session)}"]}
                    await ws.send_json(json_params)

                    response = await ws.receive()
                    data = self._inflate(response.data).decode('utf-8')
                    data = dict(json.loads(data))
                    if 'event' not in data.keys() or data['event'] != 'subscribe':
                        await self._send_error_message(queue_name, response)
                        return

                    ping_task = asyncio.create_task(self._ping_timer(ws))

                    while True:
                        response = await ws.receive()
                        data = self._inflate(response.data).decode('utf-8')

                        if data == 'pong':
                            continue

                        # Data format:
                        """
                         {
                             "table":"spot/ticker",
                             "data":
                                [{
                                "instrument_id":"ETH-USDT",
                                "last":"8.8",
                                "best_bid":"3",
                                "best_ask":"8.1",
                                "open_24h":"5.1",
                                "high_24h":"8.8",
                                "low_24h":"3",
                                "base_volume_24h":"13.77340909",
                                "quote_volume_24h":"78.49886361",
                                "timestamp":"2018-12-20T03:13:41.664Z"
                                }]
                         }
                        """

                        data = json.loads(data)['data'][0]
                        bid_ask = (data['best_bid'], data['best_ask'])
                        await self._send_data_in_exchange(queue_name, bid_ask)
        except (asyncio.CancelledError, KeyError, TypeError, json.JSONDecodeError) as e:
            if ping_task:
                ping_task.cancel()
            if type(e).__name__ != asyncio.CancelledError.__name__:
                await self._send_error_message(queue_name, response)

    async def _subscribe_candles(self, queue_name, symbol, time_frame):
        ping_task = None
        response = None
        try:
            async with ClientSession() as session:
                async with session.ws_connect(self._endpoint_ws) as ws:
                    json_params = {
                        "op": "subscribe",
                        "args": [
                            f"spot/candle{self._time_frame_translate[time_frame]}s:"
                            f"{(await self._symbol_translate(symbol, session))}"
                        ]
                    }
                    await ws.send_json(json_params)

                    response = await ws.receive()
                    data = self._inflate(response.data).decode('utf-8')
                    data = json.loads(data)
                    if 'event' not in data.keys() or data['event'] != 'subscribe':
                        await self._send_error_message(queue_name, response)
                        return

                    ping_task = asyncio.create_task(self._ping_timer(ws))

                    while True:
                        response = await ws.receive()
                        data = self._inflate(response.data).decode('utf-8')

                        if data == 'pong':
                            continue

                        # Data format
                        """
                        {
                          "table":"spot/candle60s",
                          "data":[{
                                    "candle":
                                      [
                                      "2018-12-20T06:18:00.000Z",
                                      "8.8", o
                                      "8.8", h
                                      "8.8", l
                                      "8.8", c
                                      "0" v
                                      ]
                                    ,"instrument_id":"ETH-USDT"
                            }]}
                        """

                        data = json.loads(data)['data'][0]['candle']
                        time = int(datetime.datetime.strptime(data[0], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp())
                        candle = (data[1], data[2], data[3], data[4], data[5], time)

                        await self._send_data_in_exchange(queue_name, candle)
        except (asyncio.CancelledError, KeyError, TypeError, json.JSONDecodeError) as e:
            if ping_task:
                ping_task.cancel()
            if type(e).__name__ != asyncio.CancelledError.__name__:
                await self._send_error_message(queue_name, response)

    async def _subscribe_depth(self, queue_name, symbol):
        async with ClientSession() as session:
            url_rest = f'{self._endpoint_rest}/instruments/{(await self._symbol_translate(symbol, session))}' \
                f'/book?size=20&'
            while True:
                async with session.get(url_rest) as response:
                    response = await response.text()
                    bid_ask = json.loads(response)

                    # Data format
                    """
                    {
                        "asks":[
                            [
                                "3993.2",
                                "0.41600068",
                                "1"
                            ],
                            [
                                "3993.4",
                                "1.24807818",
                                "3"
                            ],
                            [
                                "3993.6",
                                "0.03",
                                "1"
                            ],
                            [
                                "3993.8",
                                "0.03",
                                "1"
                            ]
                        ],
                        "bids":[
                            [
                                "3993",
                                "0.15149658",
                                "2"
                            ],
                            [
                                "3992.8",
                                "1.19046818",
                                "1"
                            ],
                            [
                                "3992.6",
                                "0.20831389",
                                "1"
                            ],
                            [
                                "3992.4",
                                "0.01669446",
                                "2"
                            ]
                        ],
                        "timestamp":"2019-03-20T03:55:37.888Z"
                    }
                    """

                    asks = [(item[0], item[1]) for item in bid_ask['asks']]
                    bids = [(item[0], item[1]) for item in bid_ask['bids']]
                    asks.reverse()
                    await self._send_data_in_exchange(queue_name, (bids, asks))
                    await asyncio.sleep(self._time_out)

    async def _symbol_translate(self, symbol, session):
        """Translate symbol in format for API"""
        url_rest = f'{self._endpoint_rest}/instruments/ticker'
        async with session.get(url_rest) as response:
            response = await response.text()
            response = json.loads(response)

            # Data format
            """
            [
                {
                    "base_currency":"BTC",
                    "instrument_id":"BTC-USDT",
                    "min_size":"0.001",
                    "quote_currency":"USDT",
                    "size_increment":"0.00000001",
                    "tick_size":"0.1"
                },
                {
                    "base_currency":"OKB",
                    "instrument_id":"OKB-USDT",
                    "min_size":"1",
                    "quote_currency":"USDT",
                    "size_increment":"0.0001",
                    "tick_size":"0.0001"
                }
            ]
            """

            for item in response:
                if item['product_id'].replace('-', '') == symbol:
                    return item['product_id']

    @staticmethod
    def _inflate(data):
        decompress = zlib.decompressobj(-zlib.MAX_WBITS)
        inflated = decompress.decompress(data)
        inflated += decompress.flush()
        return inflated

    @staticmethod
    async def _ping_timer(ws, time_out=20):
        try:
            while True:
                await asyncio.sleep(time_out)
                await ws.send_str('ping')
        except asyncio.CancelledError:
            return
