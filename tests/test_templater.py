"""Unit tests for minibone.templater."""

import asyncio
import os
import tempfile
import unittest
from collections.abc import Awaitable
from collections.abc import Callable
from pathlib import Path

from minibone.templater import Templater


class TestTemplater(unittest.TestCase):
    def setUp(self) -> None:
        """Create a temp dir with templates, snippets, and a TOML config."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        self.snippets_path = self.base_path / "snippets"
        self.snippets_path.mkdir()

        self.snippet_content = "<div>Hello ${user}</div>"
        self.html_content = (
            "<!DOCTYPE html><html lang='es-ES'><head><title>${title}</title></head><body>${account}</body>"
        )
        self.toml_content = """
        [page]
        html_file = 'index.html'
        title = 'Templater'

        [account]
        user = 'John'
        """

        (self.snippets_path / "account.html").write_text(self.snippet_content)
        (self.snippets_path / "account.txt").write_text(self.snippet_content)
        (self.base_path / "index.html").write_text(self.html_content)
        (self.base_path / "index.toml").write_text(self.toml_content)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _run_in_base_path(self, coro_factory: Callable[[], Awaitable[str | None]]) -> str | None:
        """Run an async factory with CWD set to the temp base path.

        The TOML path names its ``html_file`` relative to CWD, so tests
        that exercise ``aiofrom_toml`` need to chdir for the relative
        resolution to find the file.
        """
        original_cwd = os.getcwd()
        os.chdir(self.base_path)
        try:
            return asyncio.run(coro_factory())
        finally:
            os.chdir(original_cwd)

    # ------------------------------------------------------------------
    # render (sync substitution)
    # ------------------------------------------------------------------

    def test_render_template(self) -> None:
        templater = Templater()
        result = templater.render(self.snippet_content, {"user": "Max"})
        self.assertEqual(result, "<div>Hello Max</div>")

    def test_render_leaves_unknown_placeholders(self) -> None:
        """safe_substitute keeps unknown placeholders rather than raising."""
        templater = Templater()
        result = templater.render("<div>${missing}</div>", {})
        self.assertEqual(result, "<div>${missing}</div>")

    # ------------------------------------------------------------------
    # aio_file
    # ------------------------------------------------------------------

    def test_async_file_read(self) -> None:
        templater = Templater()
        result = asyncio.run(templater.aio_file(str(self.snippets_path / "account.html")))
        self.assertEqual(result, self.snippet_content)

    def test_async_file_read_missing_returns_none(self) -> None:
        templater = Templater()
        result = asyncio.run(templater.aio_file("nonexistent.html"))
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # aiofrom_file (new entry point)
    # ------------------------------------------------------------------

    def test_aiofrom_file_renders_with_mapping(self) -> None:
        templater = Templater()
        result = asyncio.run(
            templater.aiofrom_file(
                str(self.snippets_path / "account.html"),
                {"user": "Max"},
            )
        )
        self.assertEqual(result, "<div>Hello Max</div>")

    def test_aiofrom_file_missing_returns_none(self) -> None:
        templater = Templater()
        result = asyncio.run(templater.aiofrom_file("nonexistent.html", {"user": "Max"}))
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # aiofrom_toml
    # ------------------------------------------------------------------

    def test_toml_rendering(self) -> None:
        """Snippet is composed into the main template when snippets_path is set."""
        templater = Templater(snippets_path=str(self.snippets_path))
        expected = (
            "<!DOCTYPE html><html lang='es-ES'><head><title>Templater</title></head><body><div>Hello John</div></body>"
        )
        result = self._run_in_base_path(lambda: templater.aiofrom_toml(str(self.base_path / "index.toml")))
        self.assertEqual(result, expected)

    def test_toml_without_snippets_path(self) -> None:
        """Without snippets_path the main template renders, snippets are skipped."""
        templater = Templater()
        expected = "<!DOCTYPE html><html lang='es-ES'><head><title>Templater</title></head><body>${account}</body>"
        result = self._run_in_base_path(lambda: templater.aiofrom_toml(str(self.base_path / "index.toml")))
        self.assertEqual(result, expected)

    def test_toml_missing_file_returns_none(self) -> None:
        templater = Templater()
        result = asyncio.run(templater.aiofrom_toml("nonexistent.toml"))
        self.assertIsNone(result)

    def test_custom_extension(self) -> None:
        """Snippet loading honours the ext parameter."""
        templater = Templater(snippets_path=str(self.snippets_path), ext="txt")
        expected = (
            "<!DOCTYPE html><html lang='es-ES'><head><title>Templater</title></head><body><div>Hello John</div></body>"
        )
        result = self._run_in_base_path(lambda: templater.aiofrom_toml(str(self.base_path / "index.toml")))
        self.assertEqual(result, expected)

    # ------------------------------------------------------------------
    # Snippet cache
    # ------------------------------------------------------------------

    def test_deleted_snippet_does_not_linger(self) -> None:
        """Reloading drops fragments that were removed from disk.

        Regression test: the previous cache only ever added entries, so
        a deleted snippet file would keep showing up until the process
        restarted. cache_life=0 forces a reload on every call.
        """
        templater = Templater(snippets_path=str(self.snippets_path), cache_life=0)

        first = self._run_in_base_path(lambda: templater.aiofrom_toml(str(self.base_path / "index.toml")))
        self.assertIn("<div>Hello John</div>", first)

        (self.snippets_path / "account.html").unlink()

        second = self._run_in_base_path(lambda: templater.aiofrom_toml(str(self.base_path / "index.toml")))
        self.assertNotIn("<div>Hello John</div>", second)
        self.assertIn("${account}", second)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_error_handling(self) -> None:
        templater = Templater()

        with self.assertRaises(AssertionError):
            templater.render(123, {})  # type: ignore[arg-type]

        with self.assertRaises(AssertionError):
            templater.render("template", "not a dict")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
