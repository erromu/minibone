import json
import logging
import re
from datetime import date, datetime, time
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
    def from_file(cls, format: FORMAT, filepath: str, defaults: dict = None):
        """Load a file configuration and return a Config instance

        Arguments
        ---------
        format      FORMAT  A valid config.FORMAT value (TOML, YALM, JSON)
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        assert isinstance(format, FORMAT)
        assert isinstance(filepath, str) and len(filepath) > 0
        assert not defaults or isinstance(defaults, dict)

        logger = logging.getLogger(__class__.__name__)

        settings = {}

        try:
            file = "{path}".format(path=filepath)
            with open(file, "rt", encoding="utf-8") as f:
                if format == FORMAT.TOML:
                    settings = tomlkit.load(f)
                elif format == FORMAT.YAML:
                    settings = yaml.safe_load(f)
                elif format == FORMAT.JSON:
                    settings = json.load(f)

        except Exception as e:
            logger.error("from_file %s error loading %s. %s", format.value, filepath, e)

        return Config(cls.merge(defaults, settings), filepath)

    @classmethod
    async def aiofrom_file(cls, format: FORMAT, filepath: str, defaults: dict = None):
        """Load a file configuration in async mode and return a Config instance

        Arguments
        ---------
        format      FORMAT  A valid config.FORMAT value (TOML, YALM, JSON)
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        assert isinstance(format, FORMAT)
        assert isinstance(filepath, str) and len(filepath) > 0
        assert not defaults or isinstance(defaults, dict)

        logger = logging.getLogger(__class__.__name__)

        settings = {}

        try:
            file = "{path}".format(path=filepath)
            async with aiofiles.open(file, "rt", encoding="utf-8") as f:
                if format == FORMAT.TOML:
                    settings = tomlkit.loads(await f.read())
                elif format == FORMAT.YAML:
                    settings = yaml.safe_load(await f.read())
                elif format == FORMAT.JSON:
                    settings = json.loads(await f.read())

        except Exception as e:
            logger.error("aiofrom_file %s error loading %s. %s", format.value, filepath, e)

        return Config(cls.merge(defaults, settings), filepath)

    @classmethod
    def from_toml(cls, filepath: str, defaults: dict = None):
        """Load a toml configuration file and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        return cls.from_file(FORMAT.TOML, filepath, defaults)

    @classmethod
    def from_yaml(cls, filepath: str, defaults: dict = None):
        """Load a yaml configuration file and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        return cls.from_file(FORMAT.YAML, filepath, defaults)

    @classmethod
    def from_json(cls, filepath: str, defaults: dict = None):
        """Load a json configuration file and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        return cls.from_file(FORMAT.JSON, filepath, defaults)

    @classmethod
    async def aiofrom_toml(cls, filepath: str, defaults: dict = None):
        """Load a toml configuration file in asycn mode and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        return await cls.aiofrom_file(FORMAT.TOML, filepath, defaults)

    @classmethod
    async def aiofrom_yaml(cls, filepath: str, defaults: dict = None):
        """Load a toml configuration file in asycn mode and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        return await cls.aiofrom_file(FORMAT.YAML, filepath, defaults)

    @classmethod
    async def aiofrom_json(cls, filepath: str, defaults: dict = None):
        """Load a toml configuration file in asycn mode and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        return await cls.aiofrom_file(FORMAT.JSON, filepath, defaults)

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

        # TODO return a merge including second and nth sub-levels on the dict
        return defaults | settings

    def __init__(self, settings: dict = {}, filepath: str = None):
        """
        Arguments
        ---------
        settings:   dict    A dictionary of settings
                            Each key in the dictionary must start with lowercase a-z
                            and only ASCII characters are allowed in the name [a-ZA-Z_0-9]


        filepath:   str     Full filepath of the file to store settings in
        """
        assert isinstance(settings, dict)
        assert not filepath or isinstance(filepath, str)
        self._logger = logging.getLogger(__class__.__name__)

        self.filepath = filepath

        for key, value in settings.items():
            self.add(key, value)

    def _parent_exits(self):
        """create the parent directory if it does not exits"""
        file = Path(self.filepath)
        parent = Path(file.parent) if not file.exists() else None
        if parent and not parent.exists():
            parent.mkdir(exist_ok=True, parents=True)

    def _tofile(self, format: FORMAT):
        """Save settings to file in format
        Arguments:
        ----------
        format      FORMAT  A valid config.FORMAT value (TOML, YALM, JSON)
        """
        assert isinstance(format, FORMAT)

        if not self.filepath:
            self._logger.error("_tofile Not filepath defined for %s. Aborting", format.value)
            return

        try:
            self._parent_exits()
            with open(self.filepath, "wt", encoding="utf-8") as f:
                if format == FORMAT.TOML:
                    tomlkit.dump(self.copy(), f)
                elif format == FORMAT.YAML:
                    yaml.dump(self.copy(), f)
                elif format == FORMAT.JSON:
                    json.dump(self.copy(), f)

        except Exception as e:
            self._logger.error("_tofile %s error %s. %s", format.value, self.filepath, e)

    async def _aiotofile(self, format: FORMAT):
        """Save settings to file in format
        Arguments:
        ----------
        format      FORMAT  A valid config.FORMAT value (TOML, YALM, JSON)
        """
        assert isinstance(format, FORMAT)

        if not self.filepath:
            self._logger.error("_aiotofile Not filepath defined for %s. Aborting", format.value)
            return

        try:
            self._parent_exits()

            async with aiofiles.open(self.filepath, "wt", encoding="utf-8") as f:
                if format == FORMAT.TOML:
                    await f.write(tomlkit.dumps(self.copy()))
                elif format == FORMAT.YAML:
                    await f.write(yaml.dump(self.copy()))
                elif format == FORMAT.JSON:
                    await f.write(json.dumps(self.copy()))

        except Exception as e:
            self._logger.error("_aiotofile %s error %s. %s", format.value, self.filepath, e)

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
        assert isinstance(key, str) and re.match("[a-z]\w", key)
        assert isinstance(value, (str, int, float, list, dict, bool, datetime, date, time))

        self[key] = value

    def remove(self, key: str):
        """Remove a setting from this configuration
        Arguments
        ---------
        key:    str         The key of the setting to remove
        """
        self.pop(key, None)
