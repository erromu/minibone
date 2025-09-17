import glob
import logging
import time
from pathlib import Path
from string import Template

import aiofiles

from minibone.config import Config


class HTMLBase:
    """Class to render HTML templates using snippets and TOML configuration (async capable).

    Features:
    ---------
    - Async file operations
    - Template rendering with string.Template
    - Snippet caching
    - TOML configuration support

    Basic Usage:
    -----------
    from minibone.html_base import HTMLBase

    html = HTMLBase(snippets_path="/path/to/snippets")
    rendered = await html.aiofrom_toml("config.toml")
    """

    def __init__(self, snippets_path: str = "./html/pages/snippets", ext: str = "html", cache_life: int = 300):
        """
        Initialize HTML renderer.

        Args:
            snippets_path: Path to directory containing HTML snippet files
            ext: File extension for snippets (default: "html")
            cache_life: Cache lifetime in seconds (default: 300)
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

    async def _aiofile(self, file: str) -> str | None:
        """Asynchronously read file contents.

        Args:
            file: Path to file to read

        Returns:
            File contents as string or None if error occurs
        """
        assert isinstance(file, str)
        try:
            async with aiofiles.open(
                file,
                encoding="utf-8",
            ) as f:
                return await f.read()

        except Exception as e:
            self._logger.error("_aiofile %s", e)
            return None

    async def _iosnippets(self) -> None:
        """Load all HTML snippets from files (async, cached).

        Only reloads snippets if cache has expired.
        """

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

    async def aio_file(self, file: str) -> str | None:
        """Asynchronously read file contents (public interface).

        Args:
            file: Path to file to read

        Returns:
            File contents as string or None if error occurs
        """
        return await self._aiofile(file)

    def render(self, template: str, mapping: dict) -> str:
        """Render template string with variable substitution.

        Args:
            template: Template string with ${placeholders}
            mapping: Dictionary of placeholder replacements

        Returns:
            Rendered string with placeholders replaced

        Raises:
            ValueError: If template or mapping are invalid

        Example:
            >>> html = HTMLBase()
            >>> html.render("<div>${name}</div>", {"name": "John"})
            '<div>John</div>'
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
        - Minimum toml configuration has a [page] block with 'html_file' setting
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
