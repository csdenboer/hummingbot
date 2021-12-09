#!/usr/bin/env python

import sys
import asyncio
import logging
import unittest
import conf

from os.path import join, realpath
from hummingbot.connector.exchange.litebit_pro.litebit_pro_user_stream_tracker import LitebitProUserStreamTracker
from hummingbot.connector.exchange.litebit_pro.litebit_pro_auth import LitebitProAuth
from hummingbot.core.utils.async_utils import safe_ensure_future

sys.path.insert(0, realpath(join(__file__, "../../../")))


class LitebitProUserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.litebit_pro_api_key
    secret_key = conf.litebit_pro_secret_key

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.litebit_pro_auth = LitebitProAuth(cls.api_key, cls.secret_key)
        cls.trading_pairs = ["BTC-EUR"]
        cls.user_stream_tracker: LitebitProUserStreamTracker = LitebitProUserStreamTracker(
            litebit_pro_auth=cls.litebit_pro_auth, trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
