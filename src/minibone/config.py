import json
import logging
import re
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path

import tomlkit
import yaml


class FORMAT(Enum):
    TOML = "TOML"
    YAML = "YAML"
    JSON = "JSON"


class Config(dict):
    """Class to have settings in memory or in a configuration file"""

    @classmethod
    def from_toml(cls, filepath: str, defaults: dict = None):
        """Load a toml configuration file and return a Config instance

        Arguments
        ---------
        filepath:   str     The filepath of the file to load
        defaults:   dict    A dictionary with default settings.
                            Values from the file will expand/replace defaults
        """
        assert isinstance(filepath, str) and len(filepath) > 0
        logger = logging.getLogger(__class__.__name__)

        settings = {}

        try:
            file = "{path}".format(path=filepath)
            with open(file, "rt", encoding="utf-8") as f:
                settings = tomlkit.load(f)
        except Exception as e:
            logger.error("from_toml error loading %s. %s", filepath, e)

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
        assert isinstance(filepath, str) and len(filepath) > 0
        logger = logging.getLogger(__class__.__name__)

        settings = {}

        try:
            file = "{path}".format(path=filepath)
            with open(file, "rt", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
        except Exception as e:
            logger.error("from_yaml error loading %s. %s", filepath, e)

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
        assert isinstance(filepath, str) and len(filepath) > 0
        logger = logging.getLogger(__class__.__name__)

        settings = {}

        try:
            file = "{path}".format(path=filepath)
            with open(file, "rt", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception as e:
            logger.error("from_json error loading %s. %s", filepath, e)

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

    def to_toml(self):
        """Save settings to file in toml format"""
        if not self.filepath:
            self._logger.error("Not filepath defined for to_toml. Aborting")
            return

        try:
            self._parent_exits()
            with open(self.filepath, "wt", encoding="utf-8") as f:
                tomlkit.dump(self.copy(), f)

        except Exception as e:
            self._logger.error("to_toml error %s. %s", self.filepath, e)

    def to_yaml(self):
        """Save settings to file in yaml format"""
        if not self.filepath:
            self._logger.error("Not filepath defined for to_yaml. Aborting")
            return

        try:
            self._parent_exits()
            with open(self.filepath, "wt", encoding="utf-8") as f:
                yaml.dump(self.copy(), f)

        except Exception as e:
            self._logger.error("to_yaml error %s. %s", self.filepath, e)

    def to_json(self):
        """Save settings to file in json format"""
        if not self.filepath:
            self._logger.error("Not filepath defined for to_json. Aborting")
            return

        try:
            self._parent_exits()
            with open(self.filepath, "wt", encoding="utf-8") as f:
                json.dump(self.copy(), f)

        except Exception as e:
            self._logger.error("to_json error %s. %s", self.filepath, e)

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
