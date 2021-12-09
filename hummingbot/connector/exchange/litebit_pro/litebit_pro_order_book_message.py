#!/usr/bin/env python

from typing import (
    Dict,
    List,
    Optional,
)

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)


class LitebitProOrderBookMessage(OrderBookMessage):
    def __new__(
            cls,
            message_type: OrderBookMessageType,
            content: Dict[str, any],
            timestamp: Optional[float] = None,
            *args,
            **kwargs,
    ):
        if timestamp is None:
            if message_type is OrderBookMessageType.SNAPSHOT:
                raise ValueError("timestamp must not be None when initializing snapshot messages.")
            timestamp = content["timestamp"]

        return super(LitebitProOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        return int(self.content["sequence"])

    @property
    def first_update_id(self) -> int:
        return -1

    @property
    def trade_id(self) -> int:
        return -1

    @property
    def asks(self) -> List[OrderBookRow]:
        results = [
            OrderBookRow(float(entry[0]), float(entry[1]), self.update_id)
            for entry in self.content["asks"]
        ]

        return results

    @property
    def bids(self) -> List[OrderBookRow]:
        results = [
            OrderBookRow(float(entry[0]), float(entry[1]), self.update_id)
            for entry in self.content["bids"]
        ]

        return results

    @property
    def has_update_id(self) -> int:
        return True

    @property
    def has_trade_id(self) -> bool:
        # TODO: see LitebitProAPIOrderBookDataSource's listen_for_trades
        return False
