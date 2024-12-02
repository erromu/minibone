import glob
import logging
import time
from pathlib import Path
from string import Template

import aiofiles

from minibone.config import Config


class HTMLBase:
    """Class to render html using snippets and toml configuration file in async mode"""

    def __init__(self, snippets_path: str = "./html/pages/snippets", ext: str = "html", cache_life: int = 300):
        """
        Arguments
        ---------
        snippets_path:  str     The path where snippets are stored
        ext:            str     The extensio of the snippets files
        cache_life:     int     Number of seconds to have html snippets in memory before reloading them
        """
        assert isinstance(snippets_path, str)
        assert isinstance(ext, str)
        assert isinstance(cache_life, int)
        self._logger = logging.getLogger(__class__.__name__)

        self._snippets_path = snippets_path
        self._ext = ext
        self._cache_life = cache_life
        self._epoch = 0

        self._snippets = {}

    async def _aiofile(self, file: str) -> str:
        """Load content from a file using encoding utf-8 in async mode and return it

        Arguments
        ---------
        file        str     The file to load from disk
        """
        assert isinstance(file, str)
        try:
            async with aiofiles.open(
                file,
                "rt",
                encoding="utf-8",
            ) as f:
                return await f.read()

        except Exception as e:
            self._logger.error("_aiofile %s", e)
            return None

    async def _iosnippets(self) -> str:
        """Load all HTML snippets from files in async mode only when cached is old."""

        epoch = time.time()
        if self._epoch > epoch:
            return

        self._epoch = epoch + self._cache_life

        p = Path(self._snippets_path)
        if p.exists() and p.is_dir():
            files = glob.glob(glob.escape(self._snippets_path) + f"/*.{self._ext}")
            for file in files:
                name = file.split("/")[-1].split(".")[0]
                content = await self._aiofile(file)
                if content:
                    self._snippets[name] = content

    async def aio_file(self, file: str) -> str:
        """Return the file's content using encoding utf-8 in async mode.

        Arguments
        ---------
        file        str     The file to load from disk
        """
        return await self._aiofile(file)

    def render(self, template: str, mapping: dict) -> str:
        """Return a str render for template using mapping keys and values

        Arguments
        ---------
        template    str     The template in string format
        mapping     dict    A dictionary of key an values

        Sample
        ------

        h = HTMLBase()
        template = "<div>Hello ${user}</div>"
        render = h.render(template, {"user": "John"})

        # will return
        # <div>Hello John</div>
        #
        # Further reading in python string.Template module
        """
        assert isinstance(template, str)
        assert isinstance(mapping, dict)

        return Template(template).safe_substitute(mapping)

    async def aiofrom_toml(self, filepath: str) -> str:
        """Load and toml file, extract configuration values then render a html file accordingly in async mode

        Arguments
        ---------
        filepath:       str         The toml's filepath having the html render configuration

        Notes
        -----
        - Minimum toml configuration has a [page] block with 'html_file' settign
        - Add html snippets (.html) into the snippets path
        - In the toml file add additional blocks for each snippet. Named blocks as each snippet file's name
        - Add key/values to be replaced in the snippets (see render method)

        Example
        -------

        1. Into snippets path there is an account.html snippet having next markup

        <div>Hello ${user}</div>


        2. There a file named index.html having:

        <!DOCTYPE html>
        <html lang='es-ES'>
        <head>
            <title>${title}</title>
        </head>
        <body>
            ${account}
        </body>

        3. There is a file named index.toml having next minimal configuration

        [page]
        #
        html_file = 'index.html'
        #
        title = 'Super cool website'

        [account]
        #
        user = John

        4. use next code to get the html rendered

        content = aiofrom_toml("index.toml")
        """
        assert isinstance(filepath, str)

        settings = await Config.aiofrom_toml(filepath=filepath)
        if not settings or not settings.get("page", None):
            self._logger.error("from_toml invalid file %s or not [page] block found", filepath)
            return

        cfg_page = settings["page"]
        if not cfg_page["html_file"]:
            self._logger.error("from_toml file has not html_file setting in [page] block %s", filepath)
            return

        await self._iosnippets()
        for key, snippet in self._snippets.items():
            cfg_page[key] = self.render(snippet, settings.get(key, {}))

        content = await self.aio_file(cfg_page["html_file"])
        content = self.render(content, cfg_page)

        return content
