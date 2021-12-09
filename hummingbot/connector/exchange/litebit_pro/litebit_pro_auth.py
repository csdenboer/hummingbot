import hmac
import hashlib
import json
import time
from typing import Dict, Optional
from urllib import parse


class LitebitProAuth:
    """
    Auth class required by Litebit Pro API
    """

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def get_headers(self, method: str, path: str, params: Optional[dict], body: Optional[dict]) -> Dict[str, any]:
        """
        Generates authentication headers required by LiteBit Pro
        :return: a dictionary of auth headers
        """
        timestamp = str(int(time.time() * 1000))
        print(f"{path}: {timestamp}")

        return {
            "Accept": "application/json",
            "LITEBIT-API-KEY": self.api_key,
            "LITEBIT-TIMESTAMP": timestamp,
            "LITEBIT-WINDOW": "60000",
            "LITEBIT-SIGNATURE": self._calculate_signature(timestamp, method, path, params, body),
        }

    def _calculate_signature(
        self,
        timestamp: str,
        method: str,
        path: str,
        params: Optional[dict],
        body: Optional[dict],
    ) -> str:
        data = ""

        if params:
            data += "?" + parse.urlencode(params)

        if body is not None:
            data += json.dumps(body)

        signature_data = f"{timestamp}{method.upper()}{path}{data}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"), signature_data.encode("utf-8"), hashlib.sha256
        )
        return signature.hexdigest()
