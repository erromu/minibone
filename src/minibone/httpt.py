import logging
from enum import Enum

import requests

from minibone.parallel_threads import PARThreads


class Verbs(Enum):
    POST = "POST"
    GET = "GET"


class HTTPt:
    """
    Fetches HTTP requests in multi-threading mode
    Each request is queued then procesed in FIFO (first in first out) order using a thread for each one

    Usage
    -----

    from minibone.parallel_threads import PARThreads

    worker = PARThreads()
    client = HTTPt(worker)
    worker.start()

    # this could be in one thread
    uid1 = client.queue_get(url="https://httpbin.org/ip", cmd="test")

    # and this another could be in onether thread
    uid2 = client.queue_get(url="https://httpbin.org/headers", cmd="test")


    res1 = client.read_resp(uid1)
    res2 = client.read_resp(uid2)

    print(res1)
    print(res2)

    worker.stop()

    NOTES
    -----
    Each response may take different time to fetch, so latest queued requests could be gotten first
    This class is great for multi-threaded setups
    """

    def __init__(self, worker: PARThreads, timeout: int = 5):
        """
        Arguments
        ---------
        worker:     object      A PARThreads object
        timeout:    int         Time to wait for an response before giving up

        Notes:
        ------
        Pay attention this class do not call worker.start()
        """
        assert isinstance(worker, PARThreads)
        assert isinstance(timeout, int) and timeout > 0
        self._logger = logging.getLogger(__class__.__name__)

        self._timeout = timeout
        self._worker = worker

        requests.packages.urllib3.disable_warnings()
        # not shortcuts, read this
        # https://shuaib.org/technical-guide/resolving-python-requests-tls-ssl-certificate-verification-errors/

        # TODO take a look to https://netnut.io/httpx-vs-requests
        self.fetcher = requests.Session()
        self.fetcher.headers.update({
            "User-Agent": "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "X-Forwarded-For": "'\"\\--",
        })

    def _queue_request(self, verb: Verbs, url: str, cmd: str = "UID", **kwargs) -> str:
        """Add a request to the queue and return an UID to retrieve the response whit read_resp

        Arguments
        ---------
        verb:       Verbs   A valid httpt.Verbs verb value
        url:        str     The url to request. Include schema http/https
        cmd         str     Arbitrary string to set as command for this request
        payload     dict    Can be None. A dict or list with parameters for the payload

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        assert isinstance(verb, Verbs)
        assert isinstance(url, str)

        if not kwargs:
            kwargs = dict()
        kwargs["url"] = url

        if verb == Verbs.GET:
            uid = self._worker.queue(self._get, cmd=cmd, **kwargs)
        else:
            uid = self._worker.queue(self._post, cmd=cmd, **kwargs)

        self._logger.debug("queue_request %s %s", verb, url)

        return uid

    def queue_get(self, url: str, cmd: str = "get", params: dict = None) -> str:
        """Add a get request to the queue and return an UID to retrieve the response whit read_resp

        Arguments
        ---------
        url:        str     The url to get. Include schema http/https
        cmd         str     Arbitrary prefixt string to set as command for this request
                            to avoid returning a duplicated UID (returned UID is prefix_timestamp_here)

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        return self._queue_request(verb=Verbs.GET, url=url, cmd=cmd, params=params)

    def queue_post(self, url: str, cmd: str = "post", payload: dict = None, is_json: bool = True) -> str:
        """Add a post request to the queue and return an UID to retrieve the response whit read_resp

        Arguments
        ---------
        url:        str     The url to post. Include schema http/https
        cmd         str     Arbitrary string to set as command for this request
        payload     dict    Can be None. A dict or list with parameters for the payload
        is_json     bool    Set to True to parse result as JSON, otherwise to parse as text

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        return self._queue_request(verb=Verbs.POST, url=url, cmd=cmd, payload=payload, is_json=is_json)

    def read_resp(self, uid: str) -> object | None:
        """Return the response for the UID (json|text) or None if not found or it got a timeout

        Argument
        --------
        uid:    str     Unique identier returned by queue_post or queue_get
        """
        assert isinstance(uid, str)
        return self._worker.get(uid=uid, timeout=self._timeout)

    async def aioread_resp(self, uid: str) -> object | None:
        """Return the response for the UID (json|text) or None if not found or it got a timeout

        Argument
        --------
        uid:    str     Unique identier returned by queue_post or queue_get
        """
        assert isinstance(uid, str)
        return await self._worker.aioget(uid=uid, timeout=self._timeout)

    def _get(self, url: str, params: dict = None) -> str:
        assert isinstance(url, str)
        assert not params or isinstance(params, dict)
        self._logger.debug("_get %s", url)

        resp = None
        try:
            r = self.fetcher.get(url, timeout=self._timeout, verify=False, **params)
            if r.status_code == 200:
                resp = r.text
            else:
                self._logger.warning("Got %s for %s", r.status_code, url)
            r.close()

        except requests.exceptions.ProxyError as e:
            self._logger.error("Proxy error: %s", e)

        except requests.exceptions.RequestException as e:
            self._logger.error("Request error: %s", e)

        except Exception as e:
            self._logger.error("_get error: Url %s %s", url, e)

        return resp

    def _post(self, url: str, payload: dict = None, is_json: bool = True) -> dict | str:
        assert isinstance(url, str)
        assert not payload or isinstance(payload, dict)
        assert isinstance(is_json, bool)
        self._logger.debug("_post %s %s is_json %s", url, payload, is_json)

        resp = None
        try:
            r = self.fetcher.post(url, data=payload, timeout=self._timeout, verify=False)
            if r.status_code == 200 and not r.is_permanent_redirect and not r.is_redirect:
                if is_json:
                    resp = r.json()
                else:
                    resp = r.text
            else:
                self._logger.warning("Got %s or redirect for %s", r.status_code, url)

            r.close()

        except requests.exceptions.JSONDecodeError as e:
            self._logger.error("Expecting a JSON, but other kind of content gotten %s", e)

        except requests.exceptions.ProxyError as e:
            self._logger.error("Proxy error: %s", e)

        except requests.exceptions.RequestException as e:
            self._logger.error("Request error: %s", e)

        except Exception as e:
            self._logger.error("_post error: Url %s Params %s %s", url, payload, e)

        return resp
