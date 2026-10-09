#!/usr/bin/env python3
"""systemd scriptlet macros must match their section.

Inherited verbatim from Fedora, pcsc-lite-ccid once used
%systemd_postun_with_restart inside %post (a postun macro with uninstall
restart semantics) and misspelled the unit in %preun
(projectbluefin/utah-packages#365, #367). The %post section takes
%systemd_post; %postun takes %systemd_postun_with_restart. This test pins
the corrected pairing so a re-import cannot silently bring the bug back.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packages" / "pcsc-lite-ccid" / "pcsc-lite-ccid.spec"


def section_body(text: str, name: str) -> str:
    """RPM scriptlet section body (up to the next section header).

    Macro invocations (%systemd_*, %meson_*, ...) are not section
    headers; only a bare %name line starts a new section.
    """
    match = re.search(rf"^%{name}\s*$", text, re.MULTILINE)
    if not match:
        raise AssertionError(f"no %{name} section in {SPEC}")
    tail = text[match.end():]
    nxt = re.search(r"^%(?!systemd_)[a-z]+\s*$", tail, re.MULTILINE)
    return tail[:nxt.start() if nxt else None]


class ScriptletMacroTests(unittest.TestCase):
    def test_post_uses_post_macro(self):
        body = section_body(SPEC.read_text(), "post")
        self.assertRegex(body, r"%systemd_post\s+pcscd\.service")
        self.assertNotRegex(body, r"%systemd_postun")

    def test_preun_names_the_unit(self):
        body = section_body(SPEC.read_text(), "preun")
        self.assertRegex(body, r"%systemd_preun\s+pcscd\.service")
        self.assertNotRegex(body, r"%systemd_preun\s+pcscsd\.service")

    def test_postun_uses_postun_macro(self):
        body = section_body(SPEC.read_text(), "postun")
        self.assertRegex(body, r"%systemd_postun_with_restart\s+pcscd\.service")


if __name__ == "__main__":
    unittest.main()
