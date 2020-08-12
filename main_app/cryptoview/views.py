from cryptoview.backend import Observer
from aiohttp import web, WSMsgType
from asyncio import CancelledError
import aiohttp_jinja2
import json


@aiohttp_jinja2.template('index.html')
async def index(request):
    """Main page"""
    return {}


@aiohttp_jinja2.template('chart_page.html')
async def chart_handler(request):
    """Chart page"""
    return {}


async def ws_api_crypto_currency(request):
    """API for get market data

    --------
    Request:
    Connect to endpoint ws://{domain}/api/v1/ws

    send JSON with format:
        {
            action: sub | unsub,
            data_id: data_type.exchange.pair[.time_frame] | listing_info
        }

    If requested listing_info, will send information about exchanges, symbols and timeframes

    data_type.exchange.pair[.time_frame]:
        data_type: ticket | candles | cup
        valid values for exchange, pair and time_frame you can request by listing_info data_id

    if 'data_type' = 'candles', need add time_frame

    --------
    Response:
    JSON {data, data_id}
    'data_id' equal 'listing_info' or contain 4-5 item, separated pointers
    0) msg_type - start value (first message) or update (update | starting)
    1) data_type - ticker, candles, depth
    2, 3, 4) exchange, pair, time_frame - requested cryptocurrency params (timeframe only for candles data_type)

    Key 'data':
    Listing information:
    {
        exchange_name_1: [[access_timeframes_array], [access_pairs_array]],
        exchange_name_2: [[access_timeframes_array], [access_pairs_array]],
        ...
    }
    Market data:
        First message (starting):
            ticker:
                array with 2 string numbers bid and ask
            candles:
                array OHLCV-candles
                Candle array format: [open: : str(float), high: : str(float), low: str(float), close: str(float),
                                      volume: str(float), time: int (unix_time)]
                sort by time ASC (1, 2, 3, 4 ...)
            depth:
                array, that contain 2 arrays
                [bid_arr, ask_arr]
                [ [[price: str(float), volume: str(float)], [price, volume], ...], [[price, volume], [price, volume], ...]]

                prices sorted
                bids[i][0] > bids[i + 1][0]
                asks[i][0] > asks[i + 1][0]
        Update message (update):
            ticker:
                array with 2 string numbers bid and ask
            candles:
                One new candle
                Candle array format: [open: : str(float), high: : str(float), low: str(float), close: str(float),
                                      volume: str(float), time: int (unix_time)]
            depth:
                array, that contain 2 arrays
                [bid_arr, ask_arr]
                [ [[price: str(float), volume: str(float)], [price, volume], ...], [[price, volume], [price, volume], ...]]

                prices sorted
                bids[i][0] > bids[i + 1][0]
                asks[i][0] > asks[i + 1][0]

    """
    ERR_BAD_ACTION = "Bad 'action' value"
    ERR_NOT_JSON = "Message is not JSON format"
    ERR_NOT_FULL_REQUEST = "In message not needed keys"

    ws = web.WebSocketResponse()
    observer = Observer(ws)

    if not ws.can_prepare(request).ok:
        return
    await ws.prepare(request)

    # if socket close without close msg, will raise CancelledError
    try:
        while True:
            message = await ws.receive()

            if message.type == WSMsgType.text:
                try:
                    message = json.loads(message.data)
                    action = message.get('action')
                    data_id = message.get('data_id')

                    if not action or not data_id:
                        await ws.send_json(dict(error=ERR_NOT_FULL_REQUEST))
                        continue

                    if action == 'sub':
                        await request.app['Aggregator'].attach(observer, data_id)
                    elif action == 'unsub':
                        await request.app['Aggregator'].detach(observer, data_id)
                    else:
                        await ws.send_json(dict(error=ERR_BAD_ACTION))
                except json.JSONDecodeError:
                    await ws.send_json(dict(error=ERR_NOT_JSON))
            else:
                await request.app['Aggregator'].detach(observer)
                return ws
    except CancelledError as e:
        await request.app['Aggregator'].detach(observer)
        raise e
