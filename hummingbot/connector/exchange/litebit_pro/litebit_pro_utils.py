from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USD"

DEFAULT_FEES = [0.1, 0.1]


KEYS = {
    "litebit_pro_api_key":
        ConfigVar(key="litebit_pro_api_key",
                  prompt="Enter your LitebitPro API key >>> ",
                  required_if=using_exchange("litebit_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "litebit_pro_secret_key":
        ConfigVar(key="litebit_pro_secret_key",
                  prompt="Enter your LitebitPro secret key >>> ",
                  required_if=using_exchange("litebit_pro"),
                  is_secure=True,
                  is_connect_key=True),
}
