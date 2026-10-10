"""Template rendering with caller-provided or TOML-provided variables.

Provides a single class, ``Templater``, that reads a template file and
substitutes ``${name}`` placeholders. Two entry points:

- ``aiofrom_file(filepath, mapping)`` — variables come from the caller.
  Use for emails, notifications, and anything whose values are runtime
  data.
- ``aiofrom_toml(filepath)`` — variables come from a TOML file. Use for
  static pages authored alongside the template. Supports optional
  snippet composition.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from string import Template

import aiofiles

from minibone.config import Config
from minibone.config import ConfigError


class Templater:
    """Render text templates with ``${placeholder}`` substitution.

    Substitution uses ``string.Template``. Unknown placeholders are left
    in place — ``safe_substitute`` does not raise on missing keys. This
    is intentional: a partially populated mapping still produces output,
    which is useful while iterating on a template and safer for automated
    sends (a broken variable does not abort a delivery).

    Snippet composition is optional. Pass ``snippets_path`` to load
    fragments from a directory; leave it as ``None`` to skip snippet
    loading entirely. The ``aiofrom_file`` path never touches snippets.

    Both rendering methods return ``None`` on any failure — missing file,
    unreadable file, or invalid TOML — and log the reason. Callers get a
    single "did we render or not" signal without having to catch config
    layer exceptions.

    Basic usage::

        templater = Templater()
        rendered = await templater.aiofrom_file("email.html", {"user": "rock"})
    """

    def __init__(
        self,
        snippets_path: str | None = None,
        ext: str = "html",
        cache_life: int = 300,
    ):
        """
        Args:
            snippets_path: Directory containing template fragments. When
                ``None``, snippet loading is skipped and ``aiofrom_toml``
                renders the main template without composition. Paths are
                used verbatim; resolve them in the caller, not here.
            ext: Fragment file extension (default: ``html``).
            cache_life: Seconds before fragments are reloaded from disk.
        """
        assert snippets_path is None or isinstance(snippets_path, str)
        assert isinstance(ext, str)
        assert isinstance(cache_life, int)

        self._logger = logging.getLogger(self.__class__.__name__)

        self._snippets_path = snippets_path
        self._ext = ext
        self._cache_life = cache_life
        # monotonic is used instead of time() so NTP adjustments cannot
        # skip or duplicate a reload.
        self._next_reload: float = 0.0

        self._snippets: dict[str, str] = {}

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    async def _aiofile(self, file: str) -> str | None:
        """Read a file asynchronously. Returns None and logs on failure."""
        assert isinstance(file, str)
        try:
            async with aiofiles.open(file, encoding="utf-8") as f:
                return await f.read()
        except Exception as e:
            self._logger.error("_aiofile %s: %s", file, e)
            return None

    async def aio_file(self, file: str) -> str | None:
        """Public alias for reading a file asynchronously."""
        return await self._aiofile(file)

    # ------------------------------------------------------------------
    # Snippets
    # ------------------------------------------------------------------

    async def _iosnippets(self) -> None:
        """Load snippet files from the snippets directory.

        No-op when ``snippets_path`` was not configured. Reloads only
        when the cache TTL has elapsed. The reload builds a fresh dict
        and swaps it in, so fragments deleted from disk do not linger.
        """
        if self._snippets_path is None:
            return

        now = time.monotonic()
        if self._next_reload > now:
            return
        self._next_reload = now + self._cache_life

        path = Path(self._snippets_path)
        if not path.is_dir():
            return

        fresh: dict[str, str] = {}
        for file in path.glob(f"*.{self._ext}"):
            content = await self._aiofile(str(file))
            if content is not None:
                fresh[file.stem] = content

        self._snippets = fresh

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, template: str, mapping: dict) -> str:
        """Substitute ``${name}`` placeholders in ``template``.

        Unknown placeholders are left as-is (``safe_substitute``).

        Example:
            >>> t = Templater()
            >>> t.render("<div>${name}</div>", {"name": "John"})
            '<div>John</div>'
        """
        assert isinstance(template, str)
        assert isinstance(mapping, dict)
        return Template(template).safe_substitute(mapping)

    async def aiofrom_file(self, filepath: str, mapping: dict) -> str | None:
        """Read a template file and render it with caller-provided variables.

        No TOML file, no snippet lookup. Suitable for emails,
        notifications, and any template whose values are runtime data.

        Args:
            filepath: Path to the template file.
            mapping: Values for ``${name}`` substitution.

        Returns:
            Rendered string, or None if the file could not be read.
        """
        assert isinstance(filepath, str)
        assert isinstance(mapping, dict)

        content = await self._aiofile(filepath)
        if content is None:
            return None
        return self.render(content, mapping)

    async def aiofrom_toml(self, filepath: str) -> str | None:
        """Render a template driven by a TOML configuration file.

        Minimum TOML layout::

            [page]
            html_file = 'index.html'
            title = 'My site'

            [account]
            user = 'John'

        - ``[page] html_file`` names the template file to render.
        - Every other key in ``[page]`` becomes a substitution variable
          in the main template.
        - Each additional block corresponds to a snippet file of the same
          name in the snippets directory. The snippet is rendered with
          its block's values, and its output is substituted into the main
          template under that block name. Skipped entirely when
          ``snippets_path`` was not configured.

        Example. Given ``snippets/account.html``::

            <div>Hello ${user}</div>

        and ``index.html``::

            <title>${title}</title>
            <body>${account}</body>

        and ``index.toml`` as above, calling
        ``await templater.aiofrom_toml("index.toml")`` returns the fully
        composed HTML.

        Returns:
            Rendered string, or None on missing config file, invalid
            config, missing ``[page]`` block, missing ``html_file``, or
            unreadable template file.
        """
        assert isinstance(filepath, str)

        try:
            settings = await Config.aiofrom_toml(filepath=filepath)
        except ConfigError as e:
            # Covers ConfigFileNotFoundError, ConfigParseError, and other
            # config-layer failures. Render path signals "couldn't render"
            # with None, not with an exception — the caller decides what
            # to do next.
            self._logger.error("aiofrom_toml %s: %s", filepath, e)
            return None

        if not settings or not settings.get("page"):
            self._logger.error("from_toml invalid file %s or no [page] block", filepath)
            return None

        # Copy the page block so substitution does not mutate the Config.
        cfg_page = dict(settings["page"])
        if not cfg_page.get("html_file"):
            self._logger.error("from_toml [page] block missing html_file: %s", filepath)
            return None

        await self._iosnippets()
        for name, snippet in self._snippets.items():
            cfg_page[name] = self.render(snippet, settings.get(name, {}))

        content = await self.aio_file(cfg_page["html_file"])
        if content is None:
            return None
        return self.render(content, cfg_page)
