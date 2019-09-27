class Observer:

    def __init__(self, ws):
        """:param ws: WebSocket"""
        self.ws = ws

    async def update(self, data):
        await self.ws.send_json(data)
