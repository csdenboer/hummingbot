class FixtureLitebitPro:
    # General Exchange Info
    MARKETS = [
        {'market': 'BTC-EUR', 'status': 'active', 'step_size': '0.00000001', 'tick_size': '0.01',
         'minimum_amount_quote': '5.00', 'base_currency': 'BTC', 'quote_currency': 'EUR'},
        {'market': 'ETH-EUR', 'status': 'active', 'step_size': '0.00000001', 'tick_size': '0.01',
         'minimum_amount_quote': '5.00', 'base_currency': 'ETH', 'quote_currency': 'EUR'},
        {'market': 'ADA-EUR', 'status': 'active', 'step_size': '0.00000001', 'tick_size': '0.0001',
         'minimum_amount_quote': '5.00', 'base_currency': 'ADA', 'quote_currency': 'EUR'},
        {'market': 'DOGE-EUR', 'status': 'active', 'step_size': '0.00000001', 'tick_size': '0.00001',
         'minimum_amount_quote': '5.00', 'base_currency': 'DOGE', 'quote_currency': 'EUR'},
        {'market': 'BCH-EUR', 'status': 'active', 'step_size': '0.00000001', 'tick_size': '0.001',
         'minimum_amount_quote': '5.00', 'base_currency': 'BCH', 'quote_currency': 'EUR'},
        {'market': 'XRP-EUR', 'status': 'active', 'step_size': '0.00000001', 'tick_size': '0.00001',
         'minimum_amount_quote': '5.00', 'base_currency': 'XRP', 'quote_currency': 'EUR'}
    ]

    # General User Info
    BALANCES = [
        {'available': '16571.67571739', 'reserved': '3438.57500000', 'total': '20010.25071739', 'currency': 'EUR'},
        {'available': '4.18790167', 'reserved': '0.00000000', 'total': '4.18790167', 'currency': 'BTC'},
        {'available': '50000.00000000', 'reserved': '0.00000000', 'total': '50000.00000000', 'currency': 'XRP'},
        {'available': '100000000.00000000', 'reserved': '0.00000000', 'total': '100000000.00000000',
         'currency': 'DOGE'},
        {'available': '250.00000000', 'reserved': '0.00000000', 'total': '250.00000000', 'currency': 'BCH'},
        {'available': '1262.07275126', 'reserved': '0.00000000', 'total': '1262.07275126', 'currency': 'ETH'},
        {'available': '300000.00000000', 'reserved': '0.00000000', 'total': '300000.00000000', 'currency': 'ADA'}
    ]

    TRADE_FEES = {'maker': '0.15', 'taker': '0.25', 'volume': '0.00'}

    TICKERS = [
        {"market": "BTC-EUR", "open": "46015.21", "last": "44749.00000000", "volume": "27837.51739250",
         "low": "43291.79", "high": "46478.14", "bid": "44743.95", "ask": "44795.47"},
        {"market": "ETH-EUR", "open": "3907.87", "last": "3864.04000000", "volume": "279541.93568320", "low": "3762.70",
         "high": "3947.99", "bid": "3864.04", "ask": "3902.50"},
        {"market": "ADA-EUR", "open": "1.5133", "last": "1.50920000", "volume": "105200062.53102929", "low": "0.9213",
         "high": "1.6191", "bid": "1.4165", "ask": "1.5092"},
        {"market": "DOGE-EUR", "open": "0.17123", "last": "0.16128000", "volume": "5193131928.96555469",
         "low": "0.11714", "high": "0.20269", "bid": "0.12490", "ask": "0.17254"},
        {"market": "BCH-EUR", "open": "425.386", "last": "414.15000000", "volume": "37442.91031167", "low": "394.572",
         "high": "451.384", "bid": "0.000", "ask": "0.000"},
        {"market": "XRP-EUR", "open": "0", "last": "0.78986000", "volume": "0", "low": "0.78848", "high": "1.25127",
         "bid": "5.00000", "ask": "0.00000"}
    ]

    # User Trade Info
    OPEN_BUY_MARKET_ORDER = {"uuid": "7807541a-0641-45d0-999f-fb9550529e0a", "amount": "0.00222015",
                             "amount_filled": "0.00000000", "amount_quote_filled": "0.00", "fee": "0.00",
                             "price": "0.00", "side": "buy", "type": "market", "status": "open",
                             "filled_status": "not_filled", "stop": None, "stop_hit": None, "stop_price": None,
                             "post_only": False, "time_in_force": "gtc", "created_at": 1638957090629,
                             "updated_at": 1638957090629, "expire_at": None, "market": "BTC-EUR", "client_id": None}

    OPEN_SELL_MARKET_ORDER = {"uuid": "f29afff7-6dcd-4ae3-80d2-165ee5614aa7", "amount": "0.00100000",
                              "amount_filled": "0.00000000", "amount_quote_filled": "0.00", "fee": "0.00",
                              "price": "0.00", "side": "sell", "type": "market", "status": "open",
                              "filled_status": "not_filled", "stop": None, "stop_hit": None, "stop_price": None,
                              "post_only": False, "time_in_force": "gtc", "created_at": 1638957272502,
                              "updated_at": 1638957272502, "expire_at": None, "market": "BTC-EUR", "client_id": None}

    OPEN_BUY_LIMIT_ORDER = {"uuid": "39425691-8209-4134-8b6e-d763bb1c7bcb", "amount": "0.00100000",
                            "amount_filled": "0.00000000", "amount_quote_filled": "0.00", "fee": "0.00",
                            "price": "45000.00", "side": "buy", "type": "limit", "status": "open",
                            "filled_status": "not_filled", "stop": None, "stop_hit": None, "stop_price": None,
                            "post_only": False, "time_in_force": "gtc", "created_at": 1638967614598,
                            "updated_at": 1638967614598, "expire_at": None, "market": "BTC-EUR", "client_id": None}

    OPEN_SELL_LIMIT_ORDER = {"uuid": "014c1bb7-b7b2-4bc3-8a4f-165449fb7041", "amount": "0.00100000",
                             "amount_filled": "0.00000000", "amount_quote_filled": "0.00", "fee": "0.00",
                             "price": "40000.00", "side": "sell", "type": "limit", "status": "open",
                             "filled_status": "not_filled", "stop": None, "stop_hit": None, "stop_price": None,
                             "post_only": False, "time_in_force": "gtc", "created_at": 1638967961268,
                             "updated_at": 1638967961268, "expire_at": None, "market": "BTC-EUR", "client_id": None}

    WS_AFTER_MARKET_BUY = {"event": "order",
                           "data": {"uuid": "7807541a-0641-45d0-999f-fb9550529e0a", "amount": "0.00222015",
                                    "amount_filled": "0.00222015", "amount_quote_filled": "99.98", "fee": "0.25",
                                    "price": "0.00", "side": "buy", "type": "market", "status": "closed",
                                    "filled_status": "filled", "stop": None, "stop_hit": None, "stop_price": None,
                                    "post_only": False, "time_in_force": "gtc", "created_at": 1638957090629,
                                    "updated_at": 1638957090671, "expire_at": None, "market": "BTC-EUR",
                                    "client_id": None}}

    WS_AFTER_MARKET_SELL = {"event": "order",
                            "data": {"uuid": "f29afff7-6dcd-4ae3-80d2-165ee5614aa7", "amount": "0.00100000",
                                     "amount_filled": "0.00100000", "amount_quote_filled": "44.19", "fee": "0.11",
                                     "price": "0.00", "side": "sell", "type": "market", "status": "closed",
                                     "filled_status": "filled", "stop": None, "stop_hit": None, "stop_price": None,
                                     "post_only": False, "time_in_force": "gtc", "created_at": 1638957272502,
                                     "updated_at": 1638957272569, "expire_at": None, "market": "BTC-EUR",
                                     "client_id": None}}

    WS_AFTER_LIMIT_BUY = {"event": "order",
                          "data": {"uuid": "39425691-8209-4134-8b6e-d763bb1c7bcb", "amount": "0.00100000",
                                   "amount_filled": "0.00100000", "amount_quote_filled": "43.95", "fee": "0.11",
                                   "price": "45000.00", "side": "buy", "type": "limit", "status": "closed",
                                   "filled_status": "filled", "stop": None, "stop_hit": None, "stop_price": None,
                                   "post_only": False, "time_in_force": "gtc", "created_at": 1638967614598,
                                   "updated_at": 1638967614707, "expire_at": None, "market": "BTC-EUR",
                                   "client_id": None}}

    WS_AFTER_LIMIT_SELL = {"event": "order",
                           "data": {"uuid": "014c1bb7-b7b2-4bc3-8a4f-165449fb7041", "amount": "0.00100000",
                                    "amount_filled": "0.00100000", "amount_quote_filled": "43.33", "fee": "0.11",
                                    "price": "40000.00", "side": "sell", "type": "limit", "status": "closed",
                                    "filled_status": "filled", "stop": None, "stop_hit": None, "stop_price": None,
                                    "post_only": False, "time_in_force": "gtc", "created_at": 1638967961268,
                                    "updated_at": 1638967961430, "expire_at": None, "market": "BTC-EUR",
                                    "client_id": None}}

    WS_AFTER_LIMIT_BUY_CANCEL = {"event": "order",
                                 "data": {"uuid": "39425691-8209-4134-8b6e-d763bb1c7bcb", "amount": "0.00100000",
                                          "amount_filled": "0.00000000", "amount_quote_filled": "0.00", "fee": "0.00",
                                          "price": "45000.00", "side": "buy", "type": "limit", "status": "closed",
                                          "filled_status": "not_filled", "stop": None, "stop_hit": None,
                                          "stop_price": None, "post_only": False, "time_in_force": "gtc",
                                          "created_at": 1638967614598, "updated_at": 1638967614598, "expire_at": None,
                                          "market": "BTC-EUR", "client_id": None}}

    WS_AFTER_LIMIT_SELL_CANCEL = {"event": "order",
                                  "data": {"uuid": "014c1bb7-b7b2-4bc3-8a4f-165449fb7041", "amount": "0.00100000",
                                           "amount_filled": "0.00000000", "amount_quote_filled": "0.00", "fee": "0.00",
                                           "price": "40000.00", "side": "sell", "type": "limit", "status": "closed",
                                           "filled_status": "not_filled", "stop": None, "stop_hit": None,
                                           "stop_price": None, "post_only": False, "time_in_force": "gtc",
                                           "created_at": 1638967961268, "updated_at": 1638967961268, "expire_at": None,
                                           "market": "BTC-EUR", "client_id": None}}

    GET_DEPOSIT_INFO = {"address": "bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23", "success": True,
                        "addressTag": "104312555", "asset": "BNB",
                        "url": "https://explorer.binance.org/address/bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23"}

    LINKETH_SNAP = {"lastUpdateId": 299745427, "bids": [["0.01548716", "223.00000000"], ["0.01548684", "36.00000000"],
                                                        ["0.01548584", "36.00000000"]],
                    "asks": [["0.01552718", "87.00000000"], ["0.01552730", "69.00000000"],
                             ["0.01552876", "12.00000000"]]}
    ZRXETH_SNAP = {"lastUpdateId": 146902033, "bids": [["0.00127994", "723.00000000"], ["0.00127937", "439.00000000"],
                                                       ["0.00127936", "4106.00000000"]],
                   "asks": [["0.00128494", "1991.00000000"], ["0.00128495", "804.00000000"],
                            ["0.00128500", "400.00000000"]]}

    ORDER_BUY_PRECISION = {"symbol": "LINKETH", "orderId": 154388421, "orderListId": -1,
                           "clientOrderId": "buy-LINKETH-1580289856010707", "transactTime": 1580289856293,
                           "price": "0.00516884", "origQty": "3.00000000", "executedQty": "0.00000000",
                           "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC", "type": "LIMIT",
                           "side": "BUY", "fills": []}

    ORDER_BUY_PRECISION_GET = {"symbol": "LINKETH", "orderId": 154388421, "orderListId": -1,
                               "clientOrderId": "buy-LINKETH-1580289856010707", "price": "0.01447300",
                               "origQty": "3.00000000", "executedQty": "0.00000000",
                               "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC",
                               "type": "LIMIT", "side": "BUY", "stopPrice": "0.00000000", "icebergQty": "0.00000000",
                               "time": 1580289856293, "updateTime": 1580289856293, "isWorking": True,
                               "origQuoteOrderQty": "0.00000000"}

    ORDER_SELL_PRECISION = {"symbol": "LINKETH", "orderId": 154388434, "orderListId": -1,
                            "clientOrderId": "sell-LINKETH-1580289858445415", "transactTime": 1580289858734,
                            "price": "0.05333293", "origQty": "1.00000000", "executedQty": "0.00000000",
                            "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC", "type": "LIMIT",
                            "side": "SELL", "fills": []}

    ORDER_SELL_PRECISION_GET = {"symbol": "LINKETH", "orderId": 154388434, "orderListId": -1,
                                "clientOrderId": "sell-LINKETH-1580289858445415", "price": "0.01627100",
                                "origQty": "1.23000000", "executedQty": "0.00000000",
                                "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC",
                                "type": "LIMIT", "side": "SELL", "stopPrice": "0.00000000", "icebergQty": "0.00000000",
                                "time": 1580289858734, "updateTime": 1580289858734, "isWorking": True,
                                "origQuoteOrderQty": "0.00000000"}
