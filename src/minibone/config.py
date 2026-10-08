"""Configuration file handling with validation and atomic writes.

Supports TOML, YAML, and JSON with:
- Sync and async load/save
- Deep merge of defaults, file contents, and overrides
- Type and key validation
- Atomic file writes (temp file + os.replace)
- Exception hierarchy (ConfigError and subclasses)

Precedence for the ``from_*`` constructors (lowest to highest):
    defaults < file contents < overrides

``overrides`` is intended for layering values from other sources — env vars,
CLI args, tests — without ``Config`` needing to know where they came from.

Security note:
    ``filepath`` is resolved via ``Path.resolve()``. No attempt is made to
    confine it to a subdirectory — that is the caller's responsibility. If
    you need containment, validate the path yourself before passing it in.
"""

from __future__ import annotations

import contextlib
import copy as _copy
import hashlib
import json
import logging
import os
import re
import tempfile
import warnings
from datetime import date
from datetime import datetime
from datetime import time
from enum import Enum
from pathlib import Path
from typing import Any

import aiofiles
import tomlkit
import yaml


class FORMAT(Enum):
    TOML = "TOML"
    YAML = "YAML"
    JSON = "JSON"


class ConfigError(Exception):
    """Base exception for Config-related errors."""


class ConfigParseError(ConfigError):
    """Raised when a configuration file cannot be parsed."""


class ConfigFileNotFoundError(ConfigError):
    """Raised when a configuration file does not exist."""


class ConfigValidationError(ConfigError):
    """Raised when a configuration value fails validation."""


