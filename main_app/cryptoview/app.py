from .base_logic import CryptoCurrencyAggregator
from .urls import setup_routes
from aiohttp import web
import aiohttp_jinja2
import asyncio
import jinja2


async def create_app():
    app = web.Application()

    app['Aggregator'] = CryptoCurrencyAggregator()
    asyncio.get_event_loop().set_debug(True)
    asyncio.get_event_loop().create_task(app['Aggregator'].run())

    aiohttp_jinja2.setup(app, loader=jinja2.PackageLoader('cryptoview', 'templates'))
    setup_routes(app)

    return app
