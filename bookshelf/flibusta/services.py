import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_flibusta_session() -> requests.Session:
    """
    Returns a requests Session with a retry strategy for Flibusta.
    Flibusta server can be unstable, so we use retries with backoff.
    """
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=30,  # waits 30s between retries
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
