from typing import Dict


class LitebitProAuth:
    """
    Auth class required by Litebit Pro API
    """
    def __init__(self, token: str):
        self.token = token

    def get_headers(self, method: str, path_url: str, body: str = "") -> Dict[str, any]:
        return {
            "Authorization": "Bearer " + self.token,
            "Content-Type": 'application/json',
        }
