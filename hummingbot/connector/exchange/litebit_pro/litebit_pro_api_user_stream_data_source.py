#!/usr/bin/env python

import time
import asyncio
import logging
from typing import Optional, List, AsyncIterable, Any

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from .litebit_pro_auth import LitebitProAuth
from .litebit_pro_websocket import LitebitProWebsocket

__all__ = ("LitebitProAPIUserStreamDataSource",)


class LitebitProAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, litebit_pro_auth: LitebitProAuth, trading_pairs: Optional[List[str]] = []):
        self._auth: LitebitProAuth = litebit_pro_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                async for msg in self._listen_to_orders_balances():
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Litebit Pro WebSocket connection. " "Retrying after 30 seconds...",
                    exc_info=True
                )
                await asyncio.sleep(30.0)

    async def _listen_to_orders_balances(self) -> AsyncIterable[Any]:
        """
        Subscribe to active orders via web socket
        """
        ws = LitebitProWebsocket(self._auth)

        try:
            await ws.connect()

            for channel_name in ["balances", "orders"]:
                await ws.subscribe([channel_name])

            async for msg in ws.on_message():
                if msg["event"] in ["balance", "order"]:
                    yield msg

                self._last_recv_time = time.time()
        except Exception as e:
            raise e
        finally:
            await ws.disconnect()
            await asyncio.sleep(5)
