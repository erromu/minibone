import hashlib
import json
import logging
import re
from datetime import date
from datetime import datetime
from datetime import time
from enum import Enum
from pathlib import Path

import aiofiles
import tomlkit
import yaml


class FORMAT(Enum):
    TOML = "TOML"
    YAML = "YAML"
    JSON = "JSON"


class Config(dict):
    """Class to have settings in memory or in a configuration file"""

    @classmethod
    def from_file(cls, format: FORMAT, filepath: str):
        """Load a file and return the content in the specified FORMAT

        Arguments
        ---------
        format      FORMAT  A valid config.FORMAT value (TOML, YAML, JSON)
        filepath:   str     The filepath of the file to load

        Returns
        -------
        dict | None: Parsed config data or None on error
        """
        assert isinstance(format, FORMAT)
        assert isinstance(filepath, str) and len(filepath) > 0

        data = None

        try:
            file = f"{filepath}"
            with open(file, encoding="utf-8") as f:
                if format == FORMAT.TOML:
                    data = tomlkit.load(f)
                elif format == FORMAT.YAML:
                    data = yaml.safe_load(f)
                elif format == FORMAT.JSON:
                    data = json.load(f)

        except Exception as e:
            logger = logging.getLogger(__class__.__name__)
            logger.error("from_file %s error loading %s. %s", format.value, filepath, e)

        return data

    @classmethod
    async def aiofrom_file(cls, format: FORMAT, filepath: str):
        """Load a file in async mode and return the content in the specified FORMAT

        Arguments
        ---------
        format      FORMAT  A valid config.FORMAT value (TOML, YAML, JSON)
        filepath:   str     The filepath of the file to load

        Returns
        -------
        dict | None: Parsed config data or None on error
        """
        assert isinstance(format, FORMAT)
        assert isinstance(filepath, str) and len(filepath) > 0

        data = None

        try:
            file = f"{filepath}"
            async with aiofiles.open(file, encoding="utf-8") as f:
                if format == FORMAT.TOML:
                    data = tomlkit.loads(await f.read())
                elif format == FORMAT.YAML:
                    data = yaml.safe_load(await f.read())
                elif format == FORMAT.JSON:
                    data = json.loads(await f.read())

        except Exception as e:
            logger = logging.getLogger(__class__.__name__)
            logger.error("aiofrom_file %s error loading %s. %s", format.value, filepath, e)

        return data

    @classmethod
    def from_toml(cls, filepath: str, defaults: dict = None):
        """Load a toml configuration file and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        settings = cls.from_file(FORMAT.TOML, filepath)
        return Config(cls.merge(defaults, settings), filepath)

    @classmethod
    def from_yaml(cls, filepath: str, defaults: dict = None):
        """Load a yaml configuration file and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        settings = cls.from_file(FORMAT.YAML, filepath)
        return Config(cls.merge(defaults, settings), filepath)

    @classmethod
    def from_json(cls, filepath: str, defaults: dict = None):
        """Load a json configuration file and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        settings = cls.from_file(FORMAT.JSON, filepath)
        return Config(cls.merge(defaults, settings), filepath)

    @classmethod
    async def aiofrom_toml(cls, filepath: str, defaults: dict = None):
        """Load a toml configuration file in async mode and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults

        Returns
        -------
        Config: New Config instance with merged settings
        """
        settings = await cls.aiofrom_file(FORMAT.TOML, filepath)
        return Config(cls.merge(defaults, settings), filepath)

    @classmethod
    async def aiofrom_yaml(cls, filepath: str, defaults: dict = None):
        """Load a yaml configuration file in async mode and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults

        Returns
        -------
        Config: New Config instance with merged settings
        """
        settings = await cls.aiofrom_file(FORMAT.YAML, filepath)
        return Config(cls.merge(defaults, settings), filepath)

    @classmethod
    async def aiofrom_json(cls, filepath: str, defaults: dict = None):
        """Load a toml configuration file in asycn mode and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        settings = await cls.aiofrom_file(FORMAT.JSON, filepath)
        return Config(cls.merge(defaults, settings), filepath)

    @classmethod
    def merge(cls, defaults: dict = None, settings: dict = None) -> dict:
        """Merge settings into defaults (replace/expand defaults)

        Arguments
        ---------
        defaults:   dict    The default settings
        settings:   dict    The settings to expand/replace into defaults
        """
        assert not defaults or isinstance(defaults, dict)
        assert not settings or isinstance(settings, dict)

        if not defaults:
            defaults = {}
        if not settings:
            settings = {}

        # Deep merge dictionaries
        result = defaults.copy()
        for key, value in settings.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls.merge(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def to_file(cls, format: FORMAT, filepath: str, data: dict | list):
        """Save data to a file in the specified format

        Arguments
        ---------
        format      FORMAT  A valid config.FORMAT value (TOML, YAML, JSON)
        """
        assert isinstance(format, FORMAT)
        assert isinstance(filepath, str) and len(filepath) > 0
        assert isinstance(data, dict | list)

        try:
            file = Path(filepath)
            parent = Path(file.parent) if not file.exists() else None
            if parent and not parent.exists():
                parent.mkdir(exist_ok=True, parents=True)

            with open(filepath, "w", encoding="utf-8") as f:
                if format == FORMAT.TOML:
                    tomlkit.dump(data, f)
                elif format == FORMAT.YAML:
                    yaml.dump(data, f)
                elif format == FORMAT.JSON:
                    json.dump(data, f)

        except Exception as e:
            logger = logging.getLogger(__class__.__name__)
            logger.error("to_file %s error %s. %s", format.value, filepath, e)

    @classmethod
    async def aioto_file(cls, format: FORMAT, filepath: str, data: dict | list):
        """Save data in async mode to a file in the specified format

        Arguments
        ---------
        format      FORMAT  A valid config.FORMAT value (TOML, YAML, JSON)
        """
        assert isinstance(format, FORMAT)
        assert isinstance(filepath, str) and len(filepath) > 0
        assert isinstance(data, dict | list)

        try:
            file = Path(filepath)
            parent = Path(file.parent) if not file.exists() else None
            if parent and not parent.exists():
                parent.mkdir(exist_ok=True, parents=True)

            async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
                if format == FORMAT.TOML:
                    await f.write(tomlkit.dumps(data))
                elif format == FORMAT.YAML:
                    await f.write(yaml.dump(data))
                elif format == FORMAT.JSON:
                    await f.write(json.dumps(data))

        except Exception as e:
            logger = logging.getLogger(__class__.__name__)
            logger.error("aioto_file %s error %s. %s", format.value, filepath, e)

    def __init__(self, settings: dict = None, filepath: str = None):
        """
        Arguments
        ---------
        settings:   dict    A dictionary of settings
                            Each key in the dictionary must start with lowercase a-z
                            and only ASCII characters are allowed in the name [a-ZA-Z_0-9]


        filepath:   str     Full filepath of the file to store settings in
        """
        if settings is None:
            settings = {}
        assert isinstance(settings, dict)
        assert not filepath or isinstance(filepath, str)
        self._logger = logging.getLogger(__class__.__name__)

        self.filepath = filepath

        for key, value in settings.items():
            self.add(key, value)

    @property
    def sha1(self):
        """Return the sha1 hash value for current config settings"""
        return hashlib.sha1(bytes(str(self.copy()), "utf-8")).hexdigest()

    def _tofile(self, format: FORMAT):
        """Save settings to file in format

        Arguments
        ---------
        format      FORMAT  A valid config.FORMAT value (TOML, YALM, JSON)
        """
        assert isinstance(format, FORMAT)
        if not self.filepath:
            self._logger.error("_tofile Not filepath defined for %s. Aborting", format.value)
            return

        self.to_file(format=format, filepath=self.filepath, data=self.copy())

    async def _aiotofile(self, format: FORMAT):
        """Save settings to file in format

        Arguments
        ---------
        format      FORMAT  A valid config.FORMAT value (TOML, YALM, JSON)
        """
        assert isinstance(format, FORMAT)

        if not self.filepath:
            self._logger.error("_aiotofile Not filepath defined for %s. Aborting", format.value)
            return

        await self.aioto_file(format=format, filepath=self.filepath, data=self.copy())

    def to_toml(self):
        """Save settings to file in toml format"""
        self._tofile(FORMAT.TOML)

    def to_yaml(self):
        """Save settings to file in yaml format"""
        self._tofile(FORMAT.YAML)

    def to_json(self):
        """Save settings to file in json format"""
        self._tofile(FORMAT.JSON)

    async def aioto_toml(self):
        """Save settings in async mode to file in toml format"""
        await self._aiotofile(FORMAT.TOML)

    async def aioto_yaml(self):
        """Save settings in async mode to file in yaml format"""
        await self._aiotofile(FORMAT.YAML)

    async def aioto_json(self):
        """Save settings in async mode to file in json format"""
        await self._aiotofile(FORMAT.JSON)

    def add(self, key: str, value):
        """Add/set a setting

        Arguments
        ---------
        key:    str         A str valid key to name this setting.
                            The key name must star with a lowercase [a-z], and contain ASCII characters only

        value   object      Value of the setting.  The only allowed values are:
                            str, int, float, list, dict, bool, datetime, date, time
        """
        assert isinstance(key, str) and re.match(r"[a-z]\w", key)
        assert isinstance(value, str | int | float | list | dict | bool | datetime | date | time)

        self[key] = value

    def remove(self, key: str):
        """Remove a setting from this configuration

        Arguments
        ---------
        key:    str         The key of the setting to remove
        """
        self.pop(key, None)
