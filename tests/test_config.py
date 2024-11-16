import asyncio
import unittest
from pathlib import Path

from src.minibone.config import Config


class TestConfig(unittest.TestCase):
    def test_settings(self):
        settings = {"setting1": "value1", "setting2": 2, "setting3": True}
        cfg = Config(settings=settings, filepath=None)

        self.assertEqual(cfg.get("setting1", None), "value1")
        self.assertEqual(cfg.get("setting10", None), None)
        self.assertEqual(cfg.get("setting2", None), 2)
        self.assertEqual(cfg.get("setting3", None), True)

        cfg.remove("setting1")
        cfg.add("setting3", False)

        self.assertEqual(cfg.get("setting1", None), None)
        self.assertEqual(cfg.get("setting3", None), False)

        self.assertEqual(cfg.merge({}, {}), {})
        self.assertEqual(cfg.merge(defaults={"x": 1}), {"x": 1})
        self.assertEqual(cfg.merge(settings={"x": 1}), {"x": 1})
        self.assertEqual(cfg.merge(defaults={"x": 1}, settings={"y": 2}), {"x": 1, "y": 2})
        self.assertEqual(cfg.merge(defaults={"z": 1}, settings={"z": 4}), {"z": 4})

        cfgs = []
        files = ["config.toml", "config.yaml", "config.json", "aconfig.toml", "aconfig.yaml", "aconfig.json"]
        for file in files:
            cfgs.append(Config(settings=cfg, filepath=file))

        cfgs[0].to_toml()
        cfgs[1].to_yaml()
        cfgs[2].to_json()

        self.assertEqual(cfgs[0].from_toml(cfgs[0].filepath), cfg)
        self.assertEqual(cfgs[1].from_yaml(cfgs[1].filepath), cfg)
        self.assertEqual(cfgs[2].from_json(cfgs[2].filepath), cfg)

        asyncio.run(cfgs[3].aioto_toml())
        asyncio.run(cfgs[4].aioto_yaml())
        asyncio.run(cfgs[5].aioto_json())

        self.assertEqual(asyncio.run(cfgs[3].aiofrom_toml(cfgs[3].filepath)), cfg)
        self.assertEqual(asyncio.run(cfgs[4].aiofrom_yaml(cfgs[4].filepath)), cfg)
        self.assertEqual(asyncio.run(cfgs[5].aiofrom_json(cfgs[5].filepath)), cfg)

        for file in files:
            p = Path(file)
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
