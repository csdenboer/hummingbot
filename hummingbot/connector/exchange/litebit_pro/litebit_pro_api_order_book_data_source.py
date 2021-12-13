#!/usr/bin/env python
import asyncio
import logging
import time
import aiohttp
import pandas as pd
import hummingbot.connector.exchange.litebit_pro.litebit_pro_constants as constants

from typing import Optional, List, Dict, Any
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from . import litebit_pro_utils
from .litebit_pro_active_order_tracker import LitebitProActiveOrderTracker
from .litebit_pro_order_book import LitebitProOrderBook
from .litebit_pro_websocket import LitebitProWebsocket


class LitebitProAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{constants.REST_URL}/v1/markets", timeout=10) as response:
                if response.status == 200:
                    try:
                        data: List[dict] = await response.json()
                        return [litebit_pro_utils.convert_from_exchange_trading_pair(item["market"]) for item in
                                data]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs
                return []

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        result = {}
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{constants.REST_URL}/v1/tickers")
            resp_json = await resp.json()
            for t_pair in trading_pairs:
                ticker = next((ticker for ticker in resp_json if
                               ticker["market"] == litebit_pro_utils.convert_to_exchange_trading_pair(t_pair)), None)
                if ticker is not None:
                    result[t_pair] = float(ticker["last"])
        return result

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self._get_order_book_data(trading_pair)
        snapshot_msg: OrderBookMessage = LitebitProOrderBook.snapshot_message_from_exchange(
            snapshot,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: LitebitProActiveOrderTracker = LitebitProActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        # TODO: we currently don't have a websocket subscription for this
        pass

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        while True:
            try:
                ws = LitebitProWebsocket()
                await ws.connect()

                for pair in self._trading_pairs:
                    await ws.subscribe([f"book:{litebit_pro_utils.convert_to_exchange_trading_pair(pair)}"])

                async for message in ws.on_message():
                    if message["event"] == "book" and message["data"]["update_type"] == "delta":
                        order_book_msg: OrderBookMessage = LitebitProOrderBook.diff_message_from_exchange(
                            message["data"], metadata={"trading_pair": litebit_pro_utils.convert_from_exchange_trading_pair(
                                message["data"]["market"]
                            )}
                        )
                        output.put_nowait(order_book_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                await asyncio.sleep(30.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self._get_order_book_data(trading_pair)
                        snapshot_msg: OrderBookMessage = LitebitProOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above API rate limits.
                        await asyncio.sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection."
                        )
                        await asyncio.sleep(5.0)
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)

    @staticmethod
    async def _get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        async with aiohttp.ClientSession() as client:
            order_book_response = await client.get(
                f"{constants.REST_URL}/v1/book",
                params={"market": litebit_pro_utils.convert_to_exchange_trading_pair(trading_pair)}
            )

            if order_book_response.status != 200:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {constants.EXCHANGE_NAME}. "
                    f"HTTP status is {order_book_response.status}."
                )

            orderbook_data: Dict[str, Any] = await safe_gather(order_book_response.json())

        return orderbook_data[0]
