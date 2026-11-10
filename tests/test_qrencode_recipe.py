"""Preserve the QR library output and its checksum-locked source fallback."""

import json
from pathlib import Path

from tools.factory_build_backlog import _subpackage_names

ROOT = Path(__file__).resolve().parents[1]


def test_qrencode_provides_the_audited_library():
    assert "qrencode-libs" in _subpackage_names(ROOT)
    spec = (ROOT / "packages/qrencode/qrencode.spec").read_text()
    assert "%{_libdir}/libqrencode.so.%{so_ver}*" in spec
    # The hosted RPM build must run the library tests, not just compile it.
    assert "%check\npushd ./tests\nsh test_all.sh\npopd" in spec


def test_qrencode_source_fallback_preserves_the_recipe_digest():
    locks = json.loads((ROOT / "config/upstream-sources.json").read_text())["packages"]
    lock = next(entry for entry in locks if entry["name"] == "qrencode")
    source = (ROOT / "packages/qrencode/sources").read_text().strip()
    assert source == f'SHA512 ({lock["filename"]}) = {lock["sha512"]}'
    # An unavailable upstream must not promote Fedora into the primary source.
    assert lock["url"] == f'https://fukuchi.org/works/qrencode/{lock["filename"]}'
    assert lock["fallback_urls"] == [
        "https://src.fedoraproject.org/repo/pkgs/rpms/qrencode/"
        f'{lock["filename"]}/sha512/{lock["sha512"]}/{lock["filename"]}'
    ]
