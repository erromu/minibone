import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from minibone.html_base import HTMLBase


class TestHTMLBase(unittest.TestCase):
    def setUp(self) -> None:
        """Create temp dir and test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        # Create snippets dir
        self.snippets_path = self.base_path / "snippets"
        self.snippets_path.mkdir()

        # Create test files
        self.snippet_content = "<div>Hello ${user}</div>"
        self.html_content = (
            "<!DOCTYPE html><html lang='es-ES'><head><title>${title}</title></head><body>${account}</body>"
        )
        self.toml_content = """
        [page]
        html_file = 'index.html'
        title = 'HTMLBase'

        [account]
        user = 'John'
        """

        # Write test files
        (self.snippets_path / "account.html").write_text(self.snippet_content)
        (self.snippets_path / "account.txt").write_text(self.snippet_content)
        (self.base_path / "index.html").write_text(self.html_content)
        (self.base_path / "index.toml").write_text(self.toml_content)

    def tearDown(self) -> None:
        """Clean up temp dir."""
        self.temp_dir.cleanup()

    def test_render_template(self) -> None:
        """Test basic template rendering."""
        htmlbase = HTMLBase()
        mapping = {"user": "Max"}
        result = htmlbase.render(self.snippet_content, mapping)
        self.assertEqual(result, "<div>Hello Max</div>")

    def test_async_file_read(self) -> None:
        """Test async file reading."""
        htmlbase = HTMLBase(snippets_path=str(self.snippets_path))
        result = asyncio.run(htmlbase.aio_file(str(self.snippets_path / "account.html")))
        self.assertEqual(result, self.snippet_content)

    def test_toml_rendering(self) -> None:
        """Test rendering from TOML config."""
        htmlbase = HTMLBase(snippets_path=str(self.snippets_path))
        # Set the current working directory to the base path so HTML files can be found

        original_cwd = os.getcwd()
        os.chdir(self.base_path)
        try:
            expected = "<!DOCTYPE html><html lang='es-ES'><head><title>HTMLBase</title></head><body><div>Hello John</div></body>"
            result = asyncio.run(htmlbase.aiofrom_toml(str(self.base_path / "index.toml")))
            self.assertEqual(result, expected)
        finally:
            os.chdir(original_cwd)

    def test_custom_extension(self) -> None:
        """Test loading snippets with custom extension."""
        htmlbase = HTMLBase(snippets_path=str(self.snippets_path), ext="txt")
        # Set the current working directory to the base path so HTML files can be found
        original_cwd = os.getcwd()
        os.chdir(self.base_path)
        try:
            expected = "<!DOCTYPE html><html lang='es-ES'><head><title>HTMLBase</title></head><body><div>Hello John</div></body>"
            result = asyncio.run(htmlbase.aiofrom_toml(str(self.base_path / "index.toml")))
            self.assertEqual(result, expected)
        finally:
            os.chdir(original_cwd)

    def test_error_handling(self) -> None:
        """Test error cases."""
        htmlbase = HTMLBase()

        # Test invalid template
        with self.assertRaises(AssertionError):
            htmlbase.render(123, {})  # type: ignore

        # Test invalid mapping
        with self.assertRaises(AssertionError):
            htmlbase.render("template", "not a dict")  # type: ignore

        # Test missing file
        result = asyncio.run(htmlbase.aio_file("nonexistent.html"))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
