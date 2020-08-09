class Observer:

    def __init__(self, ws):
        """:param ws: WebSocket connection"""
        self.ws = ws

    async def update(self, data):
        """Send new data to ws"""
        await self.ws.send_json(data)
