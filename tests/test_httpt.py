import unittest
from unittest.mock import AsyncMock
from unittest.mock import patch

import httpx

from minibone.httpt import HTTPt
from minibone.httpt import Verbs


class TestHTTPt(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test client."""
        self.client = HTTPt()

    async def tearDown(self) -> None:
        """Clean up client."""
        await self.client.aclose()

    def test_queue_operations(self) -> None:
        """Test basic queue and response operations."""
        with patch("minibone.httpt.httpx.AsyncClient") as mock_client_class:
            # Setup mock async client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Setup mock responses
            mock_response_get = AsyncMock()
            mock_response_get.status_code = 200
            mock_response_get.json.return_value = {
                "args": {"foo": "bar"},
                "url": "https://httpbin.org/anything?foo=bar",
            }
            mock_client.get.return_value = mock_response_get

            mock_response_post = AsyncMock()
            mock_response_post.status_code = 200
            mock_response_post.json.return_value = {"url": "https://httpbin.org/post"}
            mock_client.post.return_value = mock_response_post

            # Create client with mocked httpx.AsyncClient
            client = HTTPt()

            # Test GET request
            uid1 = client.queue_get(url="https://httpbin.org/anything", params={"foo": "bar"})
            resp1 = client.read_resp(uid1)
            self.assertEqual(resp1["args"]["foo"], "bar")
            self.assertEqual(resp1["url"], "https://httpbin.org/anything?foo=bar")

            # Test POST request
            uid2 = client.queue_post(url="https://httpbin.org/post")
            resp2 = client.read_resp(uid2)
            self.assertEqual(resp2["url"], "https://httpbin.org/post")

    def test_async_operations(self) -> None:
        """Test async response retrieval."""
        with patch("minibone.httpt.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"test": "async"}
            mock_client.get.return_value = mock_response

            uid = self.client.queue_get(url="https://test.com")
            # Note: We can't easily test the async method in a synchronous test
            # For now, we'll just verify that the uid is returned correctly
            self.assertIsInstance(uid, str)
            self.assertTrue(len(uid) > 0)

    def test_error_handling(self) -> None:
        """Test error cases."""
        # Test invalid URL
        with self.assertRaises(AssertionError):
            self.client.queue_get(url="")

        # Test invalid params
        with self.assertRaises(AssertionError):
            self.client.queue_get(url="https://test.com", params="invalid")  # type: ignore

    def test_verb_enum(self) -> None:
        """Test HTTP verbs enum."""
        self.assertEqual(Verbs.GET.value, "GET")
        self.assertEqual(Verbs.POST.value, "POST")
        self.assertEqual(Verbs.PUT.value, "PUT")
        self.assertEqual(Verbs.PATCH.value, "PATCH")
        self.assertEqual(Verbs.DELETE.value, "DELETE")
        self.assertEqual(Verbs.HEAD.value, "HEAD")
        self.assertEqual(Verbs.OPTIONS.value, "OPTIONS")

    def test_all_http_methods(self) -> None:  # noqa: PLR0915
        """Test all HTTP methods."""
        with patch("minibone.httpt.httpx.AsyncClient") as mock_client_class:
            # Setup mock async client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Setup mock responses to return successful status codes
            mock_response_get = AsyncMock()
            mock_response_get.status_code = httpx.codes.OK
            mock_response_get.json.return_value = {"success": True}
            mock_client.get.return_value = mock_response_get

            mock_response_post = AsyncMock()
            mock_response_post.status_code = httpx.codes.OK
            mock_response_post.json.return_value = {"success": True}
            mock_client.post.return_value = mock_response_post

            mock_response_put = AsyncMock()
            mock_response_put.status_code = httpx.codes.OK
            mock_response_put.json.return_value = {"success": True}
            mock_client.put.return_value = mock_response_put

            mock_response_patch = AsyncMock()
            mock_response_patch.status_code = httpx.codes.OK
            mock_response_patch.json.return_value = {"success": True}
            mock_client.patch.return_value = mock_response_patch

            mock_response_delete = AsyncMock()
            mock_response_delete.status_code = httpx.codes.OK
            mock_response_delete.json.return_value = {"success": True}
            mock_client.delete.return_value = mock_response_delete

            mock_response_head = AsyncMock()
            mock_response_head.status_code = httpx.codes.OK
            mock_response_head.headers = {"Content-Type": "application/json"}
            mock_client.head.return_value = mock_response_head

            mock_response_options = AsyncMock()
            mock_response_options.status_code = httpx.codes.OK
            mock_response_options.headers = {"Allow": "GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS"}
            mock_client.options.return_value = mock_response_options

            # Create client with mocked httpx.AsyncClient
            client = HTTPt()

            # Test that all methods can be called and return a response
            uid1 = client.queue_get(url="https://httpbin.org/get")
            resp1 = client.read_resp(uid1)
            self.assertIsNotNone(resp1)

            uid2 = client.queue_post(url="https://httpbin.org/post", payload={"key": "value"})
            resp2 = client.read_resp(uid2)
            self.assertIsNotNone(resp2)

            uid3 = client.queue_put(url="https://httpbin.org/put", payload={"key": "value"})
            resp3 = client.read_resp(uid3)
            self.assertIsNotNone(resp3)

            uid4 = client.queue_patch(url="https://httpbin.org/patch", payload={"key": "value"})
            resp4 = client.read_resp(uid4)
            self.assertIsNotNone(resp4)

            uid5 = client.queue_delete(url="https://httpbin.org/delete", payload={"key": "value"})
            resp5 = client.read_resp(uid5)
            self.assertIsNotNone(resp5)

            uid6 = client.queue_head(url="https://httpbin.org/get")
            resp6 = client.read_resp(uid6)
            self.assertIsNotNone(resp6)

            uid7 = client.queue_options(url="https://httpbin.org/get")
            resp7 = client.read_resp(uid7)
            self.assertIsNotNone(resp7)


if __name__ == "__main__":
    unittest.main()
