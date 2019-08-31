from cryptoview.base_logic import Observer
from aiohttp import web, WSMsgType
from asyncio import CancelledError
import aiohttp_jinja2
import json

IS_DEBUG = False


@aiohttp_jinja2.template('index.html')
async def index(request):
    return {}


@aiohttp_jinja2.template('chart_page.html')
async def chart_handler(request):
    return {}


async def ws_api_crypto_currency(request):
    """API chart page

    Connect to endpoint ws://{domain}/api/v1/ws

    send json with format:
        {
            action: sub | unsub,
            data_id: data_type.exchange.pair[.time_frame] | listing_info
        }

    data_type: ticket | candles | cup
    exchange, pair, time_frame send with listing_info message

    if 'data_type' = 'candles', need time_frame

    """
    err_bad_action_value = "Bad 'action' value"
    err_not_json = "Message is not JSON format"
    err_bad_msg_format = "In message not needed keys"

    ws = web.WebSocketResponse()
    observer = Observer(ws)

    if not ws.can_prepare(request).ok:
        return
    await ws.prepare(request)
    try:
        while True:
            message = await ws.receive()
            if IS_DEBUG:
                print(message)

            if message.type == WSMsgType.text:
                try:
                    message = json.loads(message.data)
                    if 'action' not in message.keys() or 'data_id' not in message.keys():
                        await ws.send_json(dict(error=err_bad_msg_format))
                        continue

                    if message['action'] == 'sub':
                        await request.app['Aggregator'].attach(observer, message['data_id'])
                    elif message['action'] == 'unsub':
                        await request.app['Aggregator'].detach(observer, message['data_id'])
                    else:
                        await ws.send_json(dict(error=err_bad_action_value))
                except json.JSONDecodeError:
                    await ws.send_json(dict(error=err_not_json))
            else:
                await request.app['Aggregator'].detach(observer)
                return ws
    except CancelledError as e:
        # if socket close without close msg, will raise CancelledError
        await request.app['Aggregator'].detach(observer)
        raise e
