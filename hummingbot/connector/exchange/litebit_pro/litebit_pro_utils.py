from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = [0.5, 0.5]

KEYS = {
    "litebit_pro_token":
        ConfigVar(key="litebit_pro_token",
                  prompt="Enter your Litebit Token >>> ",
                  required_if=using_exchange("litebit_pro"),
                  is_secure=True,
                  is_connect_key=True)
}
