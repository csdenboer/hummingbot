import asyncio
import unittest
from typing import List

import conf
from hummingbot.connector.exchange.litebit_pro.litebit_pro_auth import LitebitProAuth
from hummingbot.connector.exchange.litebit_pro.litebit_pro_websocket import LitebitProWebsocket


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.litebit_pro_api_key
        secret_key = conf.litebit_pro_secret_key
        cls.auth = LitebitProAuth(api_key, secret_key)
        cls.ws = LitebitProWebsocket(cls.auth)

    async def con_auth(self):
        await self.ws.connect()
        await self.ws.subscribe(["balances"])

        async for response in self.ws.on_message():
            if response.get("event") == "subscribe":
                return response

    def test_auth(self):
        result: List[str] = self.ev_loop.run_until_complete(self.con_auth())
        assert result["event"] == "subscribe"
