import json
import unittest

from minibone.httpt import HTTPt
from minibone.parallel_threads import PARThreads


class TestHTTPt(unittest.TestCase):
    def test_httpt(self):
        worker = PARThreads()
        worker.start()

        client = HTTPt(worker=worker)

        params = {"params": {"foo": "bar"}}

        # this could be in one thread
        uid1 = client.queue_get(url="https://httpbin.org/anything", params=params)

        # and this another could be in onether thread
        uid2 = client.queue_post(url="https://httpbin.org/post")

        resp1 = json.loads(client.read_resp(uid1))
        resp2 = client.read_resp(uid2)

        worker.stop()

        self.assertEqual(resp1["args"]["foo"], "bar")
        self.assertEqual(resp1["url"], "https://httpbin.org/anything?foo=bar")
        self.assertEqual(resp2["url"], "https://httpbin.org/post")


if __name__ == "__main__":
    unittest.main()
