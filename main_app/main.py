from cryptoview.app import create_app
import aiohttp


if __name__ == '__main__':
    app = create_app()
    aiohttp.web.run_app(app, )
