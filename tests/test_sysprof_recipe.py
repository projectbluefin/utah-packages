"""Keep the host profiler installable without the optional energy helper."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "packages/sysprof/sysprof.spec").read_text()


def test_kernel_tools_is_optional():
    assert not re.search(r"^Requires:.*\bkernel-tools\b", SPEC, re.MULTILINE)
    assert re.search(r"^Recommends:\s+kernel-tools$", SPEC, re.MULTILINE)
    assert "Release:        1.2%{?dist}" in SPEC


def test_host_daemon_and_policy_are_preserved_without_the_gui():
    assert "-Dgtk=false" in SPEC
    assert "-Dsysprofd=bundled" in SPEC
    assert "-Dtools=true" in SPEC
    assert "-Dtests=true" in SPEC
    assert "%check\n%meson_test" in SPEC
    cli_files = SPEC.split("%files cli", 1)[1].split("%files -n", 1)[0]
    for payload in (
        "%{_bindir}/sysprof-cli",
        "%{_libexecdir}/sysprofd",
        "%{_unitdir}/sysprof3.service",
        "%{_datadir}/dbus-1/system.d/org.gnome.Sysprof3.conf",
        "%{_datadir}/dbus-1/system-services/org.gnome.Sysprof3.service",
        "%{_datadir}/polkit-1/actions/org.gnome.sysprof3.policy",
    ):
        assert payload in cli_files
    assert "%{_bindir}/sysprof\n" not in SPEC
    assert "org.gnome.Sysprof.desktop" not in SPEC


def test_source_matches_the_imported_recipe():
    locks = json.loads((ROOT / "config/upstream-sources.json").read_text())["packages"]
    lock = next(entry for entry in locks if entry["name"] == "sysprof")
    assert lock["url"] == "https://download.gnome.org/sources/sysprof/51/sysprof-51.0.tar.xz"
    assert (ROOT / "packages/sysprof/sources").read_text().strip() == (
        f'SHA512 ({lock["filename"]}) = {lock["sha512"]}'
    )
