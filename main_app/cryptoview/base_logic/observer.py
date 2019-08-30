class Observer:

    def __init__(self, ws):
        self.ws = ws

    async def update(self, data):
        await self.ws.send_json(data)
