from exchanges.abstract_exchange import BaseExchange
from aiohttp import ClientSession
import asyncio
import json


class Binance(BaseExchange):
    """Connector to Binance"""

    name = 'Binance'

    def __init__(self, exchanger):
        super().__init__(exchanger)
        self._max_candles = 1000

        self._root_url_ws = 'wss://stream.binance.com:9443/ws'
        self._root_url_rest = 'https://api.binance.com'

        # Key this unification view for this MS, value dict this variable for API exchange
        self._time_frame_translate = dict([('M1', '1m'), ('M5', '5m'), ('M15', '15m'), ('M30', '30m'),
                                           ('H1', '1h'), ('H4', '4h'), ('D1', '1d'), ('1W', '1w')])
        self.access_time_frames = list(self._time_frame_translate.keys())

        # Time for repeat if use polling
        self._time_out = 2

    async def _get_access_symbols(self):
        async with ClientSession() as session:
            rest_url = f'{self._root_url_rest}/api/v3/ticker/price'
            async with session.get(rest_url) as response:
                response = await response.text()

                # Data format
                """
                [
                  {
                    "symbol": "LTCBTC",
                    "price": "4.00000200"
                  },
                  {
                    "symbol": "ETHBTC",
                    "price": "0.07946600"
                  }
                ]
                """

                try:
                    response = json.loads(response)
                    symbols = [item['symbol'] for item in response]
                except (KeyError, TypeError, json.JSONDecodeError):
                    return []

                return symbols

    async def _get_starting_ticker(self, symbol):
        url_rest = f'{self._root_url_rest}/api/v3/ticker/bookTicker?symbol={symbol}'
        async with ClientSession() as session:
            async with session.get(url_rest) as response:
                response = await response.text()

                # Data format:
                """
                {
                    "symbol":"BTCUSDT",
                    "bidPrice":"10724.80000000",
                    "bidQty":"0.39682900",
                    "askPrice":"10726.80000000",
                    "askQty":"0.06294600"
                }
                """
                ticker = json.loads(response)
                return ticker['bidPrice'], ticker['askPrice']

    async def _get_starting_candles(self, symbol, time_frame):
        async with ClientSession() as session:
            rest_url = f'{self._root_url_rest}/api/v1/klines?symbol={symbol}' \
                f'&interval={self._time_frame_translate[time_frame]}&limit={self._max_candles}'
            async with session.get(rest_url) as response:
                response = await response.text()
                array_candles = json.loads(response)

                # Data format:
                """
                [
                  [
                    1499040000000,      // Open time
                    "0.01634790",       // Open
                    "0.80000000",       // High
                    "0.01575800",       // Low
                    "0.01577100",       // Close
                    "148976.11427815",  // Volume
                    1499644799999,      // Close time
                    "2434.19055334",    // Quote asset volume
                    308,                // Number of trades
                    "1756.87402397",    // Taker buy base asset volume
                    "28.46694368",      // Taker buy quote asset volume
                    "17928899.62484339" // Ignore.
                  ]
                ]
                """

                candles = []
                for item in array_candles:
                    time = int(item[0]) // 1000
                    candles.append((item[1], item[2], item[3], item[4], item[5], time))

                return candles

    async def _get_starting_depth(self, symbol):
        url_rest = f'{self._root_url_rest}/api/v1/depth?symbol={symbol}&limit=20'
        async with ClientSession() as session:
            async with session.get(url_rest) as response:
                response = await response.text()

                # Data format:
                """
                {
                  "lastUpdateId": 1027024,
                  "bids": [
                    [
                      "4.00000000",     // PRICE
                      "431.00000000"    // QTY
                    ]
                  ],
                  "asks": [
                    [
                      "4.00000200",
                      "12.00000000"
                    ]
                  ]
                }
                """

                bid_ask = json.loads(response)
                asks = [(item[0], item[1]) for item in bid_ask['asks']]
                bids = [(item[0], item[1]) for item in bid_ask['bids']]
                asks.reverse()

                return bids, asks

    async def _subscribe_ticker(self, queue_name, symbol):
        async with ClientSession() as session:
            ws_url = f'{self._root_url_ws}/{symbol.lower()}@ticker'
            async with session.ws_connect(ws_url) as ws:
                while True:
                    response = await ws.receive()
                    data = json.loads(response.data)

                    # Data format
                    """
                    {
                      "e": "24hrTicker",  // Event type
                      "E": 123456789,     // Event time
                      "s": "BNBBTC",      // Symbol
                      "p": "0.0015",      // Price change
                      "P": "250.00",      // Price change percent
                      "w": "0.0018",      // Weighted average price
                      "x": "0.0009",      // First trade(F)-1 price (first trade before the 24hr rolling window)
                      "c": "0.0025",      // Last price
                      "Q": "10",          // Last quantity
                      "b": "0.0024",      // Best bid price
                      "B": "10",          // Best bid quantity
                      "a": "0.0026",      // Best ask price
                      "A": "100",         // Best ask quantity
                      "o": "0.0010",      // Open price
                      "h": "0.0025",      // High price
                      "l": "0.0010",      // Low price
                      "v": "10000",       // Total traded base asset volume
                      "q": "18",          // Total traded quote asset volume
                      "O": 0,             // Statistics open time
                      "C": 86400000,      // Statistics close time
                      "F": 0,             // First trade ID
                      "L": 18150,         // Last trade Id
                      "n": 18151          // Total number of trades
                    }
                    """

                    bid_ask = (data['b'], data['a'])
                    await self._send_data_in_exchange(queue_name, bid_ask)

    async def _subscribe_candles(self, queue_name, symbol, time_frame):
        async with ClientSession() as session:
            symbol = symbol.lower()
            url_ws = f'{self._root_url_ws}/{symbol}@kline_{self._time_frame_translate[time_frame]}'
            async with session.ws_connect(url_ws) as ws:
                while True:
                    response = await ws.receive()

                    # Data format:
                    """
                    {
                      "e": "kline",     // Event type
                      "E": 123456789,   // Event time
                      "s": "BNBBTC",    // Symbol
                      "k": {
                        "t": 123400000, // Kline start time
                        "T": 123460000, // Kline close time
                        "s": "BNBBTC",  // Symbol
                        "i": "1m",      // Interval
                        "f": 100,       // First trade ID
                        "L": 200,       // Last trade ID
                        "o": "0.0010",  // Open price
                        "c": "0.0020",  // Close price
                        "h": "0.0025",  // High price
                        "l": "0.0015",  // Low price
                        "v": "1000",    // Base asset volume
                        "n": 100,       // Number of trades
                        "x": false,     // Is this kline closed?
                        "q": "1.0000",  // Quote asset volume
                        "V": "500",     // Taker buy base asset volume
                        "Q": "0.500",   // Taker buy quote asset volume
                        "B": "123456"   // Ignore
                      }
                    }
                    """

                    candle_data = json.loads(response.data)['k']
                    time = int(candle_data['t']) // 1000
                    candle = (candle_data['o'], candle_data['h'], candle_data['l'], candle_data['c'],
                              candle_data['v'], time)

                    await self._send_data_in_exchange(queue_name, candle)

    async def _subscribe_depth(self, queue_name, symbol):
        url_rest = f'{self._root_url_rest}/api/v1/depth?symbol={symbol}&limit=20'
        async with ClientSession() as session:
            while True:
                async with session.get(url_rest) as response:
                    response = await response.text()

                    # Data format:
                    """
                    {
                      "lastUpdateId": 1027024,
                      "bids": [
                        [
                          "4.00000000",     // PRICE
                          "431.00000000"    // QTY
                        ]
                      ],
                      "asks": [
                        [
                          "4.00000200",
                          "12.00000000"
                        ]
                      ]
                    }
                    """

                    bid_ask = json.loads(response)
                    asks = [(item[0], item[1]) for item in bid_ask['asks']]
                    bids = [(item[0], item[1]) for item in bid_ask['bids']]
                    asks.reverse()

                    await self._send_data_in_exchange(queue_name, (bids, asks))
                    await asyncio.sleep(self._time_out)
