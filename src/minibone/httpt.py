import asyncio
import logging
import uuid
from enum import Enum
from typing import Any

import httpx


class Verbs(Enum):
    POST = "POST"
    GET = "GET"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class HTTPt:
    """HTTP client for making parallel requests using async/concurrent operations.

    Features:
    ---------
    - Async concurrent request processing
    - GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS methods
    - Request queuing with unique IDs
    - Configurable timeouts
    - Automatic JSON parsing

    Basic Usage:
    -----------
    from minibone.httpt import HTTPt

    # Initialize client
    client = HTTPt()

    # Queue requests
    uid1 = client.queue_get(url="https://httpbin.org/ip")
    uid2 = client.queue_post(url="https://httpbin.org/post", payload={"key": "value"})
    uid3 = client.queue_put(url="https://httpbin.org/put", payload={"key": "value"})
    uid4 = client.queue_patch(url="https://httpbin.org/patch", payload={"key": "value"})
    uid5 = client.queue_delete(url="https://httpbin.org/delete")
    uid6 = client.queue_head(url="https://httpbin.org/get")
    uid7 = client.queue_options(url="https://httpbin.org/get")

    # Get responses (blocking call, uses asyncio.run internally)
    res1 = client.read_resp(uid1)
    res2 = client.read_resp(uid2)

    print(res1)
    print(res2)

    # Async usage:
    async def main():
        client = HTTPt()
        uid = client.queue_get(url="https://httpbin.org/ip")
        res = await client.aioread_resp(uid)
        print(res)
        await client.aclose()

    asyncio.run(main())

    Notes:
    ------
    - Responses may complete out of order
    - Timeouts are configurable per instance
    - Default User-Agent header is set
    """

    def __init__(self, timeout: int = 5, headers: dict = None):
        """Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds (default: 5)
            headers: Optional dictionary of headers to add to requests

        Note:
            asyncio client is created on demand for each async context
        """
        assert isinstance(timeout, int) and timeout > 0
        self._logger = logging.getLogger(__class__.__name__)

        self._timeout = timeout
        self._tasks: dict[str, asyncio.Task] = {}  # Maps UID to asyncio.Task
        self._client: httpx.AsyncClient | None = None

        default_headers = {
            "User-Agent": "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "X-Forwarded-For": "'\"\\--",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        if headers:
            default_headers.update(headers)
        self._default_headers = default_headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient()
            self._client.headers.update(self._default_headers)
        return self._client

    async def aclose(self) -> None:
        """Close the HTTP client and cancel pending tasks."""
        # Cancel all pending tasks
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        # Close the client
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_or_create_task(self, uid: str) -> asyncio.Task | None:
        """Get task by UID, or None if not found."""
        return self._tasks.get(uid)

    async def _execute_and_wait(self, uid: str, timeout: float) -> Any:
        """Execute a queued coroutine and wait for result.

        Used internally by read_resp to run async operations from sync context.
        """
        coro = self._tasks.get(uid)
        if coro is None:
            raise KeyError(f"No such task: {uid}")

        # If it's a coroutine, create a task
        if asyncio.iscoroutine(coro):
            task = asyncio.create_task(coro)
            self._tasks[uid] = task  # Replace coroutine with task
        else:
            task = coro

        try:
            return await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.error("Task %s timed out after %d seconds", uid, timeout)
            raise
        except asyncio.CancelledError:
            self._logger.warning("Task %s was cancelled", uid)
            raise
        except Exception as e:
            self._logger.error("Task %s failed: %s", uid, str(e))
            raise
        finally:
            # Clean up completed task
            self._tasks.pop(uid, None)

    def _queue_request(self, verb: Verbs, url: str, **kwargs) -> str:
        """Add a request to the queue and return a UID to retrieve the response with read_resp

        Arguments
        ---------
        verb:       Verbs   A valid httpt.Verbs verb value
        url:        str     The url to request. Include schema http/https
        payload     dict    Can be None. A dict or list with parameters for the payload

        Notes:
        ------
        Creates a coroutine that will be executed when read_resp or aioread_resp is called.
        """
        assert isinstance(verb, Verbs)
        assert isinstance(url, str)

        if not kwargs:
            kwargs = dict()
        kwargs["url"] = url

        # Remove cmd from kwargs as it's not needed by the HTTP methods
        kwargs.pop("cmd", None)

        # Create the appropriate coroutine
        if verb == Verbs.GET:
            coro = self._get(**kwargs)
        elif verb == Verbs.POST:
            coro = self._post(**kwargs)
        elif verb == Verbs.PUT:
            coro = self._put(**kwargs)
        elif verb == Verbs.PATCH:
            coro = self._patch(**kwargs)
        elif verb == Verbs.DELETE:
            coro = self._delete(**kwargs)
        elif verb == Verbs.HEAD:
            coro = self._head(**kwargs)
        elif verb == Verbs.OPTIONS:
            coro = self._options(**kwargs)
        else:
            raise ValueError(f"Unsupported HTTP verb: {verb}")

        # Store coroutine with UID
        uid = str(uuid.uuid4())
        self._tasks[uid] = coro

        self._logger.debug("queue_request %s %s", verb, url)

        return uid

    def queue_get(self, url: str, params: dict = None) -> str:
        """Add a GET request to the queue and return a UID to retrieve the response with read_resp

        Arguments
        ---------
        url:        str     The url to get. Include schema http/https
        cmd         str     Arbitrary prefixt string to set as command for this request
                            to avoid returning a duplicated UID (returned UID is prefix_timestamp_here)

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        assert url and isinstance(url, str), "URL must be a non-empty string"
        assert not params or isinstance(params, dict), "params must be a dictionary or None"
        return self._queue_request(verb=Verbs.GET, url=url, params=params)

    def queue_post(self, url: str, payload: dict = None, is_json: bool = True) -> str:
        """Add a POST request to the queue and return a UID to retrieve the response with read_resp

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
        return self._queue_request(verb=Verbs.POST, url=url, payload=payload, is_json=is_json)

    def queue_put(self, url: str, payload: dict = None, is_json: bool = True) -> str:
        """Add a PUT request to the queue and return a UID to retrieve the response with read_resp

        Arguments
        ---------
        url:        str     The url to put. Include schema http/https
        cmd         str     Arbitrary string to set as command for this request
        payload     dict    Can be None. A dict or list with parameters for the payload
        is_json     bool    Set to True to parse result as JSON, otherwise to parse as text

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        return self._queue_request(verb=Verbs.PUT, url=url, payload=payload, is_json=is_json)

    def queue_patch(self, url: str, payload: dict = None, is_json: bool = True) -> str:
        """Add a PATCH request to the queue and return a UID to retrieve the response with read_resp

        Arguments
        ---------
        url:        str     The url to patch. Include schema http/https
        cmd         str     Arbitrary string to set as command for this request
        payload     dict    Can be None. A dict or list with parameters for the payload
        is_json     bool    Set to True to parse result as JSON, otherwise to parse as text

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        return self._queue_request(verb=Verbs.PATCH, url=url, payload=payload, is_json=is_json)

    def queue_delete(self, url: str, payload: dict = None, is_json: bool = True) -> str:
        """Add a DELETE request to the queue and return a UID to retrieve the response with read_resp

        Arguments
        ---------
        url:        str     The url to delete. Include schema http/https
        cmd         str     Arbitrary string to set as command for this request
        payload     dict    Can be None. A dict or list with parameters for the payload
        is_json     bool    Set to True to parse result as JSON, otherwise to parse as text

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        return self._queue_request(verb=Verbs.DELETE, url=url, payload=payload, is_json=is_json)

    def queue_head(self, url: str, params: dict = None) -> str:
        """Add a HEAD request to the queue and return a UID to retrieve the response with read_resp

        Arguments
        ---------
        url:        str     The url to head. Include schema http/https
        cmd         str     Arbitrary string to set as command for this request
        params      dict    Can be None. Query parameters for the request

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        assert url and isinstance(url, str), "URL must be a non-empty string"
        assert not params or isinstance(params, dict), "params must be a dictionary or None"
        return self._queue_request(verb=Verbs.HEAD, url=url, params=params)

    def queue_options(self, url: str) -> str:
        """Add an OPTIONS request to the queue and return a UID to retrieve the response with read_resp

        Arguments
        ---------
        url:        str     The url to options. Include schema http/https
        cmd         str     Arbitrary string to set as command for this request

        Notes:
        ------
        The UID to return is prefixed with the value of the cmd argument if provided
        """
        assert url and isinstance(url, str), "URL must be a non-empty string"
        return self._queue_request(verb=Verbs.OPTIONS, url=url)

    def read_resp(self, uid: str) -> object | None:
        """Return the response for the UID (json|text) or None if not found or it got a timeout

        Argument
        --------
        uid:    str     Unique identier returned by queue_post or queue_get

        Note:
            This is a blocking call that uses asyncio.run internally.
            Results are removed from cache after retrieval.
        """
        assert isinstance(uid, str)
        try:
            return asyncio.run(self._execute_and_wait(uid, self._timeout))
        except TimeoutError:
            self._logger.error("read_resp %s timed out", uid)
            return None
        except KeyError as e:
            self._logger.error("read_resp %s not found: %s", uid, str(e))
            return None
        except Exception as e:
            self._logger.error("read_resp %s failed: %s", uid, str(e))
            return None

    async def aioread_resp(self, uid: str) -> object | None:
        """Return the response for the UID (json|text) or None if not found or it got a timeout
        Async version - use from async context.

        Argument
        --------
        uid:    str     Unique identier returned by queue_post or queue_get

        Note:
            Must be called from an async context. Results are removed from cache after retrieval.
        """
        assert isinstance(uid, str)
        try:
            return await self._execute_and_wait(uid, self._timeout)
        except asyncio.TimeoutError:
            self._logger.error("aioread_resp %s timed out", uid)
            return None
        except KeyError as e:
            self._logger.error("aioread_resp %s not found: %s", uid, str(e))
            return None
        except Exception as e:
            self._logger.error("aioread_resp %s failed: %s", uid, str(e))
            return None

    async def _get(self, url: str, params: dict = None) -> dict | str | None:
        """Execute GET request and return response.

        Args:
            url: URL to request
            params: Optional query parameters

        Returns:
            Parsed JSON (dict), raw text (str), or None on failure
        """
        assert isinstance(url, str)
        assert not params or isinstance(params, dict)
        self._logger.debug("GET %s", url)

        if not params:
            params = dict()

        try:
            client = await self._get_client()
            r = await client.get(url, timeout=self._timeout, params=params)
            if r.status_code == httpx.codes.OK:
                try:
                    return await r.json()
                except (httpx.DecodingError, ValueError):
                    return r.text
            self._logger.warning("GET %s failed with status %d", url, r.status_code)

        except httpx.TimeoutException:
            self._logger.error("GET %s timed out after %d seconds", url, self._timeout)
        except httpx.RequestError as e:
            self._logger.error("GET %s failed: %s", url, str(e))
        except Exception as e:
            self._logger.error("Unexpected error in GET %s: %s", url, str(e))

        return None

    async def _put(self, url: str, payload: dict = None, is_json: bool = True) -> dict | str | None:
        """Execute PUT request and return response.

        Args:
            url: URL to request
            payload: Optional request body data
            is_json: Whether to parse response as JSON (default: True)

        Returns:
            Parsed JSON (dict), raw text (str), or None on failure
        """
        assert isinstance(url, str)
        assert not payload or isinstance(payload, dict)
        assert isinstance(is_json, bool)
        self._logger.debug("PUT %s", url)

        if not payload:
            payload = dict()

        try:
            client = await self._get_client()
            r = await client.put(
                url,
                json=payload if is_json else None,
                data=None if is_json else payload,
                timeout=self._timeout,
            )
            if r.status_code == httpx.codes.OK:
                try:
                    return await r.json() if is_json else r.text
                except (httpx.DecodingError, ValueError) as e:
                    if is_json:
                        self._logger.error("Expected JSON but got: %s", e)
                    return r.text
            self._logger.warning("PUT %s failed with status %d", url, r.status_code)

        except httpx.TimeoutException:
            self._logger.error("PUT %s timed out after %d seconds", url, self._timeout)
        except httpx.RequestError as e:
            self._logger.error("PUT %s failed: %s", url, str(e))
        except Exception as e:
            self._logger.error("Unexpected error in PUT %s: %s", url, str(e))

        return None

    async def _patch(self, url: str, payload: dict = None, is_json: bool = True) -> dict | str | None:
        """Execute PATCH request and return response.

        Args:
            url: URL to request
            payload: Optional request body data
            is_json: Whether to parse response as JSON (default: True)

        Returns:
            Parsed JSON (dict), raw text (str), or None on failure
        """
        assert isinstance(url, str)
        assert not payload or isinstance(payload, dict)
        assert isinstance(is_json, bool)
        self._logger.debug("PATCH %s", url)

        if not payload:
            payload = dict()

        try:
            client = await self._get_client()
            r = await client.patch(
                url,
                json=payload if is_json else None,
                data=None if is_json else payload,
                timeout=self._timeout,
            )
            if r.status_code == httpx.codes.OK:
                try:
                    return await r.json() if is_json else r.text
                except (httpx.DecodingError, ValueError) as e:
                    if is_json:
                        self._logger.error("Expected JSON but got: %s", e)
                    return r.text
            self._logger.warning("PATCH %s failed with status %d", url, r.status_code)

        except httpx.TimeoutException:
            self._logger.error("PATCH %s timed out after %d seconds", url, self._timeout)
        except httpx.RequestError as e:
            self._logger.error("PATCH %s failed: %s", url, str(e))
        except Exception as e:
            self._logger.error("Unexpected error in PATCH %s: %s", url, str(e))

        return None

    async def _delete(self, url: str, payload: dict = None, is_json: bool = True) -> dict | str | None:
        """Execute DELETE request and return response.

        Args:
            url: URL to request
            payload: Optional request body data
            is_json: Whether to parse response as JSON (default: True)

        Returns:
            Parsed JSON (dict), raw text (str), or None on failure
        """
        assert isinstance(url, str)
        assert not payload or isinstance(payload, dict)
        assert isinstance(is_json, bool)
        self._logger.debug("DELETE %s", url)

        try:
            client = await self._get_client()
            r = await client.delete(url, timeout=self._timeout)
            # For DELETE requests, we also consider 204 (No Content) as success
            if r.status_code in [httpx.codes.OK, httpx.codes.NO_CONTENT]:
                try:
                    return await r.json() if is_json else r.text
                except (httpx.DecodingError, ValueError) as e:
                    if is_json:
                        self._logger.error("Expected JSON but got: %s", e)
                    return r.text
            self._logger.warning("DELETE %s failed with status %d", url, r.status_code)

        except httpx.TimeoutException:
            self._logger.error("DELETE %s timed out after %d seconds", url, self._timeout)
        except httpx.RequestError as e:
            self._logger.error("DELETE %s failed: %s", url, str(e))
        except Exception as e:
            self._logger.error("Unexpected error in DELETE %s: %s", url, str(e))

        return None

    async def _head(self, url: str, params: dict = None) -> dict | str | None:
        """Execute HEAD request and return response headers.

        Args:
            url: URL to request
            params: Optional query parameters

        Returns:
            Response headers (dict) or None on failure
        """
        assert isinstance(url, str)
        assert not params or isinstance(params, dict)
        self._logger.debug("HEAD %s", url)

        if not params:
            params = dict()

        try:
            client = await self._get_client()
            r = await client.head(url, timeout=self._timeout, params=params)
            if r.status_code == httpx.codes.OK:
                return dict(r.headers)
            self._logger.warning("HEAD %s failed with status %d", url, r.status_code)

        except httpx.TimeoutException:
            self._logger.error("HEAD %s timed out after %d seconds", url, self._timeout)
        except httpx.RequestError as e:
            self._logger.error("HEAD %s failed: %s", url, str(e))
        except Exception as e:
            self._logger.error("Unexpected error in HEAD %s: %s", url, str(e))

        return None

    async def _options(self, url: str) -> dict | str | None:
        """Execute OPTIONS request and return response.

        Args:
            url: URL to request

        Returns:
            Response headers (dict) or None on failure
        """
        assert isinstance(url, str)
        self._logger.debug("OPTIONS %s", url)

        try:
            client = await self._get_client()
            r = await client.options(url, timeout=self._timeout)
            if r.status_code == httpx.codes.OK:
                return dict(r.headers)
            self._logger.warning("OPTIONS %s failed with status %d", url, r.status_code)

        except httpx.TimeoutException:
            self._logger.error("OPTIONS %s timed out after %d seconds", url, self._timeout)
        except httpx.RequestError as e:
            self._logger.error("OPTIONS %s failed: %s", url, str(e))
        except Exception as e:
            self._logger.error("Unexpected error in OPTIONS %s: %s", url, str(e))

        return None

    async def _post(self, url: str, payload: dict = None, is_json: bool = True) -> dict | str | None:
        """Execute POST request and return response.

        Args:
            url: URL to request
            payload: Optional request body data
            is_json: Whether to parse response as JSON (default: True)

        Returns:
            Parsed JSON (dict), raw text (str), or None on failure
        """
        assert isinstance(url, str)
        assert not payload or isinstance(payload, dict)
        assert isinstance(is_json, bool)
        self._logger.debug("POST %s", url)

        if not payload:
            payload = dict()

        try:
            client = await self._get_client()
            r = await client.post(
                url,
                json=payload if is_json else None,
                data=None if is_json else payload,
                timeout=self._timeout,
            )
            if r.status_code == httpx.codes.OK:
                try:
                    return await r.json() if is_json else r.text
                except (httpx.DecodingError, ValueError) as e:
                    if is_json:
                        self._logger.error("Expected JSON but got: %s", e)
                    return r.text
            self._logger.warning("POST %s failed with status %d", url, r.status_code)

        except httpx.TimeoutException:
            self._logger.error("POST %s timed out after %d seconds", url, self._timeout)
        except httpx.RequestError as e:
            self._logger.error("POST %s failed: %s", url, str(e))
        except Exception as e:
            self._logger.error("Unexpected error in POST %s: %s", url, str(e))

        return None
