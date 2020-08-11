from exchanges.abstract_exchange import BaseExchange
from aiohttp import ClientSession
import datetime
import asyncio
import json


class Bittrex(BaseExchange):
    """Connector to Bittrex (Use api v3)"""

    name = 'Bittrex'

    def __init__(self, mq_exchanger):
        super().__init__(mq_exchanger)
        self._root_url_rest = 'https://api.bittrex.com'

        # Key this unification view for this MS, value dict this variable for API exchange
        self._timeframe_translate = dict([('M1', 'MINUTE_1'), ('M5', 'MINUTE_5'), ('H1', 'HOUR_1'), ('D1', 'DAY_1')])
        self.access_timeframes = list(self._timeframe_translate.keys())

    async def _get_access_symbols(self):
        async with ClientSession() as session:
            url = f'{self._root_url_rest}/v3/markets'
            async with session.get(url) as response:
                response = await response.text()

                # Data format
                """
                [
                  {
                    "symbol": "string",
                    "baseCurrencySymbol": "string",
                    "quoteCurrencySymbol": "string",
                    "minTradeSize": "number (double)",
                    "precision": "integer (int32)",
                    "status": "string",
                    "createdAt": "string (date-time)",
                    "notice": "string"
                  }
                ]
                """

                try:
                    response = json.loads(response)
                    symbols = [item['symbol'].replace('-', '') for item in response]
                except (KeyError, TypeError, json.JSONDecodeError):
                    return []

                return symbols

    async def _get_starting_ticker(self, queue_name, symbol):
        async with ClientSession() as session:
            url = f'{self._root_url_rest}/v3/markets/{(await self._symbol_translate(symbol, session))}/ticker'
            async with session.get(url) as response:
                response = await response.text()
                bid_ask = json.loads(response)

                # Data format
                """
                {
                  "symbol": "string",
                  "lastTradeRate": "number (double)",
                  "bidRate": "number (double)",
                  "askRate": "number (double)"
                }
                """

                bid_ask = (bid_ask['bidRate'], bid_ask['askRate'])
                await self._send_data_in_exchange(queue_name, bid_ask)

    async def _get_starting_candles(self, queue_name, symbol, time_frame):
        async with ClientSession() as session:
            url_rest = f'{self._root_url_rest}/v3/markets/{(await self._symbol_translate(symbol, session))}' \
                f'/candles?CandleInterval={self._timeframe_translate[time_frame]}'
            async with session.get(url_rest) as response:
                response = await response.text()

                # Data format
                """
                [
                  {
                    "startsAt": "string (date-time)",
                    "open": "number (double)",
                    "high": "number (double)",
                    "low": "number (double)",
                    "close": "number (double)",
                    "volume": "number (double)",
                    "baseVolume": "number (double)"
                  }
                ]
                """

                candles = []
                candles_data = json.loads(response)

                for item in candles_data:
                    time = int(datetime.datetime.strptime(item['startsAt'], "%Y-%m-%dT%H:%M:%fZ").timestamp())
                    candles.append((item['open'], item['high'], item['low'], item['close'], item['volume'],
                                    time))

                await self._send_data_in_exchange(queue_name, candles)

    async def _get_starting_depth(self, queue_name, symbol):
        async with ClientSession() as session:
            url = f'{self._root_url_rest}/v3/markets/{(await self._symbol_translate(symbol, session))}/orderbook'
            async with session.get(url) as response:
                response = await response.text()
                bid_ask = json.loads(response)

                # Data format
                """
                {
                  "bid": [
                    {
                      "quantity": "number (double)",
                      "rate": "number (double)"
                    }
                  ],
                  "ask": [
                    {
                      "quantity": "number (double)",
                      "rate": "number (double)"
                    }
                  ]
                }
                """

                asks = [(item['rate'], item['quantity']) for item in bid_ask['ask']][:20]
                bids = [(item['rate'], item['quantity']) for item in bid_ask['bid']][:20]
                asks.reverse()

                await self._send_data_in_exchange(queue_name, (bids, asks))

    async def _subscribe_ticker(self, queue_name, symbol):
        async with ClientSession() as session:
            url = f'{self._root_url_rest}/v3/markets/{(await self._symbol_translate(symbol, session))}/ticker'
            while True:
                async with session.get(url) as response:
                    response = await response.text()
                    bid_ask = json.loads(response)

                    # Data format
                    """
                    {
                      "symbol": "string",
                      "lastTradeRate": "number (double)",
                      "bidRate": "number (double)",
                      "askRate": "number (double)"
                    }
                    """

                    bid_ask = (bid_ask['bidRate'], bid_ask['askRate'])
                    await self._send_data_in_exchange(queue_name, bid_ask)
                    await asyncio.sleep(self.time_out)

    async def _subscribe_candles(self, queue_name, symbol, time_frame):
        async with ClientSession() as session:
            url_rest = f'{self._root_url_rest}/v3/markets/{(await self._symbol_translate(symbol, session))}' \
                f'/candles?CandleInterval={self._timeframe_translate[time_frame]}'
            while True:
                async with session.get(url_rest) as response:
                    response = await response.text()

                    # Data format
                    """
                    [
                      {
                        "startsAt": "string (date-time)",
                        "open": "number (double)",
                        "high": "number (double)",
                        "low": "number (double)",
                        "close": "number (double)",
                        "volume": "number (double)",
                        "baseVolume": "number (double)"
                      }
                    ]
                    """

                    candle = json.loads(response)[-1]

                    time = int(datetime.datetime.strptime(candle['startsAt'], "%Y-%m-%dT%H:%M:%fZ").timestamp())
                    candle = (candle['open'], candle['high'], candle['low'], candle['close'], candle['volume'], time)

                    await self._send_data_in_exchange(queue_name, candle)
                    await asyncio.sleep(self.time_out)

    async def _subscribe_depth(self, queue_name, symbol):
        async with ClientSession() as session:
            url = f'{self._root_url_rest}/v3/markets/{(await self._symbol_translate(symbol, session))}/orderbook'
            while True:
                async with session.get(url) as response:
                    response = await response.text()
                    bid_ask = json.loads(response)

                    # Data format
                    """
                    {
                      "bid": [
                        {
                          "quantity": "number (double)",
                          "rate": "number (double)"
                        }
                      ],
                      "ask": [
                        {
                          "quantity": "number (double)",
                          "rate": "number (double)"
                        }
                      ]
                    }
                    """

                    asks = [(item['rate'], item['quantity']) for item in bid_ask['ask']][:20]
                    bids = [(item['rate'], item['quantity']) for item in bid_ask['bid']][:20]
                    asks.reverse()

                    await self._send_data_in_exchange(queue_name, (bids, asks))
                    await asyncio.sleep(self.time_out)

    async def _symbol_translate(self, symbol, session):
        url = f'{self._root_url_rest}/v3/markets'
        async with session.get(url) as response:
            response = await response.text()
            response = json.loads(response)

            # Data format
            """
            [
              {
                "symbol": "string",
                "baseCurrencySymbol": "string",
                "quoteCurrencySymbol": "string",
                "minTradeSize": "number (double)",
                "precision": "integer (int32)",
                "status": "string",
                "createdAt": "string (date-time)",
                "notice": "string"
              }
            ]
            """

            for item in response:
                if item['symbol'].replace('-', '') == symbol:
                    return item['symbol']
