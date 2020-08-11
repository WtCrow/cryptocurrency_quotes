from exchanges.abstract_exchange import BaseExchange
from aiohttp import ClientSession
import datetime
import hashlib
import gzip
import json


class HuobiGlobal(BaseExchange):
    """Connector to Huobi_Global"""

    name = 'Huobi_Global'

    def __init__(self, mq_exchanger):
        super().__init__(mq_exchanger)
        self._max_candle = 2000

        self._root_url_rest = 'http://api.huobi.pro'
        self._root_url_ws = 'wss://api.huobi.pro/ws'

        # Key this unification view for this MS, value dict this variable for API exchange
        self._timeframe_translate = dict([('M1', '1min'), ('M5', '5min'), ('M15', '15min'), ('M30', '30min'),
                                          ('H1', '60min'), ('D1', '1day'), ('1W', '1week'), ('1M', '1mon'),
                                          ('1Y', '1year')])
        self.access_timeframes = list(self._timeframe_translate.keys())

    async def _get_access_symbols(self):
        async with ClientSession() as session:
            rest_url = f'{self._root_url_rest}/v1/common/symbols'
            async with session.get(rest_url) as response:
                response = await response.text()

                # Data format
                """
                {
                  "status":"ok",
                  "data":
                  [
                   {
                     "base-currency":"eko",
                     "quote-currency":"btc",
                     "price-precision":10,
                     "amount-precision":2,
                     "symbol-partition":"innovation",
                     "symbol":"ekobtc","state":"online",
                     "value-precision":8,"min-order-amt":1,
                     "max-order-amt":10000000,
                     "min-order-value":0.0001
                   },
                   {...}, ...
                  ]
                """

                try:
                    response = json.loads(response)['data']
                    symbols = [item['base-currency'].upper() + item['quote-currency'].upper() for item in response]
                except (KeyError, TypeError, json.JSONDecodeError):
                    return []

                return symbols

    async def _get_starting_ticker(self, queue_name, symbol):
        async with ClientSession() as session:
            rest_url = f'{self._root_url_rest}/market/detail/merged?symbol={symbol.lower()}'
            async with session.get(rest_url) as response:
                response = await response.text()

                # Data format
                """
                "tick": {
                    "id":  
                    "amount":  
                    "count":  
                    "open":  
                    "close": Closing price.If this is a latest kline,this shows the current price
                    "low":  
                    "high":  
                    "vol":  volume
                    "bid": [bid1 price, volume],
                    "ask": [ask1 price, volume]
                  }
                """

                response = json.loads(response)['tick']
                ticker = str(response['bid'][0]), str(response['ask'][0])

                await self._send_data_in_exchange(queue_name, ticker)

    async def _get_starting_candles(self, queue_name, symbol, time_frame):
        async with ClientSession() as session:
            url_rest = f'{self._root_url_rest}/market/history/kline?symbol={symbol.lower()}' \
                f'&period={self._timeframe_translate[time_frame]}&size={self._max_candle}'
            async with session.get(url_rest) as response:
                response = await response.text()
                candles = []
                response = json.loads(response)

                # Data format
                """
                "data": [
                {
                    "id": kline id,
                    "amount": trading amount,
                    "count": 
                    "open": Open price,
                    "close": Closing price.If this is a latest kline,this shows the current price
                    "low":  
                    "high": 
                    "vol": volume
                  }
                ]
                """

                for item in response['data']:
                    time = int(item['id'])
                    candles.append((str(item['open']), str(item['high']), str(item['low']),
                                    str(item['close']), str(item['vol']), time))
                candles.reverse()
                await self._send_data_in_exchange(queue_name, candles)

    async def _get_starting_depth(self, queue_name, symbol):
        async with ClientSession() as session:
            rest_url = f'{self._root_url_rest}/market/depth?symbol={symbol.lower()}&type=step1'
            async with session.get(rest_url) as response:
                response = await response.text()

                # Data format
                """
                "tick": {
                    "id": 
                    "ts": millisecond,
                    "bids":  [price , amount ] 
                    "asks":  [price , amount ] 
                  }
                """

                response = json.loads(response)['tick']

                bids = [(str(item[0]), str(item[1])) for item in response['bids']][:20]
                asks = [(str(item[0]), str(item[1])) for item in response['asks']][:20]
                asks.reverse()

                await self._send_data_in_exchange(queue_name, (bids, asks))

    async def _subscribe_ticker(self, queue_name, symbol):
        async with ClientSession() as session:
            async with session.ws_connect(self._root_url_ws) as ws:

                id_ = hashlib.md5("huobi_ticker".encode('utf-8')).hexdigest()
                json_params = {
                    "sub": f'market.{symbol.lower()}.depth.step0',
                    "id": id_
                }
                await ws.send_json(json_params)

                while True:
                    response = await ws.receive()
                    response = json.loads(gzip.decompress(response.data).decode("utf-8"))

                    if 'ping' in response.keys():
                        json_params = json.dumps(dict(pong=str(datetime.datetime.utcnow())))
                        await ws.send_json(json_params)
                        continue
                    elif 'status' in response.keys():
                        if response['status'] != 'ok':
                            await self._send_error_message(queue_name, response)
                            return
                        else:
                            continue
                    else:

                        # Data format
                        """
                        {
                          'ch': 'market.btcusdt.depth.step0', 'ts': 1565436814043,
                          'tick':
                            {
                              'bids':
                              [[11460.01, 0.056187], [11460.0, 42.330615], [11459.93, 0.050624], [11457.22, 0.05], ...],
                              'asks':
                              [[...], [...], ...]
                            }
                        """

                        tick = response['tick']
                        bid_ask = (str(tick['bids'][0][0]), str(tick['asks'][0][0]))

                    await self._send_data_in_exchange(queue_name, bid_ask)

    async def _subscribe_candles(self, queue_name, symbol, time_frame):
        async with ClientSession() as session:
            async with session.ws_connect(self._root_url_ws) as ws:

                id_ = hashlib.md5("huobi_candle".encode('utf-8')).hexdigest()
                json_params = {
                    "sub": f"market.{symbol.lower()}.kline.{self._timeframe_translate[time_frame]}",
                    "id": id_
                }
                await ws.send_json(json_params)

                while True:
                    response = await ws.receive()
                    response = json.loads(gzip.decompress(response.data).decode("utf-8"))

                    if 'ping' in response.keys():
                        json_params = json.dumps(dict(pong=str(datetime.datetime.utcnow())))
                        await ws.send_json(json_params)
                        continue
                    elif 'status' in response.keys():
                        if response['status'] != 'ok':
                            await self._send_error_message(queue_name, response)
                            return
                        else:
                            continue
                    else:

                        # Data format
                        """
                        {'ch': 'market.btcusdt.kline.1min', 'ts': 1565437380662,
                            'tick':
                                {
                                    'id': 1565437380,
                                    'open': 11404.66,
                                    'close': 11403.44,
                                    'low': 11403.44,
                                    'high': 11404.7,
                                    'amount': 1.530531,
                                    'vol': 17454.0186904,
                                    'count': 7
                                }
                        }
                        """

                        response = response['tick']
                        time = response['id']
                        candle = (str(response['open']), str(response['high']), str(response['low']),
                                  str(response['close']), str(response['vol']), time)

                    await self._send_data_in_exchange(queue_name, candle)

    async def _subscribe_depth(self, queue_name, symbol):
        async with ClientSession() as session:
            async with session.ws_connect(self._root_url_ws) as ws:

                id_ = hashlib.md5("huobi_depth".encode('utf-8')).hexdigest()
                json_params = {
                    "sub": f'market.{symbol.lower()}.depth.step1',
                    "id": id_
                }
                await ws.send_json(json_params)

                while True:
                    response = await ws.receive()
                    data = json.loads(gzip.decompress(response.data).decode("utf-8"))

                    if 'ping' in data.keys():
                        json_params = json.dumps(dict(pong=str(datetime.datetime.utcnow())))
                        await ws.send_json(json_params)
                        continue
                    elif 'status' in data.keys():
                        if data['status'] != 'ok':
                            await self._send_error_message(queue_name, response)
                            return
                        else:
                            continue
                    else:

                        # Data format
                        """
                        {
                          'ch': 'market.btcusdt.depth.step0', 'ts': 1565436814043,
                          'tick':
                            {
                              'bids':
                              [[11460.01, 0.056187], [11460.0, 42.330615], [11459.93, 0.050624], 
                              [11457.22, 0.05], ...],
                              'asks':
                              [[...], [...], ...]
                            }
                        """

                        bid_ask = data['tick']
                        bids = [(str(item[0]), str(item[1])) for item in bid_ask['bids']][:20]
                        asks = [(str(item[0]), str(item[1])) for item in bid_ask['asks']][:20]
                    asks.reverse()
                    await self._send_data_in_exchange(queue_name, (bids, asks))
