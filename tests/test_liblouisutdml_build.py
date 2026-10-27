"""Guard the braille converter's documentation-only ICU build-root opt-in."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_icu_opt_in_keeps_documentation_and_tests():
    entries = json.loads((ROOT / "config/upstream-sources.json").read_text())["packages"]
    entry = next(item for item in entries if item["name"] == "liblouisutdml")
    spec = (ROOT / "packages/liblouisutdml/liblouisutdml.spec").read_text()
    build_requires = re.findall(r"^BuildRequires:\s*(.*)$", spec, re.MULTILINE)

    assert entry["buildroot_icu77"] is True
    assert "texinfo-tex" in build_requires
    assert not any(re.search(r"\b(?:libicu-devel|icu-devel|pkgconfig\(icu-)", dep)
                   for dep in build_requires)
    assert "make -C doc liblouisutdml.pdf" in spec
    assert "%doc doc/%{name}.{html,txt,pdf}" in spec
    assert re.search(r"^%check\s*\nmake check\s*$", spec, re.MULTILINE)
