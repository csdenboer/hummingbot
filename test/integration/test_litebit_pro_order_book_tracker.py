#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import time
import asyncio
import logging
import unittest
from typing import Dict, Optional, List
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderBookEvent
from hummingbot.connector.exchange.litebit_pro.litebit_pro_order_book_tracker import LitebitProOrderBookTracker
from hummingbot.connector.exchange.litebit_pro.litebit_pro_api_order_book_data_source import LitebitProAPIOrderBookDataSource
from hummingbot.core.data_type.order_book import OrderBook


class LitebitProOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[LitebitProOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "BTC-EUR",
        "ETH-EUR",
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: LitebitProOrderBookTracker = LitebitProOrderBookTracker(cls.trading_pairs)
        cls.order_book_tracker.start()
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    async def run_parallel_async(self, *tasks, timeout=None):
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        timer = 0
        while not future.done():
            if timeout and timer > timeout:
                raise Exception("Timeout running parallel async tasks in tests")
            timer += 1
            now = time.time()
            _next_iteration = now // 1.0 + 1  # noqa: F841
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def setUp(self):
        self.event_logger = EventLogger()
        for event_tag in self.events:
            for trading_pair, order_book in self.order_book_tracker.order_books.items():
                order_book.add_listener(event_tag, self.event_logger)

    def test_tracker_integrity(self):
        # Wait 5 seconds to process some diffs.
        self.ev_loop.run_until_complete(asyncio.sleep(10.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        eth_eur: OrderBook = order_books["ETH-EUR"]
        self.assertIsNot(eth_eur.last_diff_uid, 0)
        self.assertGreaterEqual(eth_eur.get_price_for_volume(True, 10).result_price,
                                eth_eur.get_price(True))
        self.assertLessEqual(eth_eur.get_price_for_volume(False, 10).result_price,
                             eth_eur.get_price(False))

    def test_api_get_last_traded_prices(self):
        prices = self.ev_loop.run_until_complete(
            LitebitProAPIOrderBookDataSource.get_last_traded_prices(["BTC-EUR", "ETH-EUR"]))
        for key, value in prices.items():
            print(f"{key} last_trade_price: {value}")
        self.assertGreater(prices["BTC-EUR"], 1000)
        self.assertGreater(prices["ETH-EUR"], 300)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