class Config(dict):
    """Settings container with validation and file I/O.

    Values may be str, int, float, list, dict, bool, datetime, date, time,
    or None. Keys must start with a lowercase letter and contain only ASCII
    word characters.
    """

    _ALLOWED_TYPES = (str, int, float, list, dict, bool, datetime, date, time, type(None))
    _KEY_PATTERN = re.compile(r"^[a-z][a-zA-Z0-9_]*$")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_path(cls, filepath: str) -> Path:
        """Resolve a filepath to an absolute Path.

        Raises ConfigValidationError if the input is not a non-empty string.
        """
        if not isinstance(filepath, str) or not filepath.strip():
            raise ConfigValidationError("filepath must be a non-empty string")
        return Path(filepath).expanduser().resolve()

    # ------------------------------------------------------------------
    # Parse / serialize (shared by sync and async paths)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_format(format: FORMAT) -> None:
        if not isinstance(format, FORMAT):
            raise ConfigValidationError(f"format must be a FORMAT enum, got {type(format)}")

    @staticmethod
    def _check_data(data: Any) -> None:
        if not isinstance(data, (dict, list)):
            raise ConfigValidationError(f"data must be dict or list, got {type(data).__name__}")

    @staticmethod
    def _check_overrides(overrides: dict | None) -> None:
        if overrides is not None and not isinstance(overrides, dict):
            raise ConfigValidationError(f"overrides must be a dict or None, got {type(overrides).__name__}")

    @staticmethod
    def _parse(format: FORMAT, content: str, source: str) -> dict:
        """Parse ``content`` as ``format`` and return a dict."""
        if format == FORMAT.TOML:
            data = tomlkit.loads(content)
        elif format == FORMAT.YAML:
            data = yaml.safe_load(content)
        elif format == FORMAT.JSON:
            data = json.loads(content)
        else:
            raise ConfigParseError(f"Unsupported format: {format.value}")

        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ConfigParseError(f"Expected dict at root of {source}, got {type(data).__name__}")
        return data

    @staticmethod
    def _serialize(format: FORMAT, data: dict | list) -> str:
        """Serialize ``data`` to a string in ``format``."""
        if format == FORMAT.TOML:
            return tomlkit.dumps(data)
        elif format == FORMAT.YAML:
            return yaml.dump(data, default_flow_style=False, allow_unicode=True)
        elif format == FORMAT.JSON:
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            raise ConfigParseError(f"Unsupported format: {format.value}")

    # ------------------------------------------------------------------
    # Load (sync)
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, format: FORMAT, filepath: str) -> dict:
        """Load a file and return its contents as a dict."""
        cls._check_format(format)
        path = cls._resolve_path(filepath)

        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise ConfigFileNotFoundError(f"Configuration file not found: {filepath}") from e
        except IsADirectoryError as e:
            raise ConfigFileNotFoundError(f"Path is not a file: {filepath}") from e
        except UnicodeDecodeError as e:
            raise ConfigParseError(f"File encoding error in {filepath}: {e}") from e
        except OSError as e:
            raise ConfigFileNotFoundError(f"Cannot read file {filepath}: {e}") from e

        try:
            return cls._parse(format, content, filepath)
        except (tomlkit.exceptions.ParseError, yaml.YAMLError, json.JSONDecodeError) as e:
            raise ConfigParseError(f"Failed to parse {format.value} file {filepath}: {e}") from e

    # ------------------------------------------------------------------
    # Load (async)
    # ------------------------------------------------------------------

    @classmethod
    async def aiofrom_file(cls, format: FORMAT, filepath: str) -> dict:
        """Load a file and return its contents as a dict (async)."""
        cls._check_format(format)
        path = cls._resolve_path(filepath)

        try:
            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()
        except FileNotFoundError as e:
            raise ConfigFileNotFoundError(f"Configuration file not found: {filepath}") from e
        except IsADirectoryError as e:
            raise ConfigFileNotFoundError(f"Path is not a file: {filepath}") from e
        except UnicodeDecodeError as e:
            raise ConfigParseError(f"File encoding error in {filepath}: {e}") from e
        except OSError as e:
            raise ConfigFileNotFoundError(f"Cannot read file {filepath}: {e}") from e

        try:
            return cls._parse(format, content, filepath)
        except (tomlkit.exceptions.ParseError, yaml.YAMLError, json.JSONDecodeError) as e:
            raise ConfigParseError(f"Failed to parse {format.value} file {filepath}: {e}") from e

    # ------------------------------------------------------------------
    # Save (sync)
    # ------------------------------------------------------------------

    @classmethod
    def to_file(cls, format: FORMAT, filepath: str, data: dict | list) -> None:
        """Serialize ``data`` and write it atomically."""
        cls._check_format(format)
        cls._check_data(data)
        path = cls._resolve_path(filepath)

        try:
            content = cls._serialize(format, data)
        except (TypeError, ValueError) as e:
            raise ConfigError(f"Failed to serialize {format.value}: {e}") from e

        cls._atomic_write(path, content, format)

    # ------------------------------------------------------------------
    # Save (async)
    # ------------------------------------------------------------------

    @classmethod
    async def aioto_file(cls, format: FORMAT, filepath: str, data: dict | list) -> None:
        """Serialize ``data`` and write it atomically (async)."""
        cls._check_format(format)
        cls._check_data(data)
        path = cls._resolve_path(filepath)

        try:
            content = cls._serialize(format, data)
        except (TypeError, ValueError) as e:
            raise ConfigError(f"Failed to serialize {format.value}: {e}") from e

        await cls._aio_atomic_write(path, content, format)

    # ------------------------------------------------------------------
    # Atomic write helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _atomic_write(path: Path, content: str, format: FORMAT) -> None:
        """Write to a temp file in the target directory, fsync, then rename."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ConfigError(f"Cannot create directory for {path}: {e}") from e

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name

            os.replace(tmp_path, path)
            tmp_path = None
        except OSError as e:
            raise ConfigError(f"Failed to write {format.value} file {path}: {e}") from e
        finally:
            if tmp_path is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)

    @staticmethod
    async def _aio_atomic_write(path: Path, content: str, format: FORMAT) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ConfigError(f"Cannot create directory for {path}: {e}") from e

        tmp_path: str | None = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
            )
            os.close(fd)

            async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
                await f.write(content)

            os.replace(tmp_path, path)
            tmp_path = None
        except OSError as e:
            raise ConfigError(f"Failed to write {format.value} file {path}: {e}") from e
        finally:
            if tmp_path is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_toml(
        cls,
        filepath: str,
        defaults: dict | None = None,
        overrides: dict | None = None,
    ) -> Config:
        """Load TOML, layered as: defaults < file < overrides."""
        settings = cls.from_file(FORMAT.TOML, filepath)
        return Config(cls._layer(defaults, settings, overrides), filepath)

    @classmethod
    def from_yaml(
        cls,
        filepath: str,
        defaults: dict | None = None,
        overrides: dict | None = None,
    ) -> Config:
        """Load YAML, layered as: defaults < file < overrides."""
        settings = cls.from_file(FORMAT.YAML, filepath)
        return Config(cls._layer(defaults, settings, overrides), filepath)

    @classmethod
    def from_json(
        cls,
        filepath: str,
        defaults: dict | None = None,
        overrides: dict | None = None,
    ) -> Config:
        """Load JSON, layered as: defaults < file < overrides."""
        settings = cls.from_file(FORMAT.JSON, filepath)
        return Config(cls._layer(defaults, settings, overrides), filepath)

    @classmethod
    async def aiofrom_toml(
        cls,
        filepath: str,
        defaults: dict | None = None,
        overrides: dict | None = None,
    ) -> Config:
        """Load TOML, layered as: defaults < file < overrides (async)."""
        settings = await cls.aiofrom_file(FORMAT.TOML, filepath)
        return Config(cls._layer(defaults, settings, overrides), filepath)

    @classmethod
    async def aiofrom_yaml(
        cls,
        filepath: str,
        defaults: dict | None = None,
        overrides: dict | None = None,
    ) -> Config:
        """Load YAML, layered as: defaults < file < overrides (async)."""
        settings = await cls.aiofrom_file(FORMAT.YAML, filepath)
        return Config(cls._layer(defaults, settings, overrides), filepath)

    @classmethod
    async def aiofrom_json(
        cls,
        filepath: str,
        defaults: dict | None = None,
        overrides: dict | None = None,
    ) -> Config:
        """Load JSON, layered as: defaults < file < overrides (async)."""
        settings = await cls.aiofrom_file(FORMAT.JSON, filepath)
        return Config(cls._layer(defaults, settings, overrides), filepath)

    @classmethod
    def _layer(
        cls,
        defaults: dict | None,
        file_data: dict,
        overrides: dict | None,
    ) -> dict:
        """Apply the precedence chain: defaults < file_data < overrides."""
        cls._check_overrides(overrides)
        merged = cls.merge(defaults, file_data)
        if overrides:
            merged = cls.merge(merged, overrides)
        return merged

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    @classmethod
    def merge(
        cls,
        defaults: dict | None = None,
        settings: dict | None = None,
        _visited: set[int] | None = None,
    ) -> dict:
        """Deep-merge ``settings`` over ``defaults``.

        Nested dicts are merged recursively; all other values are replaced.
        ``_visited`` tracks dict object ids along the current path to
        prevent infinite recursion if the same dict is merged into itself.
        It is not full cycle detection: a self-referencing dict that is
        never traversed on both sides is passed through by reference.

        Raises ConfigValidationError on non-dict inputs or on detected
        recursion.
        """
        if _visited is None:
            _visited = set()

        if defaults is None:
            defaults = {}
        if settings is None:
            settings = {}

        if not isinstance(defaults, dict):
            raise ConfigValidationError(f"defaults must be a dict, got {type(defaults).__name__}")
        if not isinstance(settings, dict):
            raise ConfigValidationError(f"settings must be a dict, got {type(settings).__name__}")

        settings_id = id(settings)
        if settings_id in _visited:
            raise ConfigValidationError("Recursive reference detected while merging settings.")
        _visited.add(settings_id)

        result = dict(defaults)
        for key, value in settings.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls.merge(result[key], value, _visited.copy())
            else:
                result[key] = value
        return result

    # ------------------------------------------------------------------
    # Instance
    # ------------------------------------------------------------------

    def __init__(self, settings: dict | None = None, filepath: str | None = None):
        if settings is None:
            settings = {}
        if not isinstance(settings, dict):
            raise ConfigValidationError(f"settings must be a dict, got {type(settings).__name__}")
        if filepath is not None and not isinstance(filepath, str):
            raise ConfigValidationError(f"filepath must be str or None, got {type(filepath).__name__}")

        self._logger = logging.getLogger(self.__class__.__name__)
        self.filepath = filepath

        super().__init__()
        for key, value in settings.items():
            self._validate_and_set(key, value)

    def _validate_and_set(self, key: str, value: Any) -> None:
        if not isinstance(key, str):
            raise ConfigValidationError(f"key must be str, got {type(key).__name__}")
        if not self._KEY_PATTERN.match(key):
            raise ConfigValidationError(
                f"Invalid key '{key}'. Must start with lowercase a-z and contain only "
                f"ASCII letters, digits, and underscores."
            )
        if not isinstance(value, self._ALLOWED_TYPES):
            raise ConfigValidationError(
                f"Invalid value type for key '{key}': {type(value).__name__}. "
                f"Allowed types: {', '.join(t.__name__ for t in self._ALLOWED_TYPES)}"
            )
        dict.__setitem__(self, key, value)

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------

    @property
    def sha256(self) -> str:
        """SHA-256 of a canonical JSON representation of the settings."""
        canonical = json.dumps(dict(self), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def sha1(self) -> str:
        """Deprecated. Use :attr:`sha256` instead."""
        warnings.warn(
            "Config.sha1 is deprecated and insecure. Use Config.sha256 instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        legacy_json = json.dumps(dict(self), default=str)
        return hashlib.sha1(legacy_json.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Instance save
    # ------------------------------------------------------------------

    def _tofile(self, format: FORMAT) -> None:
        if not self.filepath:
            raise ConfigValidationError("No filepath defined for this Config instance")
        self.to_file(format=format, filepath=self.filepath, data=dict(self))

    async def _aiotofile(self, format: FORMAT) -> None:
        if not self.filepath:
            raise ConfigValidationError("No filepath defined for this Config instance")
        await self.aioto_file(format=format, filepath=self.filepath, data=dict(self))

    def to_toml(self) -> None:
        self._tofile(FORMAT.TOML)

    def to_yaml(self) -> None:
        self._tofile(FORMAT.YAML)

    def to_json(self) -> None:
        self._tofile(FORMAT.JSON)

    async def aioto_toml(self) -> None:
        await self._aiotofile(FORMAT.TOML)

    async def aioto_yaml(self) -> None:
        await self._aiotofile(FORMAT.YAML)

    async def aioto_json(self) -> None:
        await self._aiotofile(FORMAT.JSON)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, key: str, value: Any) -> None:
        """Add or replace a setting."""
        self._validate_and_set(key, value)

    def remove(self, key: str) -> None:
        """Remove a setting. No-op if the key does not exist."""
        if not isinstance(key, str):
            raise ConfigValidationError(f"key must be str, got {type(key).__name__}")
        with contextlib.suppress(KeyError):
            del self[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._validate_and_set(key, value)

    def __delitem__(self, key: str) -> None:
        if not isinstance(key, str):
            raise ConfigValidationError(f"key must be str, got {type(key).__name__}")
        dict.__delitem__(self, key)

    def update(self, *args, **kwargs) -> None:
        """Validate-and-set each item from a mapping, iterable of pairs, or kwargs."""
        if args:
            if len(args) > 1:
                raise TypeError(f"update expected at most 1 argument, got {len(args)}")
            other = args[0]
            items = other.items() if isinstance(other, dict) else other
            for key, value in items:
                self._validate_and_set(key, value)
        for key, value in kwargs.items():
            self._validate_and_set(key, value)

    # ------------------------------------------------------------------
    # Copies and dunders
    # ------------------------------------------------------------------

    def copy(self) -> dict:
        """Shallow copy as a plain dict."""
        return dict(self)

    def deep_copy(self) -> dict:
        """Deep copy as a plain dict. Preserves datetime, date, and time objects."""
        return _copy.deepcopy(dict(self))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(filepath={self.filepath!r}, settings={dict(self)!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, dict):
            return NotImplemented
        return dict(self) == dict(other)

    def __hash__(self) -> int:
        raise TypeError("Config objects are unhashable")
