#!/usr/bin/env python
import asyncio
import copy
import hashlib
import hmac
import logging
import time
from typing import Optional, AsyncIterable, Any, List

import websockets
from websockets.exceptions import ConnectionClosed
import ujson

import hummingbot.connector.exchange.litebit_pro.litebit_pro_constants as constants
from hummingbot.connector.exchange.litebit_pro.litebit_pro_auth import LitebitProAuth
from hummingbot.logger import HummingbotLogger

__all__ = ("LitebitProWebsocket",)


class LitebitProWebsocket:
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: Optional[LitebitProAuth] = None):
        self._auth = auth
        self._ws_url = constants.WSS_URL
        self._client: Optional[websockets.WebSocketClientProtocol] = None

    # connect to exchange
    async def connect(self):
        try:
            self._client = await websockets.connect(self._ws_url)

            if self._auth is not None:
                await self._authenticate()
                # wait for response
                await asyncio.sleep(1)

            return self._client
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)

    # disconnect from exchange
    async def disconnect(self):
        if self._client is None:
            return

        await self._client.close()

    # receive & parse messages
    async def _messages(self) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    raw_msg_str: str = await asyncio.wait_for(self._client.recv(), timeout=self.MESSAGE_TIMEOUT)
                    raw_msg = ujson.loads(raw_msg_str)
                    yield raw_msg
                except asyncio.TimeoutError:
                    await asyncio.wait_for(self._client.ping(), timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await self.disconnect()

    # emit messages
    async def _emit(self, event: str, data: Optional[Any] = None):
        if data is None:
            data = {}

        payload = {
            "event": event,
            "data": copy.deepcopy(data),
        }

        await self._client.send(ujson.dumps(payload))

    # request via websocket
    async def request(self, method: str, data: Optional[Any] = None):
        if data is None:
            data = {}

        await self._emit(method, data)

    # subscribe to a method
    async def subscribe(self, channels: List[str]):
        await self.request("subscribe", channels)

    # unsubscribe to a method
    async def unsubscribe(self, channels: List[str]):
        await self.request("unsubscribe", channels)

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            if msg["event"] not in ["authenticate"]:
                yield msg

    async def _authenticate(self):
        timestamp = int(time.time() * 1000)
        signature = self._calculate_signature("authenticate" + str(timestamp), self._auth.secret_key)

        await self.request("authenticate", {
            "api_key": self._auth.api_key,
            "timestamp": timestamp,
            "signature": signature,
        })

    @classmethod
    def _calculate_signature(cls, data: str, secret: str) -> str:
        signature = hmac.new(
            secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
        )
        return signature.hexdigest()
