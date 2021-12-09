from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.connector.exchange.litebit_pro.litebit_pro_active_order_tracker import LitebitProActiveOrderTracker


class LitebitProOrderBookTrackerEntry(OrderBookTrackerEntry):
    def __init__(self,
                 trading_pair: str,
                 timestamp: float,
                 order_book: OrderBook,
                 active_order_tracker: LitebitProActiveOrderTracker):
        self._active_order_tracker = active_order_tracker
        super(LitebitProOrderBookTrackerEntry, self).__init__(trading_pair, timestamp, order_book)

    def __repr__(self) -> str:
        return (
            f"LitebitProOrderBookTrackerEntry(trading_pair='{self._trading_pair}', timestamp='{self._timestamp}', "
            f"order_book='{self._order_book}')"
        )

    @property
    def active_order_tracker(self) -> LitebitProActiveOrderTracker:
        return self._active_order_tracker
