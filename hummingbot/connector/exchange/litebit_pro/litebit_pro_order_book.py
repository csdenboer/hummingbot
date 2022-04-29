#!/usr/bin/env python

import logging
import hummingbot.connector.exchange.litebit_pro.litebit_pro_constants as constants

from sqlalchemy.engine import RowProxy
from typing import (
    Optional,
    Dict,
    List, Any)

from hummingbot.connector.exchange.litebit_pro import litebit_pro_utils
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage, OrderBookMessageType
)
from hummingbot.connector.exchange.litebit_pro.litebit_pro_order_book_message import LitebitProOrderBookMessage
from hummingbot.connector.exchange.litebit_pro.litebit_pro_utils import ms_timestamp_to_s

_logger = None


class LitebitProOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _logger
        if _logger is None:
            _logger = logging.getLogger(__name__)
        return _logger

    @classmethod
    def snapshot_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Convert json snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from API
        :param metadata: meta data related to msg
        :return: LitebitProOrderBook
        """
        if metadata:
            msg.update(metadata)

        return LitebitProOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=ms_timestamp_to_s(msg["timestamp"])
        )

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        """
        *used for backtesting
        Convert a row of snapshot data into standard OrderBookMessage format
        :param record: a row of snapshot data from the database
        :param metadata: meta data related to record
        :return: LitebitProOrderBook
        """
        return LitebitProOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=record.json,
            timestamp=record.timestamp
        )

    @classmethod
    def diff_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Convert json diff data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param metadata: meta data related to msg
        :return: LitebitProOrderBook
        """
        if metadata:
            msg.update(metadata)

        return LitebitProOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=ms_timestamp_to_s(msg["timestamp"])
        )

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        """
        *used for backtesting
        Convert a row of diff data into standard OrderBookMessage format
        :param record: a row of diff data from the database
        :return: LitebitProOrderBook
        """
        return LitebitProOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=record.json,
            timestamp=record.timestamp
        )

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, Any], metadata: Optional[Dict] = None):
        """
        Convert a trade data into standard OrderBookMessage format
        :return: LitebitProOrderBook
        """
        if metadata:
            msg.update(metadata)

        return LitebitProOrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                **msg,
                "trading_pair": litebit_pro_utils.convert_from_exchange_trading_pair(
                    msg["market"]
                ),
                # side of the taker
                "trade_type": float(TradeType.SELL.value) if msg["side"] == "sell" else float(
                    TradeType.BUY.value)
            },
            timestamp=ms_timestamp_to_s(msg["timestamp"])
        )

    @classmethod
    def trade_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        """
        *used for backtesting
        Convert a row of trade data into standard OrderBookMessage format
        :param record: a row of trade data from the database
        :return: LitebitProOrderBook
        """
        return LitebitProOrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=record.json,
            timestamp=record.timestamp
        )

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError(constants.EXCHANGE_NAME + " order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError(constants.EXCHANGE_NAME + " order book needs to retain individual order data.")
