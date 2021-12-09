from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../../../")))

from hummingbot.core.mock_api.mock_web_server import MockWebServer
from hummingbot.core.mock_api.mock_web_socket_server import MockWebSocketServerFactory

from unittest import mock

from hummingbot.connector.exchange.litebit_pro import litebit_pro_constants

import asyncio
import logging
from decimal import Decimal
import unittest
import contextlib
import time
import os
from typing import List, Optional
import conf

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    OrderCancelledEvent, TradeFee, TradeType
)
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.trade_fill import TradeFill
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.connector.exchange.litebit_pro.litebit_pro_exchange import LitebitProExchange
from test.connector.exchange.litebit_pro.fixture_litebit_pro import FixtureLitebitPro

logging.basicConfig(level=METRICS_LOG_LEVEL)

API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.litebit_pro_api_key
SECRET_KEY = "XXX" if API_MOCK_ENABLED else conf.litebit_pro_secret_key
BASE_API_URL = "api.pro.litebit.com"


class LitebitProExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]
    connector: LitebitProExchange
    event_logger: EventLogger
    trading_pair = "BTC-EUR"
    base_token, quote_token = trading_pair.split("-")
    stack: contextlib.ExitStack
    base_api_url = BASE_API_URL

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.ev_loop = asyncio.get_event_loop()

        if API_MOCK_ENABLED:
            # TODO: fix for litebit
            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(cls.base_api_url, ["/api/v2/time", "/api/v2/markets", "/api/v2/book"])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response("get", cls.base_api_url, "/api/v2/balances", FixtureLitebitPro.BALANCES)
            cls.web_app.update_response("get", cls.base_api_url, "/api/v2/markets",
                                        FixtureLitebitPro.MARKETS)
            cls.web_app.update_response("get", cls.base_api_url, "/api/v2/fee",
                                        FixtureLitebitPro.TRADE_FEES)
            cls.web_app.update_response("get", cls.base_api_url, "/api/v2/tickers",
                                        FixtureLitebitPro.TICKERS)
            cls.web_app.update_response("get", cls.base_api_url, "/api/v2/order", {})
            cls.web_app.update_response("delete", cls.base_api_url, "/api/v2/orders", {})

            MockWebSocketServerFactory.start_new_server(litebit_pro_constants.WSS_URL)
            cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
            cls._ws_mock = cls._ws_patcher.start()
            cls._ws_mock.side_effect = MockWebSocketServerFactory.reroute_ws_connect

            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.litebit_pro.litebit_pro_utils.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.connector: LitebitProExchange = LitebitProExchange(
            litebit_pro_api_key=API_KEY,
            litebit_pro_secret_key=SECRET_KEY,
            trading_pairs=[cls.trading_pair],
            trading_required=True
        )
        print("Initializing Litebit Pro market... this will take about a minute.")
        cls.clock.add_iterator(cls.connector)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
            cls._req_patcher.stop()
            cls._ws_patcher.stop()
            cls._t_nonce_patcher.stop()

    @classmethod
    async def wait_til_ready(cls, connector=None):
        if connector is None:
            connector = cls.connector
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../connector_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.event_logger = EventLogger()
        for event_tag in self.events:
            self.connector.add_listener(event_tag, self.event_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.connector.remove_listener(event_tag, self.event_logger)
        self.event_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        maker_buy_trade_fee: TradeFee = self.connector.get_fee("BTC", "EUR", OrderType.LIMIT_MAKER, TradeType.BUY,
                                                               Decimal(1), Decimal(4000))
        self.assertGreater(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: TradeFee = self.connector.get_fee("BTC", "EUR", OrderType.LIMIT, TradeType.BUY, Decimal(1))
        self.assertGreater(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.connector.get_fee("BTC", "EUR", OrderType.LIMIT, TradeType.SELL, Decimal(1),
                                                          Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.connector.get_fee("BTC", "EUR", OrderType.LIMIT_MAKER, TradeType.SELL,
                                                          Decimal(1),
                                                          Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_limit_buy(self):
        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.05")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.001"))

        order_id = self._place_order(True, self.trading_pair, amount, OrderType.LIMIT, price, 1,
                                     FixtureLitebitPro.OPEN_BUY_LIMIT_ORDER, FixtureLitebitPro.WS_AFTER_LIMIT_BUY)

        order_completed_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCompletedEvent))
        self.ev_loop.run_until_complete(asyncio.sleep(2))
        trade_events = [t for t in self.event_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(amount, order_completed_event.base_asset_amount)
        self.assertEqual("BTC", order_completed_event.base_asset)
        self.assertEqual("EUR", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.event_logger.event_log]))

    def test_limit_sell(self):
        # Try to sell back the same amount to the exchange, and watch for completion event.
        price = self.connector.get_price(self.trading_pair, True) * Decimal("0.95")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.001"))
        order_id = self._place_order(False, self.trading_pair, amount, OrderType.LIMIT, price, 2,
                                     FixtureLitebitPro.OPEN_SELL_LIMIT_ORDER, FixtureLitebitPro.WS_AFTER_LIMIT_SELL)
        order_completed_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))
        trade_events = [t for t in self.event_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(amount, order_completed_event.base_asset_amount)
        self.assertEqual("BTC", order_completed_event.base_asset)
        self.assertEqual("EUR", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.event_logger.event_log]))

    def test_limit_maker_rejections(self):
        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.2")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.001"))
        cl_order_id = self._place_order(True, self.trading_pair, amount, OrderType.LIMIT_MAKER, price, 1,
                                        FixtureLitebitPro.OPEN_BUY_LIMIT_ORDER,
                                        FixtureLitebitPro.WS_AFTER_LIMIT_BUY_CANCEL)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(cl_order_id, event.order_id)

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price = self.connector.get_price(self.trading_pair, False) * Decimal("0.8")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.001"))
        cl_order_id = self._place_order(False, self.trading_pair, amount, OrderType.LIMIT_MAKER, price, 2,
                                        FixtureLitebitPro.OPEN_SELL_LIMIT_ORDER,
                                        FixtureLitebitPro.WS_AFTER_LIMIT_SELL_CANCEL)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(cl_order_id, event.order_id)

    def test_limit_makers_unfilled(self):
        price = self.connector.get_price(self.trading_pair, True) * Decimal("0.8")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.001"))

        buy_id = self._place_order(True, self.trading_pair, amount, OrderType.LIMIT_MAKER, price, 1,
                                   FixtureLitebitPro.OPEN_BUY_LIMIT_ORDER)
        order_created_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(buy_id, order_created_event.order_id)

        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.2")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, 1)

        sell_id = self._place_order(False, self.trading_pair, amount, OrderType.LIMIT_MAKER,
                                    price, 2,
                                    FixtureLitebitPro.OPEN_SELL_LIMIT_ORDER)
        [sell_order_created_event] = self.run_parallel(self.event_logger.wait_for(SellOrderCreatedEvent))
        sell_order_created_event: BuyOrderCreatedEvent = sell_order_created_event
        self.assertEqual(sell_id, sell_order_created_event.order_id)

        if API_MOCK_ENABLED:
            message = FixtureLitebitPro.WS_AFTER_LIMIT_BUY.copy()
            message["data"]["client_id"] = buy_id
            MockWebSocketServerFactory.send_json_threadsafe(litebit_pro_constants.WSS_URL, message, delay=0.1)

            message = FixtureLitebitPro.WS_AFTER_LIMIT_SELL.copy()
            message["data"]["client_id"] = sell_id
            MockWebSocketServerFactory.send_json_threadsafe(litebit_pro_constants.WSS_URL, message, delay=0.1)

        [cancellation_results] = self.run_parallel(self.connector.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_cancel_all(self):
        bid_price: Decimal = self.connector.get_price(self.trading_pair, True)
        ask_price: Decimal = self.connector.get_price(self.trading_pair, False)
        amount: Decimal = Decimal("0.001")
        quantized_amount: Decimal = self.connector.quantize_order_amount(self.trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.connector.quantize_order_price(self.trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.connector.quantize_order_price(self.trading_pair, ask_price * Decimal("1.5"))

        self._place_order(True, self.trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price,
                          1,
                          FixtureLitebitPro.OPEN_BUY_LIMIT_ORDER, FixtureLitebitPro.WS_AFTER_LIMIT_BUY)

        self._place_order(False, self.trading_pair, quantized_amount, OrderType.LIMIT, quantize_ask_price,
                          2,
                          FixtureLitebitPro.OPEN_SELL_LIMIT_ORDER, FixtureLitebitPro.WS_AFTER_LIMIT_SELL)

        self.run_parallel(asyncio.sleep(5))

        [cancellation_results] = self.run_parallel(self.connector.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_order_price_precision(self):
        bid_price: Decimal = self.connector.get_price(self.trading_pair, True)
        ask_price: Decimal = self.connector.get_price(self.trading_pair, False)
        mid_price: Decimal = (bid_price + ask_price) / 2
        amount: Decimal = Decimal("0.00123456")

        # Make sure there's enough balance to make the limit orders.
        self.assertGreater(self.connector.get_balance("BTC"), Decimal("0.001"))
        self.assertGreater(self.connector.get_balance("EUR"), Decimal("10"))

        # Intentionally set some prices with too many decimal places s.t. they
        # need to be quantized. Also, place them far away from the mid-price s.t. they won't
        # get filled during the test.
        bid_price = mid_price * Decimal("0.9333192292111341")
        ask_price = mid_price * Decimal("1.0492431474884933")

        cl_order_id_1 = self._place_order(True, self.trading_pair, amount, OrderType.LIMIT, bid_price, 1,
                                          FixtureLitebitPro.OPEN_BUY_LIMIT_ORDER)

        # Wait for the order created event and examine the order made
        self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
        order = self.connector.in_flight_orders[cl_order_id_1]
        quantized_bid_price = self.connector.quantize_order_price(self.trading_pair, bid_price)
        quantized_bid_size = self.connector.quantize_order_amount(self.trading_pair, amount)
        self.assertEqual(quantized_bid_price, order.price)
        self.assertEqual(quantized_bid_size, order.amount)

        # Test ask order
        cl_order_id_2 = self._place_order(False, self.trading_pair, amount, OrderType.LIMIT, ask_price, 1,
                                          FixtureLitebitPro.OPEN_SELL_LIMIT_ORDER)

        # Wait for the order created event and examine and order made
        self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCreatedEvent))
        order = self.connector.in_flight_orders[cl_order_id_2]
        quantized_ask_price = self.connector.quantize_order_price(self.trading_pair, Decimal(ask_price))
        quantized_ask_size = self.connector.quantize_order_amount(self.trading_pair, Decimal(amount))
        self.assertEqual(quantized_ask_price, order.price)
        self.assertEqual(quantized_ask_size, order.amount)

        if API_MOCK_ENABLED:
            message = FixtureLitebitPro.WS_AFTER_LIMIT_BUY.copy()
            message["data"]["client_id"] = cl_order_id_1
            MockWebSocketServerFactory.send_json_threadsafe(litebit_pro_constants.WSS_URL, message, delay=0.1)

            message = FixtureLitebitPro.WS_AFTER_LIMIT_SELL.copy()
            message["data"]["client_id"] = cl_order_id_2
            MockWebSocketServerFactory.send_json_threadsafe(litebit_pro_constants.WSS_URL, message, delay=0.1)

        [cancellation_results] = self.run_parallel(self.connector.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id = None
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.connector.tracking_states))

            # Try to buy some token from the exchange, and watch for completion event.
            price = self.connector.get_price(self.trading_pair, True) * Decimal("0.8")
            price = self.connector.quantize_order_price(self.trading_pair, price)
            amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.001"))

            order_id = self._place_order(True, self.trading_pair, amount, OrderType.LIMIT, price, 1,
                                         FixtureLitebitPro.OPEN_BUY_LIMIT_ORDER)
            [order_created_event] = self.run_parallel(self.event_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.connector.tracking_states))
            self.assertEqual(order_id, list(self.connector.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.connector)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.connector)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.connector)
            for event_tag in self.events:
                self.connector.remove_listener(event_tag, self.event_logger)
            self.__class__.connector: LitebitProExchange = LitebitProExchange(API_KEY, SECRET_KEY, [self.trading_pair],
                                                                              True)
            for event_tag in self.events:
                self.connector.add_listener(event_tag, self.event_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, self.connector)
            self.clock.add_iterator(self.connector)
            self.ev_loop.run_until_complete(self.wait_til_ready())

            self.assertEqual(0, len(self.connector.limit_orders))
            self.assertEqual(0, len(self.connector.tracking_states))
            self.connector.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.connector.limit_orders))
            self.assertEqual(1, len(self.connector.tracking_states))

            # Cancel the order and verify that the change is saved.
            if API_MOCK_ENABLED:
                message = FixtureLitebitPro.WS_AFTER_LIMIT_BUY_CANCEL.copy()
                message["data"]["client_id"] = order_id
                MockWebSocketServerFactory.send_json_threadsafe(litebit_pro_constants.WSS_URL, message, delay=0.1)

            self.connector.cancel(self.trading_pair, order_id)
            self.run_parallel(self.event_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.connector.limit_orders))
            self.assertEqual(0, len(self.connector.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.connector)
            self.assertEqual(0, len(saved_market_states.saved_state))

        finally:
            if order_id is not None:
                self.connector.cancel(self.trading_pair, order_id)
                self.run_parallel(self.event_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        buy_id: Optional[str] = None
        sell_id: Optional[str] = None
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy some token from the exchange, and watch for completion event.
            price = self.connector.get_price(self.trading_pair, True) * Decimal("1.05")
            price = self.connector.quantize_order_price(self.trading_pair, price)
            amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.001"))

            buy_id = self._place_order(True, self.trading_pair, amount, OrderType.LIMIT, price, 1,
                                       FixtureLitebitPro.OPEN_BUY_LIMIT_ORDER, FixtureLitebitPro.WS_AFTER_LIMIT_BUY)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCompletedEvent))
            self.ev_loop.run_until_complete(asyncio.sleep(1))

            # Reset the logs
            self.event_logger.clear()

            # Try to sell back the same amount to the exchange, and watch for completion event.
            price = self.connector.get_price(self.trading_pair, True) * Decimal("0.95")
            price = self.connector.quantize_order_price(self.trading_pair, price)
            amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.001"))
            sell_id = self._place_order(False, self.trading_pair, amount, OrderType.LIMIT, price, 2,
                                        FixtureLitebitPro.OPEN_SELL_LIMIT_ORDER, FixtureLitebitPro.WS_AFTER_LIMIT_SELL)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertGreaterEqual(len(trade_fills), 2)
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertGreaterEqual(len(buy_fills), 1)
            self.assertGreaterEqual(len(sell_fills), 1)

            buy_id = sell_id = None
        finally:
            if buy_id is not None:
                self.connector.cancel(self.trading_pair, buy_id)
                self.run_parallel(self.event_logger.wait_for(OrderCancelledEvent))
            if sell_id is not None:
                self.connector.cancel(self.trading_pair, sell_id)
                self.run_parallel(self.event_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def _order_response(self, fixture_data, nonce, side, trading_pair):
        order_resp = fixture_data.copy()
        return order_resp

    def _place_order(self, is_buy, trading_pair, amount, order_type, price, nonce, fixture_resp,
                     fixture_ws_1=None):
        order_id = None
        if API_MOCK_ENABLED:
            resp = self._order_response(fixture_resp, nonce, 'buy' if is_buy else 'sell', trading_pair)
            self.web_app.update_response("post", self.base_api_url, "/api/v2/order", resp)
        if is_buy:
            order_id = self.connector.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.connector.sell(trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED and fixture_ws_1 is not None:
            exchange_order_id = str(resp['uuid'])

            message = fixture_ws_1.copy()
            message["data"]["uuid"] = exchange_order_id
            message["data"]["client_id"] = order_id
            MockWebSocketServerFactory.send_json_threadsafe(litebit_pro_constants.WSS_URL, message, delay=0.1)
        return order_id
