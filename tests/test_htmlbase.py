import asyncio
import unittest
from pathlib import Path

from minibone.html_base import HTMLBase


class TestHTMLBase(unittest.TestCase):
    def test_htmlbase(self):
        pathsnippets = Path("./snippets")
        pathsnippets.mkdir(parents=True, exist_ok=True)

        mapping = {"user": "Max"}
        snippet = "<div>Hello ${user}</div>"
        html = "<!DOCTYPE html><html lang='es-ES'><head><title>${title}</title></head><body>${account}</body>"
        toml = """
        [page]
        html_file = 'index.html'
        title = 'HTMLBase'

        [account]
        user = 'John'        
        """

        with open("./snippets/account.html", "tw") as f:
            f.write(snippet)

        with open("./snippets/account.txt", "tw") as f:
            f.write(snippet)

        with open("./index.html", "tw") as f:
            f.write(html)

        with open("./index.toml", "tw") as f:
            f.write(toml)

        htmlbase = HTMLBase(snippets_path="./snippets")
        self.assertEqual(htmlbase.render(snippet, mapping), "<div>Hello Max</div>")
        self.assertEqual(asyncio.run(htmlbase.aio_file("./snippets/account.html")), "<div>Hello ${user}</div>")
        self.assertEqual(
            asyncio.run(htmlbase.aiofrom_toml("index.toml")),
            "<!DOCTYPE html><html lang='es-ES'><head><title>HTMLBase</title></head><body><div>Hello John</div></body>",
        )

        htmlbase = HTMLBase(snippets_path="./snippets", ext="txt")
        self.assertEqual(
            asyncio.run(htmlbase.aiofrom_toml("index.toml")),
            "<!DOCTYPE html><html lang='es-ES'><head><title>HTMLBase</title></head><body><div>Hello John</div></body>",
        )

        files = ["./index.toml", "./index.html", "./snippets/account.html", "./snippets/account.txt"]
        for file in files:
            p = Path(file)
            p.unlink(missing_ok=True)
        pathsnippets.rmdir()


if __name__ == "__main__":
    unittest.main()
