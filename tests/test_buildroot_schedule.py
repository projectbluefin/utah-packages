#!/usr/bin/env python3
"""The build-root refresh is batched with the Sunday full rebuild (#1207).

A build-root move changes every package's cache key. If the refresh lands on
its own, the week pays one cold rebuild for the move and another for the
weekly full run. The decided rule is to open the refresh PR just before the
Sunday full run so one cold rebuild covers both.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def crons(name: str) -> list[str]:
    text = (WORKFLOWS / name).read_text()
    return re.findall(r"^\s*- cron: '([^']+)'", text, re.M)


def parse(cron: str) -> tuple[int, int, int] | None:
    fields = cron.split()
    minute, hour, day_of_week = int(fields[0]), int(fields[1]), fields[4]
    if not day_of_week.isdigit():
        return None
    return int(day_of_week), hour, minute


class BuildrootScheduleTests(unittest.TestCase):
    def test_refresh_is_opened_the_day_before_the_weekly_full_run(self) -> None:
        refresh = crons("refresh-buildroot.yml")
        rebuild = crons("rebuild-rpms.yml")
        self.assertEqual(len(refresh), 1, "refresh should have one weekly schedule")
        weekly = [c for c in rebuild if parse(c) and parse(c)[0] == 0]
        self.assertEqual(len(weekly), 1, "rebuild-rpms should have one Sunday cron")

        refresh_day, _, _ = parse(refresh[0])
        self.assertEqual(refresh_day, (parse(weekly[0])[0] - 1) % 7)

    def test_the_refresh_pr_tells_the_reader_when_to_merge(self) -> None:
        body = (WORKFLOWS / "refresh-buildroot.yml").read_text()
        self.assertIn("Sunday", body)
        self.assertIn("01:23", body)

    def test_the_timing_rule_is_written_down(self) -> None:
        architecture = (ROOT / "docs" / "architecture.md").read_text()
        self.assertIn("just before the Sunday full run", architecture)
