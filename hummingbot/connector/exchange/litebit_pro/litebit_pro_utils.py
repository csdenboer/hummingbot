from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = [0.5, 0.5]

KEYS = {
    "litebit_pro_api_key":
        ConfigVar(key="litebit_pro_api_key",
                  prompt="Enter your Litebit API key >>> ",
                  required_if=using_exchange("litebit_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "litebit_pro_secret_key":
        ConfigVar(key="litebit_pro_secret_key",
                  prompt="Enter your Litebit secret key >>> ",
                  required_if=using_exchange("litebit_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "litebit_pro_passphrase":
        ConfigVar(key="litebit_pro_passphrase",
                  prompt="Enter your Litebit passphrase >>> ",
                  required_if=using_exchange("litebit_pro"),
                  is_secure=True,
                  is_connect_key=True),
}
