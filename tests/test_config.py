import asyncio
import tempfile
import unittest
from pathlib import Path

from minibone.config import FORMAT
from minibone.config import Config


class TestConfig(unittest.TestCase):
    def setUp(self) -> None:
        """Create temp dir and sample config for tests."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sample_config = {"setting1": "value1", "setting2": 2, "setting3": True, "nested": {"a": 1, "b": 2}}

    def tearDown(self) -> None:
        """Clean up temp dir."""
        self.temp_dir.cleanup()

    def test_basic_operations(self) -> None:
        """Test basic config get/set/remove operations."""
        cfg = Config(settings=self.sample_config, filepath=None)

        self.assertEqual(cfg.sha1, "c0db7517c05268c8bf70e63a9b10defc93556d4d")
        self.assertEqual(cfg.get("setting1", None), "value1")
        self.assertEqual(cfg.get("setting10", None), None)
        self.assertEqual(cfg.get("setting2", None), 2)
        self.assertEqual(cfg.get("setting3", None), True)

        cfg.remove("setting1")
        cfg.add("setting3", False)

        self.assertEqual(cfg.get("setting1", None), None)
        self.assertEqual(cfg.get("setting3", None), False)

    def test_merge_operations(self) -> None:
        """Test config merge functionality."""
        cfg = Config()

        # Test basic merges
        self.assertEqual(cfg.merge({}, {}), {})
        self.assertEqual(cfg.merge(defaults={"x": 1}), {"x": 1})
        self.assertEqual(cfg.merge(settings={"x": 1}), {"x": 1})
        self.assertEqual(cfg.merge(defaults={"x": 1}, settings={"y": 2}), {"x": 1, "y": 2})
        self.assertEqual(cfg.merge(defaults={"z": 1}, settings={"z": 4}), {"z": 4})

        # Test nested merge
        defaults = {"a": 1, "nested": {"x": 10}}
        settings = {"b": 2, "nested": {"y": 20}}
        expected = {"a": 1, "b": 2, "nested": {"x": 10, "y": 20}}
        self.assertEqual(cfg.merge(defaults, settings), expected)

    def test_file_operations(self) -> None:
        """Test config file I/O operations."""
        # Test sync file operations
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = str(Path(self.temp_dir.name) / f"test.{fmt.value.lower()}")
                cfg = Config(settings=self.sample_config, filepath=filepath)

                # Test write
                if fmt == FORMAT.TOML:
                    cfg.to_toml()
                elif fmt == FORMAT.YAML:
                    cfg.to_yaml()
                elif fmt == FORMAT.JSON:
                    cfg.to_json()

                # Test read
                if fmt == FORMAT.TOML:
                    loaded = Config.from_toml(filepath)
                elif fmt == FORMAT.YAML:
                    loaded = Config.from_yaml(filepath)
                elif fmt == FORMAT.JSON:
                    loaded = Config.from_json(filepath)

                self.assertEqual(loaded, cfg)

    def test_async_file_operations(self) -> None:
        """Test async config file I/O operations."""
        # Test async file operations
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = str(Path(self.temp_dir.name) / f"async_test.{fmt.value.lower()}")
                cfg = Config(settings=self.sample_config, filepath=filepath)

                # Test async write
                if fmt == FORMAT.TOML:
                    asyncio.run(cfg.aioto_toml())
                elif fmt == FORMAT.YAML:
                    asyncio.run(cfg.aioto_yaml())
                elif fmt == FORMAT.JSON:
                    asyncio.run(cfg.aioto_json())

                # Test async read
                if fmt == FORMAT.TOML:
                    loaded = asyncio.run(Config.aiofrom_toml(filepath))
                elif fmt == FORMAT.YAML:
                    loaded = asyncio.run(Config.aiofrom_yaml(filepath))
                elif fmt == FORMAT.JSON:
                    loaded = asyncio.run(Config.aiofrom_json(filepath))

                self.assertEqual(loaded, cfg)

    def test_error_handling(self) -> None:
        """Test config error cases."""
        # Test invalid settings
        with self.assertRaises(AssertionError):
            Config(settings="invalid")  # type: ignore

        # Test invalid merge inputs
        with self.assertRaises(AssertionError):
            cfg = Config()
            cfg.merge(defaults="invalid", settings={})  # type: ignore


if __name__ == "__main__":
    unittest.main()
