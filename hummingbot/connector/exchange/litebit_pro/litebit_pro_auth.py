from typing import Dict, Any


class LitebitProAuth():
    """
    Auth class required by litebit.eu API
    """
    def __init__(self, token: str):
        self.token = token

    def generate_auth_dict(
        self,
        path_url: str,
        data: Dict[str, Any] = None
    ):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """

        data = data or {}
        data['method'] = path_url

        data_params = data.get('params', {})
        if not data_params:
            data['params'] = {}

        return data

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by litebit.eu
        :return: a dictionary of auth headers
        """

        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.token
        }
