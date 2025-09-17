import unittest
from typing import Any
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

    @patch("minibone.httpt.httpx.Client")
    def test_queue_operations(self, mock_client: Any) -> None:
        """Test basic queue and response operations."""
        # Setup mock responses
        mock_client.return_value.get.return_value.json.return_value = {
            "args": {"foo": "bar"},
            "url": "https://httpbin.org/anything?foo=bar",
        }
        mock_client.return_value.post.return_value.json.return_value = {"url": "https://httpbin.org/post"}

        # Test GET request
        uid1 = self.client.queue_get(url="https://httpbin.org/anything", params={"foo": "bar"})
        resp1 = self.client.read_resp(uid1)
        self.assertEqual(resp1["args"]["foo"], "bar")
        self.assertEqual(resp1["url"], "https://httpbin.org/anything?foo=bar")

        # Test POST request
        uid2 = self.client.queue_post(url="https://httpbin.org/post")
        resp2 = self.client.read_resp(uid2)
        self.assertEqual(resp2["url"], "https://httpbin.org/post")

    def test_async_operations(self) -> None:
        """Test async response retrieval."""
        with patch("minibone.httpt.httpx.Client") as mock_client:
            mock_client.return_value.get.return_value.json.return_value = {"test": "async"}

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

    @patch("minibone.httpt.httpx.Client")
    def test_all_http_methods(self, mock_client: Any) -> None:
        """Test all HTTP methods."""
        # Setup mock responses to return successful status codes
        mock_client.return_value.get.return_value.status_code = httpx.codes.OK
        mock_client.return_value.get.return_value.json.return_value = {"success": True}

        mock_client.return_value.post.return_value.status_code = httpx.codes.OK
        mock_client.return_value.post.return_value.json.return_value = {"success": True}

        mock_client.return_value.put.return_value.status_code = httpx.codes.OK
        mock_client.return_value.put.return_value.json.return_value = {"success": True}

        mock_client.return_value.patch.return_value.status_code = httpx.codes.OK
        mock_client.return_value.patch.return_value.json.return_value = {"success": True}

        mock_client.return_value.delete.return_value.status_code = httpx.codes.OK
        mock_client.return_value.delete.return_value.json.return_value = {"success": True}

        mock_client.return_value.head.return_value.status_code = httpx.codes.OK
        mock_client.return_value.head.return_value.headers = {"Content-Type": "application/json"}

        mock_client.return_value.options.return_value.status_code = httpx.codes.OK
        mock_client.return_value.options.return_value.headers = {
            "Allow": "GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS"
        }

        # Test that all methods can be called and return a response
        uid1 = self.client.queue_get(url="https://httpbin.org/get")
        resp1 = self.client.read_resp(uid1)
        self.assertIsNotNone(resp1)

        uid2 = self.client.queue_post(url="https://httpbin.org/post", payload={"key": "value"})
        resp2 = self.client.read_resp(uid2)
        self.assertIsNotNone(resp2)

        uid3 = self.client.queue_put(url="https://httpbin.org/put", payload={"key": "value"})
        resp3 = self.client.read_resp(uid3)
        self.assertIsNotNone(resp3)

        uid4 = self.client.queue_patch(url="https://httpbin.org/patch", payload={"key": "value"})
        resp4 = self.client.read_resp(uid4)
        self.assertIsNotNone(resp4)

        uid5 = self.client.queue_delete(url="https://httpbin.org/delete", payload={"key": "value"})
        resp5 = self.client.read_resp(uid5)
        self.assertIsNotNone(resp5)

        uid6 = self.client.queue_head(url="https://httpbin.org/get")
        resp6 = self.client.read_resp(uid6)
        self.assertIsNotNone(resp6)

        uid7 = self.client.queue_options(url="https://httpbin.org/get")
        resp7 = self.client.read_resp(uid7)
        self.assertIsNotNone(resp7)


if __name__ == "__main__":
    unittest.main()
