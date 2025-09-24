import unittest
from unittest.mock import patch

import httpx

from minibone.httpt import HTTPt
from minibone.httpt import Verbs
from minibone.io_threads import IOThreads


class TestHTTPt(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test worker and client."""
        self.worker = IOThreads()
        self.client = HTTPt(worker=self.worker)

    def tearDown(self) -> None:
        """Clean up worker."""
        self.worker.shutdown()

    def test_queue_operations(self) -> None:
        """Test basic queue and response operations."""
        with patch("minibone.httpt.httpx.Client") as mock_client_class:
            # Setup mock responses
            mock_client = mock_client_class.return_value
            mock_response_get = mock_client.get.return_value
            mock_response_get.status_code = 200
            mock_response_get.json.return_value = {
                "args": {"foo": "bar"},
                "url": "https://httpbin.org/anything?foo=bar",
            }

            mock_response_post = mock_client.post.return_value
            mock_response_post.status_code = 200
            mock_response_post.json.return_value = {"url": "https://httpbin.org/post"}

            # Create client with mocked httpx.Client
            client = HTTPt(worker=self.worker)

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
        with patch("minibone.httpt.httpx.Client") as mock_client:
            mock_response = mock_client.return_value.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"test": "async"}

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

    def test_all_http_methods(self) -> None:
        """Test all HTTP methods."""
        with patch("minibone.httpt.httpx.Client") as mock_client_class:
            # Setup mock responses to return successful status codes
            mock_client = mock_client_class.return_value
            mock_response_get = mock_client.get.return_value
            mock_response_get.status_code = httpx.codes.OK
            mock_response_get.json.return_value = {"success": True}

            mock_response_post = mock_client.post.return_value
            mock_response_post.status_code = httpx.codes.OK
            mock_response_post.json.return_value = {"success": True}

            mock_response_put = mock_client.put.return_value
            mock_response_put.status_code = httpx.codes.OK
            mock_response_put.json.return_value = {"success": True}

            mock_response_patch = mock_client.patch.return_value
            mock_response_patch.status_code = httpx.codes.OK
            mock_response_patch.json.return_value = {"success": True}

            mock_response_delete = mock_client.delete.return_value
            mock_response_delete.status_code = httpx.codes.OK
            mock_response_delete.json.return_value = {"success": True}

            mock_response_head = mock_client.head.return_value
            mock_response_head.status_code = httpx.codes.OK
            mock_response_head.headers = {"Content-Type": "application/json"}

            mock_response_options = mock_client.options.return_value
            mock_response_options.status_code = httpx.codes.OK
            mock_response_options.headers = {"Allow": "GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS"}

            # Create client with mocked httpx.Client
            client = HTTPt(worker=self.worker)

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
