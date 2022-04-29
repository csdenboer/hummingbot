import math
from typing import Tuple

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True
EXAMPLE_PAIR = "ETH-EUR"
# TODO: update fees
DEFAULT_FEES = [0.1, 0.1]


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair


def convert_trading_pair_to_base_currency_code_quote_currency_code(trading_pair: str) -> Tuple[str, str]:
    codes = trading_pair.split("-")

    if len(codes) != 2:
        raise Exception(f"Unexpected codes: {codes}")

    return codes[0], codes[1]


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "buy" if is_buy else "sell"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"


KEYS = {
    "litebit_pro_api_key":
        ConfigVar(key="litebit_pro_api_key",
                  prompt="Enter your LiteBit Pro API key >>> ",
                  required_if=using_exchange("litebit_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "litebit_pro_secret_key":
        ConfigVar(key="litebit_pro_secret_key",
                  prompt="Enter your LiteBit Pro secret key >>> ",
                  required_if=using_exchange("litebit_pro"),
                  is_secure=True,
                  is_connect_key=True),
}
