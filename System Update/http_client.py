import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:
    class Retry:
        def __init__(self, total=3, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504)):
            self.total = total
            self.backoff_factor = backoff_factor
            self.status_forcelist = set(status_forcelist)

session = requests.Session()
if "Retry" in globals():
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=64, pool_maxsize=64)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
session.headers.update({"Connection": "keep-alive"})
