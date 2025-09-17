import time
import unittest
from pathlib import Path
from typing import Any

from minibone.storing import Storing


class TestStoring(unittest.TestCase):
    """Test cases for Storing class."""

    def setUp(self) -> None:
        """Set up test files."""
        self.test_files: list[str] = []

    def tearDown(self) -> None:
        """Clean up test files."""
        for file in self.test_files:
            p = Path(file)
            p.unlink(missing_ok=True)

    def test_basic_json_operations(self) -> None:
        """Test basic JSON storage and retrieval operations."""
        data1: list[int] = [1, 4, 5, 6]
        data2: dict[str, Any] = {"key1": "val1", "key2": "val2", "list": [1, 2, 3]}

        storing = Storing(chunks=2, interval=1)
        storing.to_json(path="./", filename="storing1.json", data=data1)
        storing.to_json(path="./", filename="storing2.json", data=data2)
        storing.start()

        time.sleep(3)  # Reduced sleep time for faster tests

        files = ["./storing1.json", "./storing2.json"]
        self.test_files.extend(files)

        json1 = storing.from_json(files[0])
        json2 = storing.from_json(files[1])

        self.assertEqual(json1, [1, 4, 5, 6])
        self.assertEqual(json2, {"key1": "val1", "key2": "val2", "list": [1, 2, 3]})

        storing.stop()

    def test_storing_with_different_data_types(self) -> None:
        """Test storing various data types."""
        storing = Storing(chunks=10, interval=1)

        # Test with different data types (wrapped in dicts/lists as required)
        test_cases = [
            ("string_test.json", {"value": "hello world"}),
            ("number_test.json", {"value": 42}),
            ("float_test.json", {"value": 3.14}),
            ("bool_test.json", {"value": True}),
            ("null_test.json", {"value": None}),
            ("list_test.json", [1, 2, 3, 4, 5]),
            ("nested_test.json", {"nested": {"deep": {"value": 100}}}),
        ]

        for filename, data in test_cases:
            storing.to_json(path="./", filename=filename, data=data)
            self.test_files.append(f"./{filename}")

        storing.start()
        time.sleep(3)

        # Verify all data was stored correctly
        for filename, expected_data in test_cases:
            result = storing.from_json(f"./{filename}")
            self.assertEqual(result, expected_data)

        storing.stop()

    def test_storing_stop_immediately(self) -> None:
        """Test stopping storage immediately."""
        storing = Storing(chunks=1, interval=1)
        storing.to_json(path="./", filename="immediate_stop.json", data={"test": "data"})
        self.test_files.append("./immediate_stop.json")

        storing.start()
        storing.stop()  # Stop immediately

        # File should still be created
        result = storing.from_json("./immediate_stop.json")
        self.assertEqual(result, {"test": "data"})

    def test_invalid_file_operations(self) -> None:
        """Test operations with invalid files."""
        storing = Storing(chunks=1, interval=1)

        # Test reading non-existent file
        with self.assertRaises(FileNotFoundError):
            storing.from_json("./non_existent.json")

        # Test with invalid path
        with self.assertRaises(FileNotFoundError):
            storing.from_json("/invalid/path/file.json")

    def test_concurrent_operations(self) -> None:
        """Test concurrent storage operations."""
        storing = Storing(chunks=5, interval=1)

        # Store multiple items quickly
        for i in range(10):
            storing.to_json(path="./", filename=f"concurrent_{i}.json", data={"index": i})
            self.test_files.append(f"./concurrent_{i}.json")

        storing.start()
        time.sleep(3)  # Allow time for processing
        storing.stop()

        # Verify all files were created
        for i in range(10):
            result = storing.from_json(f"./concurrent_{i}.json")
            self.assertEqual(result, {"index": i})


if __name__ == "__main__":
    unittest.main()
