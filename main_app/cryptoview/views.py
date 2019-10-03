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

    send json with format:
        {
            action: sub | unsub,
            data_id: data_type.exchange.pair[.time_frame] | listing_info
        }

    data_type: ticket | candles | cup
    good values exchange, pair, time_frame you can get in response listing_info message

    if 'data_type' = 'candles', need add time_frame

    """
    err_bad_action_value = "Bad 'action' value"
    err_not_json = "Message is not JSON format"
    err_bad_msg_format = "In message not needed keys"

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
                    action = message.get('action', '')
                    data_id = message.get('data_id', '')

                    if not action or not data_id:
                        await ws.send_json(dict(error=err_bad_msg_format))
                        continue

                    if action == 'sub':
                        await request.app['Aggregator'].attach(observer, data_id)
                    elif action == 'unsub':
                        await request.app['Aggregator'].detach(observer, data_id)
                    else:
                        await ws.send_json(dict(error=err_bad_action_value))
                except json.JSONDecodeError:
                    await ws.send_json(dict(error=err_not_json))
            else:
                await request.app['Aggregator'].detach(observer)
                return ws
    except CancelledError as e:
        await request.app['Aggregator'].detach(observer)
        raise e