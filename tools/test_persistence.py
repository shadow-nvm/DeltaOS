#!/usr/bin/env python3
"""Tests for the live-persistence helper's pure logic.

    python3 tools/test_persistence.py

The block-device work cannot run without root and a USB stick, so this covers
the parts that decide where a partition goes and what the live system reports.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "config/includes.chroot/usr/bin/deltaos-persistence"


def load_helper():
    loader = importlib.machinery.SourceFileLoader("deltaos_persistence", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("cannot load deltaos-persistence")
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


helper = load_helper()


def table(label: str = "dos", *, sector: int = 512, last: int = 30_000_000,
          parts: list[dict[str, int]] | None = None) -> dict:
    return {"partitiontable": {
        "label": label,
        "sectorsize": sector,
        "lastlba": last,
        "partitions": parts if parts is not None else [
            {"start": 64, "size": 8_000_000, "node": "/dev/sdb1"}],
    }}


class PlanPartitionTests(unittest.TestCase):
    def test_new_partition_follows_the_iso_and_is_aligned(self) -> None:
        plan = helper.plan_partition(table())
        self.assertEqual(plan["start"] % 2048, 0)
        self.assertGreaterEqual(plan["start"], 8_000_064)
        self.assertLessEqual(plan["start"] + plan["sectors"] - 1, 30_000_000)
        self.assertEqual(plan["bytes"], plan["sectors"] * 512)
        self.assertGreaterEqual(plan["bytes"], helper.MIN_BYTES)
        self.assertEqual(plan["table"], "dos")

    def test_gpt_tables_use_the_same_geometry(self) -> None:
        plan = helper.plan_partition(table("gpt"))
        self.assertEqual(plan["table"], "gpt")
        self.assertEqual(plan["start"] % 2048, 0)
        self.assertGreater(plan["bytes"], 1)

    def test_empty_table_starts_after_the_alignment_gap(self) -> None:
        plan = helper.plan_partition(table(parts=[]))
        self.assertEqual(plan["start"], 2048)

    def test_full_disk_is_refused(self) -> None:
        parts = [{"start": 64, "size": 20_000_000}]
        with self.assertRaises(helper.ToolError):
            helper.plan_partition(table(last=20_000_063, parts=parts))

    def test_tiny_free_space_is_refused(self) -> None:
        parts = [{"start": 64, "size": 20_000_000}]
        with self.assertRaises(helper.ToolError):
            helper.plan_partition(table(last=20_400_000, parts=parts))

    def test_four_primary_mbr_partitions_are_refused(self) -> None:
        parts = [{"start": 2048 * (index + 1), "size": 1000} for index in range(4)]
        with self.assertRaises(helper.ToolError):
            helper.plan_partition(table(parts=parts))

    def test_unknown_table_is_refused(self) -> None:
        with self.assertRaises(helper.ToolError):
            helper.plan_partition(table("sun"))

    def test_4k_sectors_still_align_to_one_mebibyte(self) -> None:
        parts = [{"start": 64, "size": 1_000_000, "node": "/dev/sdb1"}]
        plan = helper.plan_partition(table(sector=4096, last=8_000_000, parts=parts))
        self.assertEqual(plan["start"] % 256, 0)
        self.assertEqual(plan["bytes"], plan["sectors"] * 4096)


class PersistenceConfTests(unittest.TestCase):
    def test_conf_has_exactly_one_directive(self) -> None:
        directives = [line.split("#", 1)[0].strip()
                      for line in helper.CONF_TEXT.splitlines()]
        directives = [line for line in directives if line]
        self.assertEqual(directives, ["/ union"])

    def test_conf_is_plain_ascii_and_ends_with_newline(self) -> None:
        self.assertTrue(helper.CONF_TEXT.endswith("\n"))
        self.assertTrue(helper.CONF_TEXT.isascii())


class WriteConfTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.directory = tempfile.TemporaryDirectory(prefix="deltaos-conf-test-")
        self.root = Path(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def directives(self) -> list[str]:
        target = self.root / helper.CONF_NAME
        return [line.split("#", 1)[0].strip()
                for line in target.read_text(encoding="utf-8").splitlines()
                if line.split("#", 1)[0].strip()]

    def test_creates_the_conf_file(self) -> None:
        helper.write_persistence_conf(self.root)
        self.assertEqual(self.directives(), ["/ union"])
        self.assertEqual(helper.CONF_NAME, "persistence.conf")

    def test_keeps_existing_entries(self) -> None:
        target = self.root / helper.CONF_NAME
        target.write_text("/home link,source=home\n", encoding="utf-8")
        helper.write_persistence_conf(self.root)
        self.assertEqual(self.directives(), ["/home link,source=home", "/ union"])

    def test_does_not_duplicate_an_existing_union(self) -> None:
        target = self.root / helper.CONF_NAME
        target.write_text(helper.CONF_TEXT, encoding="utf-8")
        before = target.read_text(encoding="utf-8")
        helper.write_persistence_conf(self.root)
        self.assertEqual(target.read_text(encoding="utf-8"), before)


class BootParameterTests(unittest.TestCase):
    def test_persistence_parameter_is_detected(self) -> None:
        options = helper.cmdline_options(
            "boot=live components quiet splash persistence hostname=deltaos")
        self.assertTrue(helper.persistence_requested(options))

    def test_nopersistence_disables_it(self) -> None:
        options = helper.cmdline_options("boot=live persistence nopersistence")
        self.assertFalse(helper.persistence_requested(options))

    def test_a_label_option_does_not_enable_persistence(self) -> None:
        options = helper.cmdline_options("boot=live persistence-label=private")
        self.assertFalse(helper.persistence_requested(options))

    def test_values_are_kept(self) -> None:
        options = helper.cmdline_options("hostname=deltaos quiet")
        self.assertEqual(options["hostname"], "deltaos")
        self.assertIsNone(options["quiet"])


class StatusLineTests(unittest.TestCase):
    def state(self, **overrides) -> dict:
        base = {"live": True, "requested": True, "disabled": False,
                "volumes": [], "upper": None, "active": False}
        base.update(overrides)
        return base

    def test_installed_system(self) -> None:
        self.assertIn("Not a live session", helper.status_line(self.state(live=False)))

    def test_active_persistence_names_the_volume(self) -> None:
        line = helper.status_line(self.state(
            active=True, upper="/live/persistence/sdb2/overlay"))
        self.assertIn("/live/persistence/sdb2", line)

    def test_volume_from_upper_handles_a_bare_volume(self) -> None:
        self.assertEqual(helper.volume_from_upper("/live/persistence/sdb2"),
                         "/live/persistence/sdb2")
        self.assertEqual(helper.volume_from_upper("/run/overlay"),
                         "/live/persistence")

    def test_disabled_by_nopersistence(self) -> None:
        line = helper.status_line(self.state(disabled=True))
        self.assertIn("nopersistence", line)

    def test_volume_waiting_for_reboot(self) -> None:
        line = helper.status_line(self.state(volumes=[Path("/live/persistence/sdb2")]))
        self.assertIn("reboot", line.lower())

    def test_no_volume(self) -> None:
        self.assertIn("not persistent", helper.status_line(self.state()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
