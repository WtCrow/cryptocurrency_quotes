from pathlib import Path
from .views import *


def setup_routes(app):
    urlpatterns = [
        web.get('/', index),
        web.get('/chart', chart_handler),
        web.get('/api/v1/ws', ws_api_crypto_currency),
    ]
    app.router.add_routes(urlpatterns)

    path_to_static_dir = Path(__file__).parents[0] / 'static'
    app.router.add_static('/', path_to_static_dir)
