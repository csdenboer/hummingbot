import logging
from typing import (
    Dict,
    List,
    Optional,
    Any,
    AsyncIterable,
)
from decimal import Decimal
import asyncio
import json
import aiohttp
import time

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.core.clock import Clock
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType,
    TradeFee,
)
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.litebit_pro.litebit_pro_order_book_tracker import LitebitProOrderBookTracker
from hummingbot.connector.exchange.litebit_pro.litebit_pro_user_stream_tracker import LitebitProUserStreamTracker
from hummingbot.connector.exchange.litebit_pro.litebit_pro_auth import LitebitProAuth
from hummingbot.connector.exchange.litebit_pro.litebit_pro_in_flight_order import LitebitProInFlightOrder
from hummingbot.connector.exchange.litebit_pro import litebit_pro_utils
from hummingbot.connector.exchange.litebit_pro import litebit_pro_constants as constants

ctce_logger = None
s_decimal_0 = Decimal("0.0")
s_decimal_NaN = Decimal("nan")


class LitebitProExchange(ExchangeBase):
    """
    LitebitProExchange connects with Litebit Pro exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated

    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self,
                 litebit_pro_api_key: str,
                 litebit_pro_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param litebit_pro_access_token: The access token to connect to private Litebit Pro APIs.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._litebit_pro_auth = LitebitProAuth(litebit_pro_api_key, litebit_pro_secret_key)
        self._order_book_tracker = LitebitProOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = LitebitProUserStreamTracker(self._litebit_pro_auth, trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, LitebitProInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0

    @property
    def name(self) -> str:
        return "litebit_pro"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, LitebitProInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various connector's components.
        """
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
        }

    @property
    def ready(self) -> bool:
        """
        :return True when all statuses pass, this might take 5-10 seconds for all the connector's components and
        services to be ready.
        """
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        :return active in-flight orders in json format, is used to save in sqlite db.
        """
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
            if not value.is_done
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_orders.update({
            key: LitebitProInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def start(self, clock: Clock, timestamp: float):
        """
        This function is called automatically by the clock.
        """
        super().start(clock, timestamp)

    def stop(self, clock: Clock):
        """
        This function is called automatically by the clock.
        """
        super().stop(clock)

    async def start_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        It starts tracking order book, polling trading rules,
        updating statuses and tracking user data.
        """
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        """
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def check_network(self) -> NetworkStatus:
        """
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Simply ping the network (or call any light weight public API).
        """
        try:
            await self._api_request("get", "/api/v2/time")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _trading_rules_polling_loop(self):
        """
        Periodically update trading rule.
        """
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Litebit Pro. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        instruments_info = await self._api_request("get", path_url="/api/v2/markets")
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(instruments_info)

    def _format_trading_rules(self, instruments_info: List[dict]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param instruments_info: The json API response
        :return A dictionary of trading rules.
        """
        result = {}
        for market in instruments_info:
            try:
                trading_pair = litebit_pro_utils.convert_from_exchange_trading_pair(market["market"])
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_price_increment=Decimal(market["tick_size"]),
                                                   min_base_amount_increment=Decimal(market["step_size"]),
                                                   min_notional_size=Decimal(market["minimum_amount_quote"]),
                                                   min_order_size=Decimal("0.00000001"))
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {market}.  Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False) -> Any:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = f"{constants.REST_URL}{path_url}"
        client = await self._http_client()

        if is_auth_required:
            headers = self._litebit_pro_auth.get_headers(method,
                                                         path_url,
                                                         params=params if method == "get" else None,
                                                         body=params if method in ["post", "put", "delete"] else None)
        else:
            headers = {"Accept": "application/json", }

        if method == "get":
            response = await client.get(url, params=params, headers=headers)
        elif method in ["post", "put", "delete"]:
            post_json = json.dumps(params)
            response = await getattr(client, method)(url, data=post_json, headers=headers)
        else:
            raise NotImplementedError

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")

        if response.status >= 400:
            if parsed_response['code'] == 50000:
                print(headers)

            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        # print(f"REQUEST: {method} {path_url} {params}")
        # print(f"RESPONSE: {parsed_response}")
        return parsed_response

    def get_order_price_quantum(self, trading_pair: str, price: Decimal):
        """
        Returns a price step, a minimum price increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: object):
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Buys an amount of base asset (of the given trading pair). This function returns immediately.
        To see an actual order, you'll have to wait for BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-USDT) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns A new internal order id
        """
        order_id: str = litebit_pro_utils.get_new_client_order_id(True, trading_pair)
        safe_ensure_future(self._create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, price))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Sells an amount of base asset (of the given trading pair). This function returns immediately.
        To see an actual order, you'll have to wait for SellOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-USDT) to sell from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns A new internal order id
        """
        order_id: str = litebit_pro_utils.get_new_client_order_id(False, trading_pair)
        safe_ensure_future(self._create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price))
        return order_id

    def cancel(self, trading_pair: str, order_id: str):
        """
        Cancel an order. This function returns immediately.
        To get the cancellation result, you'll have to wait for OrderCancelledEvent.
        :param trading_pair: The market (e.g. BTC-USDT) of the order.
        :param order_id: The internal order id (also called client_order_id)
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
        return order_id

    def quantize_order_amount(self, trading_pair: str, amount: Decimal, price=s_decimal_0) -> Decimal:
        trading_rule = self._trading_rules[trading_pair]
        quantized_amount = super().quantize_order_amount(trading_pair, amount)
        current_price = self.get_price(trading_pair, False)

        if price == s_decimal_0:
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount
        # Add 1% as a safety factor in case the prices changed while making the order.
        if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
            return s_decimal_0

        return quantized_amount

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Decimal):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param order_type: The order type
        :param price: The order price
        """
        trading_rule = self._trading_rules[trading_pair]

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        if amount < trading_rule.min_order_size:
            raise ValueError(f"order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        api_params = {"market": litebit_pro_utils.convert_to_exchange_trading_pair(trading_pair),
                      "side": trade_type.name.lower(),
                      "type": "limit",
                      "price": f"{price:f}",
                      "amount": f"{amount:f}",
                      "client_id": order_id,
                      }
        if order_type is OrderType.LIMIT_MAKER:
            api_params["post_only"] = True

        try:
            self.start_tracking_order(order_id,
                                      trading_pair,
                                      trade_type,
                                      price,
                                      amount,
                                      order_type
                                      )
            order_result = await self._api_request("post", "/api/v2/order", api_params, True)

            exchange_order_id = str(order_result["uuid"])
            tracked_order = self._in_flight_orders.get(order_id)

            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_class(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   amount,
                                   price,
                                   order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to Litebit Pro for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    def start_tracking_order(self,
                             order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = LitebitProInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def get_order(self, client_order_id: str) -> Dict[str, Any]:
        """
        Gets status update for a particular order via rest API
        :returns: json response
        """
        order = self._in_flight_orders.get(client_order_id)
        if order is None:
            return None
        exchange_order_id = await order.get_exchange_order_id()
        result = await self._api_request("get",
                                         "/api/v2/order",
                                         {"market": litebit_pro_utils.convert_to_exchange_trading_pair(
                                             order.trading_pair), "uuid": exchange_order_id},
                                         True)
        return result

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Executes order cancellation process by first calling cancel-order API. The API result doesn't confirm whether
        the cancellation is successful, it simply states it receives the request.
        :param order_id: The internal order id
        order.last_state to change to CANCELED
        """
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
            if tracked_order.exchange_order_id is None:
                await tracked_order.get_exchange_order_id()
            ex_order_id = tracked_order.exchange_order_id
            await self._api_request(
                "delete",
                "/api/v2/orders",
                {"market": litebit_pro_utils.convert_to_exchange_trading_pair(trading_pair), "orders": [ex_order_id]},
                True
            )
            return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Litebit Pro. "
                                f"Check API key and network connection."
            )

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Litebit Pro. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            account_info = await self._api_request("get", "/api/v2/balances", None, True)
        except Exception:
            raise

        for account in account_info:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["total"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())

            for tracked_order in tracked_orders:
                client_order_id = tracked_order.client_order_id

                try:
                    order = await self.get_order(client_order_id)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: ",
                        exc_info=True,
                        app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                        f"Check API key and network connection.{e}"
                    )
                    continue
                else:
                    self._process_order_message(client_order_id, order)

    def _process_order_message(self, client_order_id: str, order_update: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_update: The order response from either REST or web socket API (they are of the same format)
        """
        if client_order_id not in self._in_flight_orders:
            return
        tracked_order = self._in_flight_orders[client_order_id]

        # Calculate the newly executed amount for this update.
        new_confirmed_amount = Decimal(order_update["amount_filled"])
        execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

        order_type = tracked_order.order_type
        executed_value = (Decimal(order_update["amount_quote_filled"]) - Decimal(
            order_update["fee"]))
        execute_price = s_decimal_0 if new_confirmed_amount == s_decimal_0 \
            else executed_value / new_confirmed_amount

        # Emit event if executed amount is greater than 0.
        if execute_amount_diff > s_decimal_0:
            order_filled_event = OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                execute_price,
                execute_amount_diff,
                self.get_fee(
                    tracked_order.base_asset,
                    tracked_order.quote_asset,
                    order_type,
                    tracked_order.trade_type,
                    execute_price,
                    execute_amount_diff,
                ),
                # TODO: do we need this?
                # Coinbase Pro's websocket stream tags events with order_id rather than trade_id
                # Using order_id here for easier data validation
                exchange_trade_id=tracked_order.exchange_order_id,
            )
            self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                               f"order {client_order_id}.")
            self.trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

        # Update the tracked order
        tracked_order.last_state = order_update["status"]
        tracked_order.executed_amount_base = new_confirmed_amount
        tracked_order.executed_amount_quote = executed_value
        tracked_order.fee_paid = Decimal(order_update["fee"])

        if tracked_order.is_done:
            if not tracked_order.is_failure:
                if tracked_order.trade_type == TradeType.BUY:
                    self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                       f"according to order status API.")
                    self.trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                       BuyOrderCompletedEvent(self.current_timestamp,
                                                              tracked_order.client_order_id,
                                                              tracked_order.base_asset,
                                                              tracked_order.quote_asset,
                                                              (tracked_order.fee_asset
                                                               or tracked_order.base_asset),
                                                              tracked_order.executed_amount_base,
                                                              tracked_order.executed_amount_quote,
                                                              tracked_order.fee_paid,
                                                              order_type))
                else:
                    self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                       f"according to order status API.")
                    self.trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                       SellOrderCompletedEvent(self.current_timestamp,
                                                               tracked_order.client_order_id,
                                                               tracked_order.base_asset,
                                                               tracked_order.quote_asset,
                                                               (tracked_order.fee_asset
                                                                or tracked_order.quote_asset),
                                                               tracked_order.executed_amount_base,
                                                               tracked_order.executed_amount_quote,
                                                               tracked_order.fee_paid,
                                                               order_type))
            else:
                self.logger().info(f"The market order {tracked_order.client_order_id} has failed/been cancelled "
                                   f"according to order status API.")
                self.trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                   OrderCancelledEvent(
                                       self.current_timestamp,
                                       tracked_order.client_order_id
                                   ))
            self.stop_tracking_order(tracked_order.client_order_id)

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]

        try:
            await self._api_request(
                "delete",
                "/api/v2/orders",
                {},
                True
            )
        except Exception:
            self.logger().network(
                "Failed to cancel all orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel all orders on LiteBit Pro. Check API key and network connection."
            )
        else:
            # wait for cancellation task to be finished
            await asyncio.sleep(20)

        return [
            CancellationResult(o.client_order_id, o.client_order_id not in self._in_flight_orders)
            for o in incomplete_orders
        ]

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return TradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from LiteBit Pro. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        LitebitProAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if "event" not in event_message:
                    continue

                event = event_message["event"]
                data = event_message["data"]

                if event == "order":
                    tracked_order = self._in_flight_orders.get(data["client_id"])

                    # if we are not interested in this order, then just skip
                    if tracked_order is not None:
                        self._process_order_message(tracked_order.client_order_id, data)
                elif event == "balance":
                    asset_name = data["currency"]
                    self._account_balances[asset_name] = Decimal(str(data["available"])) + Decimal(
                        str(data["reserved"]))
                    self._account_available_balances[asset_name] = Decimal(str(data["available"]))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)
