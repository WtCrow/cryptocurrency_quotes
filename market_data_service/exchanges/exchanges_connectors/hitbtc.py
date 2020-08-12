from exchanges.abstract_exchange import BaseExchange
from aiohttp import ClientSession
from datetime import datetime
import hashlib
import asyncio
import json


class HitBTC(BaseExchange):
    """Connector to HitBTC"""

    name = 'HitBTC'

    def __init__(self, mq_exchanger):
        super().__init__(mq_exchanger)

        self._root_url_ws = 'wss://api.hitbtc.com/api/2/ws'
        self._root_url_rest = 'https://api.hitbtc.com'

        # Key this unification view for this MS, value dict this variable for API exchange
        self.access_timeframes = ('M1', 'M3', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'D7', '1M')

    async def _get_access_symbols(self):
        async with ClientSession() as session:
            url = f'{self._root_url_rest}/api/2/public/symbol'
            async with session.get(url) as response:
                response = await response.text()

                # Data format:
                """
                [      
                  {
                    "id": "ETHBTC",
                    "baseCurrency": "ETH",
                    "quoteCurrency": "BTC",
                    "quantityIncrement": "0.001",
                    "tickSize": "0.000001",
                    "takeLiquidityRate": "0.001",
                    "provideLiquidityRate": "-0.0001",
                    "feeCurrency": "BTC"
                  }
                ],
                ...
                """
                response = json.loads(response)
                symbols = [item['id'] for item in response]
                return symbols

    async def _get_raw_data_ticker(self, queue_name, symbol):
        async with ClientSession() as session:
            url = f'{self._root_url_rest}/api/2/public/ticker/{symbol}'
            async with session.get(url) as response:
                response = await response.text()

                # Data format
                """
                {
                    "ask": "0.050043",
                    "bid": "0.050042",
                    "last": "0.050042",
                    "open": "0.047800",
                    "low": "0.047052",
                    "high": "0.051679",
                    "volume": "36456.720",
                    "volumeQuote": "1782.625000",
                    "timestamp": "2017-05-12T14:57:19.999Z",
                    "symbol": "ETHBTC"
                }
                """
                ticker = json.loads(response)
                await self._send_data_in_exchange(queue_name, ticker)

    async def _get_starting_ticker(self, queue_name, symbol):
        url = f'{self._root_url_rest}/api/2/public/ticker/{symbol}'
        async with ClientSession() as session:
            async with session.get(url) as response:
                response = await response.text()

                # Data format
                """
                {
                    "ask": "0.050043",
                    "bid": "0.050042",
                    "last": "0.050042",
                    "open": "0.047800",
                    "low": "0.047052",
                    "high": "0.051679",
                    "volume": "36456.720",
                    "volumeQuote": "1782.625000",
                    "timestamp": "2017-05-12T14:57:19.999Z",
                    "symbol": "ETHBTC"
                }
                """
                ticker = json.loads(response)
                await self._send_data_in_exchange(queue_name, (ticker['bid'], ticker['ask']))

    async def _get_starting_candles(self, queue_name, symbol, time_frame):
        url = f'{self._root_url_rest}/api/2/public/candles/{symbol}?period={time_frame}' \
              f'&limit={self.request_candles}&sort=DESC'
        async with ClientSession() as session:
            async with session.get(url) as response:
                response = await response.text()
                candles = json.loads(response)

                # Data format
                """
                [
                  {
                    "timestamp": "2017-10-20T20:00:00.000Z",
                    "open": "0.050459",
                    "close": "0.050087",
                    "min": "0.050000",
                    "max": "0.050511",
                    "volume": "1326.628",
                    "volumeQuote": "66.555987736"
                  },
                  {
                    "timestamp": "2017-10-20T20:30:00.000Z",
                    "open": "0.050108",
                    "close": "0.050139",
                    "min": "0.050068",
                    "max": "0.050223",
                    "volume": "87.515",
                    "volumeQuote": "4.386062831"
                  }
                ]
                """
                formatted_candles = []
                for candle in candles:
                    time = int(datetime.strptime(candle['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ').timestamp())
                    formatted_candles.append((candle['open'], candle['max'], candle['min'], candle['close'],
                                              candle['volume'], time))
                formatted_candles.reverse()

                await self._send_data_in_exchange(queue_name, formatted_candles)

    async def _get_starting_depth(self, queue_name, symbol):
        url = f'{self._root_url_rest}/api/2/public/orderbook/{symbol}?limit=20'
        async with ClientSession() as session:
            async with session.get(url) as response:
                response = await response.text()

                # Data format
                """
                {
                  "ask": [
                    {
                      "price": "0.046002",
                      "size": "0.088"
                    },
                    {
                      "price": "0.046800",
                      "size": "0.200"
                    }
                  ],
                  "bid": [
                    {
                      "price": "0.046001",
                      "size": "0.005"
                    },
                    {
                      "price": "0.046000",
                      "size": "0.200"
                    }
                  ],
                  "timestamp": "2018-11-19T05:00:28.193Z"
                }
                """
                bid_ask = json.loads(response)
                asks = [(item['price'], item['size']) for item in bid_ask['ask']]
                bids = [(item['price'], item['size']) for item in bid_ask['bid']]
                asks.reverse()
                await self._send_data_in_exchange(queue_name, (bids, asks))

    async def _subscribe_ticker(self, queue_name, symbol):
        async with ClientSession() as session:
            async with session.ws_connect(self._root_url_ws) as ws:
                id_ = hashlib.md5("hitbtc_ticker".encode('utf-8')).hexdigest()
                json_params = {
                    "method": "subscribeTicker",
                    "params": {
                        "symbol": symbol
                    },
                    "id": id_
                }
                await ws.send_json(json_params)
                response = await ws.receive()
                # первое сообщение это результат соединения
                if not json.loads(response.data)['result']:
                    await self._send_error_message(queue_name, response)
                    return

                while True:
                    response = await ws.receive()

                    # Data format
                    """
                    {
                      "jsonrpc": "2.0",
                      "method": "ticker",
                      "params": {
                        "ask": "0.054464",
                        "bid": "0.054463",
                        "last": "0.054463",
                        "open": "0.057133",
                        "low": "0.053615",
                        "high": "0.057559",
                        "volume": "33068.346",
                        "volumeQuote": "1832.687530809",
                        "timestamp": "2017-10-19T15:45:44.941Z",
                        "symbol": "ETHBTC"
                      }
                    }
                    """
                    data = json.loads(response.data)['params']
                    bid_ask = (data['bid'], data['ask'])
                    await self._send_data_in_exchange(queue_name, bid_ask)

    async def _subscribe_candles(self, queue_name, symbol, time_frame):
        async with ClientSession() as session:
            async with session.ws_connect(self._root_url_ws) as ws:

                id_ = hashlib.md5("hitbtc_candles".encode('utf-8')).hexdigest()
                json_params = {
                    "method": "subscribeCandles",
                    "params": {
                        "symbol": symbol,
                        "period": time_frame,
                        "limit": 1
                    },
                    "id": id_
                }
                await ws.send_json(json_params)
                response = await ws.receive()
                if not json.loads(response.data)['result']:
                    await self._send_error_message(queue_name, response)
                    return

                while True:
                    response = await ws.receive()

                    # Data format first message:
                    """
                    {
                      "jsonrpc": "2.0",
                      "method": "snapshotCandles",
                      "params": {
                        "data": [
                          {
                            "timestamp": "2017-10-19T15:00:00.000Z",
                            "open": "0.054801",
                            "close": "0.054625",
                            "min": "0.054601",
                            "max": "0.054894",
                            "volume": "380.750",
                            "volumeQuote": "20.844237223"
                          },
                          {
                            "timestamp": "2017-10-19T15:30:00.000Z",
                            "open": "0.054616",
                            "close": "0.054618",
                            "min": "0.054420",
                            "max": "0.054724",
                            "volume": "348.527",
                            "volumeQuote": "19.011854364"
                          },
                          ...
                        ],
                        "symbol": "ETHBTC",
                        "period": "M30"
                      }
                    }
                    """
                    # Data format notification
                    """
                    {
                      "jsonrpc": "2.0",
                      "method": "updateCandles",
                      "params": {
                        "data": [
                          {
                            "timestamp": "2017-10-19T16:30:00.000Z",
                            "open": "0.054614",
                            "close": "0.054465",
                            "min": "0.054339",
                            "max": "0.054724",
                            "volume": "141.268",
                            "volumeQuote": "7.709353873"
                          }
                        ],
                        "symbol": "ETHBTC",
                        "period": "M30"
                      }
                    }
                    """
                    data = json.loads(response.data)
                    candle = data['params']['data'][0]
                    time = int(datetime.strptime(candle['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ').timestamp())
                    candle = (candle['open'], candle['max'], candle['min'], candle['close'], candle['volume'], time)

                    await self._send_data_in_exchange(queue_name, candle)

    async def _subscribe_depth(self, queue_name, symbol):
        url = f'{self._root_url_rest}/api/2/public/orderbook/{symbol}?limit=20'
        async with ClientSession() as session:
            while True:
                async with session.get(url) as response:
                    response = await response.text()

                    # Data format
                    """
                    {
                      "ask": [
                        {
                          "price": "0.046002",
                          "size": "0.088"
                        },
                        {
                          "price": "0.046800",
                          "size": "0.200"
                        }
                      ],
                      "bid": [
                        {
                          "price": "0.046001",
                          "size": "0.005"
                        },
                        {
                          "price": "0.046000",
                          "size": "0.200"
                        }
                      ],
                      "timestamp": "2018-11-19T05:00:28.193Z"
                    }
                    """

                    bid_ask = json.loads(response)
                    asks = [(item['price'], item['size']) for item in bid_ask['ask']]
                    bids = [(item['price'], item['size']) for item in bid_ask['bid']]
                    asks.reverse()

                    await self._send_data_in_exchange(queue_name, (bids, asks))
                    await asyncio.sleep(self.time_out)
