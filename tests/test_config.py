"""Tests for minibone.config.

Follows the style of the other minibone test modules: unittest, one temp
directory per test, subtests for format variants.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from minibone.config import FORMAT
from minibone.config import Config
from minibone.config import ConfigFileNotFoundError
from minibone.config import ConfigParseError
from minibone.config import ConfigValidationError


class TestConfig(unittest.TestCase):
    def setUp(self) -> None:
        """Create temp dir and sample config for tests."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sample_config = {
            "setting1": "value1",
            "setting2": 2,
            "setting3": True,
            "nested": {"a": 1, "b": 2},
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _path(self, name: str) -> str:
        return str(Path(self.temp_dir.name) / name)

    def _write(self, fmt: FORMAT, filepath: str, data: dict) -> None:
        """Write `data` to `filepath` in `fmt` synchronously."""
        if fmt == FORMAT.TOML:
            Config.to_file(FORMAT.TOML, filepath, data)
        elif fmt == FORMAT.YAML:
            Config.to_file(FORMAT.YAML, filepath, data)
        elif fmt == FORMAT.JSON:
            Config.to_file(FORMAT.JSON, filepath, data)
        else:
            raise AssertionError(f"Unhandled format: {fmt}")

    def _load(self, fmt: FORMAT, filepath: str, **kwargs) -> Config:
        """Load `filepath` in `fmt` synchronously, passing through kwargs."""
        if fmt == FORMAT.TOML:
            return Config.from_toml(filepath, **kwargs)
        if fmt == FORMAT.YAML:
            return Config.from_yaml(filepath, **kwargs)
        if fmt == FORMAT.JSON:
            return Config.from_json(filepath, **kwargs)
        raise AssertionError(f"Unhandled format: {fmt}")

    async def _aload(self, fmt: FORMAT, filepath: str, **kwargs) -> Config:
        """Load `filepath` in `fmt` asynchronously, passing through kwargs."""
        if fmt == FORMAT.TOML:
            return await Config.aiofrom_toml(filepath, **kwargs)
        if fmt == FORMAT.YAML:
            return await Config.aiofrom_yaml(filepath, **kwargs)
        if fmt == FORMAT.JSON:
            return await Config.aiofrom_json(filepath, **kwargs)
        raise AssertionError(f"Unhandled format: {fmt}")

    # ------------------------------------------------------------------
    # Basic operations
    # ------------------------------------------------------------------

    def test_basic_operations(self) -> None:
        """Test basic config get/set/remove operations."""
        cfg = Config(settings=self.sample_config, filepath=None)

        self.assertEqual(
            cfg.sha256,
            "7575995cf1eee201891c0d3b72fa5db0dae4635efcda1dedc133d1709d23750e",
        )
        self.assertEqual(cfg.get("setting1", None), "value1")
        self.assertEqual(cfg.get("setting10", None), None)
        self.assertEqual(cfg.get("setting2", None), 2)
        self.assertEqual(cfg.get("setting3", None), True)

        cfg.remove("setting1")
        cfg.add("setting3", False)

        self.assertEqual(cfg.get("setting1", None), None)
        self.assertEqual(cfg.get("setting3", None), False)

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def test_merge_operations(self) -> None:
        """Test config merge functionality."""
        cfg = Config()

        self.assertEqual(cfg.merge({}, {}), {})
        self.assertEqual(cfg.merge(defaults={"x": 1}), {"x": 1})
        self.assertEqual(cfg.merge(settings={"x": 1}), {"x": 1})
        self.assertEqual(cfg.merge(defaults={"x": 1}, settings={"y": 2}), {"x": 1, "y": 2})
        self.assertEqual(cfg.merge(defaults={"z": 1}, settings={"z": 4}), {"z": 4})

        defaults = {"a": 1, "nested": {"x": 10}}
        settings = {"b": 2, "nested": {"y": 20}}
        expected = {"a": 1, "b": 2, "nested": {"x": 10, "y": 20}}
        self.assertEqual(cfg.merge(defaults, settings), expected)

    # ------------------------------------------------------------------
    # File I/O (sync)
    # ------------------------------------------------------------------

    def test_file_operations(self) -> None:
        """Test config file I/O operations."""
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = self._path(f"test.{fmt.value.lower()}")
                cfg = Config(settings=self.sample_config, filepath=filepath)

                if fmt == FORMAT.TOML:
                    cfg.to_toml()
                elif fmt == FORMAT.YAML:
                    cfg.to_yaml()
                elif fmt == FORMAT.JSON:
                    cfg.to_json()

                loaded = self._load(fmt, filepath)
                self.assertEqual(loaded, cfg)

    # ------------------------------------------------------------------
    # File I/O (async)
    # ------------------------------------------------------------------

    def test_async_file_operations(self) -> None:
        """Test async config file I/O operations."""
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = self._path(f"async_test.{fmt.value.lower()}")
                cfg = Config(settings=self.sample_config, filepath=filepath)

                if fmt == FORMAT.TOML:
                    asyncio.run(cfg.aioto_toml())
                elif fmt == FORMAT.YAML:
                    asyncio.run(cfg.aioto_yaml())
                elif fmt == FORMAT.JSON:
                    asyncio.run(cfg.aioto_json())

                loaded = asyncio.run(self._aload(fmt, filepath))
                self.assertEqual(loaded, cfg)

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def test_overrides_precedence(self) -> None:
        """defaults < file < overrides, applied recursively."""
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = self._path(f"override.{fmt.value.lower()}")
                file_data = {
                    "a": "from_file",
                    "nested": {"x": "from_file", "y": "from_file"},
                }
                self._write(fmt, filepath, file_data)

                defaults = {
                    "a": "from_defaults",
                    "b": "from_defaults",
                    "nested": {"x": "from_defaults", "z": "from_defaults"},
                }
                overrides = {
                    "b": "from_overrides",
                    "nested": {"y": "from_overrides", "w": "from_overrides"},
                }

                cfg = self._load(fmt, filepath, defaults=defaults, overrides=overrides)

                # a: file wins over defaults.
                self.assertEqual(cfg["a"], "from_file")
                # b: overrides win over defaults; no file value present.
                self.assertEqual(cfg["b"], "from_overrides")
                # nested.x: file wins over defaults.
                self.assertEqual(cfg["nested"]["x"], "from_file")
                # nested.y: overrides win over file.
                self.assertEqual(cfg["nested"]["y"], "from_overrides")
                # nested.z: only in defaults; survives.
                self.assertEqual(cfg["nested"]["z"], "from_defaults")
                # nested.w: only in overrides; added.
                self.assertEqual(cfg["nested"]["w"], "from_overrides")

    def test_overrides_optional(self) -> None:
        """Omitting overrides is equivalent to passing an empty dict."""
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = self._path(f"no_override.{fmt.value.lower()}")
                self._write(fmt, filepath, {"a": 1})

                cfg_none = self._load(fmt, filepath, defaults={"b": 2})
                cfg_empty = self._load(fmt, filepath, defaults={"b": 2}, overrides={})
                self.assertEqual(cfg_none, cfg_empty)

    def test_overrides_none_values_do_not_delete(self) -> None:
        """An override of None wins like any other value (merge, not delete)."""
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = self._path(f"override_none.{fmt.value.lower()}")
                self._write(fmt, filepath, {"keep": "x"})

                cfg = self._load(fmt, filepath, overrides={"keep": None})
                self.assertIsNone(cfg["keep"])

    def test_overrides_invalid_type_raises(self) -> None:
        """Non-dict overrides are rejected before merge."""
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = self._path(f"bad_override.{fmt.value.lower()}")
                self._write(fmt, filepath, {"a": 1})

                with self.assertRaises(ConfigValidationError):
                    self._load(fmt, filepath, overrides="not a dict")  # type: ignore[arg-type]

    def test_async_overrides(self) -> None:
        """Async loaders honor overrides with the same precedence."""
        for fmt in FORMAT:
            with self.subTest(format=fmt):
                filepath = self._path(f"async_override.{fmt.value.lower()}")
                self._write(fmt, filepath, {"a": "file"})

                async def run(fmt, filepath) -> Config:
                    return await self._aload(
                        fmt,
                        filepath,
                        defaults={"a": "default", "b": "default"},
                        overrides={"a": "override"},
                    )

                cfg = asyncio.run(run(fmt, filepath))
                self.assertEqual(cfg["a"], "override")
                self.assertEqual(cfg["b"], "default")

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_error_handling(self) -> None:
        """Test config error cases."""
        with self.assertRaises(ConfigValidationError):
            Config(settings="invalid")  # type: ignore[arg-type]

        with self.assertRaises(ConfigValidationError):
            cfg = Config()
            cfg.merge(defaults="invalid", settings={})  # type: ignore[arg-type]

    def test_missing_file_raises(self) -> None:
        missing = self._path("does_not_exist.toml")
        with self.assertRaises(ConfigFileNotFoundError):
            Config.from_toml(missing)

    def test_parse_error_raises(self) -> None:
        filepath = self._path("bad.toml")
        Path(filepath).write_text("this is not [ valid toml", encoding="utf-8")
        with self.assertRaises(ConfigParseError):
            Config.from_toml(filepath)

    def test_invalid_key_pattern_rejected(self) -> None:
        with self.assertRaises(ConfigValidationError):
            Config(settings={"BadKey": 1})

    def test_invalid_value_type_rejected(self) -> None:
        with self.assertRaises(ConfigValidationError):
            Config(settings={"good_key": object()})


if __name__ == "__main__":
    unittest.main()
