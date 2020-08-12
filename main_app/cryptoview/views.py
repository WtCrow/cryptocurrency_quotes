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

    Connect to endpoint ws://{domain}/api/v1/ws

    send JSON with format:
        {
            action: sub | unsub,
            data_id: data_type.exchange.pair[.time_frame] | listing_info
        }

    data_type: ticket | candles | cup
    valid values for exchange, pair and time_frame you can request by listing_info data_id

    if 'data_type' = 'candles', need add time_frame

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
