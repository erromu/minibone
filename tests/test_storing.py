import time
import unittest
from pathlib import Path

from minibone.storing import Storing


class TestStoring(unittest.TestCase):
    def test_settings(self):
        data1 = [1, 4, 5, 6]
        data2 = {"key1": "val1", "key2": "val2", "list": [1, 2, 3]}
        storing = Storing(chunks=2, interval=1)
        storing.to_json(path="./", filename="storing1.json", data=data1)
        storing.to_json(path="./", filename="storing2.json", data=data2)
        storing.start()

        time.sleep(5)

        files = ["./storing1.json", "./storing2.json"]

        json1 = storing.from_json(files[0])
        json2 = storing.from_json(files[1])

        self.assertEqual(json1, [1, 4, 5, 6])
        self.assertEqual(json2, {"key1": "val1", "key2": "val2", "list": [1, 2, 3]})

        storing.stop()

        for file in files:
            p = Path(file)
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
