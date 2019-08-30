from cryptoview.views.handlers import index, ws_api_crypto_currency
from pathlib import Path
from aiohttp import web


def setup_routes(app):
    urlpatterns = [
        web.get('/', index),
        web.get('/api/v1/ws', ws_api_crypto_currency),
    ]
    app.router.add_routes(urlpatterns)

    path_to_static_dir = Path(__file__).parents[0] / 'static_files'
    app.router.add_static('/', path_to_static_dir / 'main_page')
