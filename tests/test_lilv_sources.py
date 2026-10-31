"""Keep the audio plugin discovery dependency family registered together."""

from pathlib import Path

from tools.package_inventory import source_locks


ROOT = Path(__file__).resolve().parent.parent


def test_lilv_factory_dependencies_are_registered():
    locks = source_locks(ROOT)
    dependencies = {
        "sord": ("serd", "zix"),
        "sratom": ("serd", "sord", "lv2"),
        "lilv": ("serd", "sord", "sratom", "lv2", "zix"),
    }
    for consumer, providers in dependencies.items():
        for provider in providers:
            assert provider in locks
            spec = (ROOT / "packages" / consumer / f"{consumer}.spec").read_text()
            assert f"pkgconfig({provider}" in spec
        # The graph solver orders this acyclic family from BuildRequires.
        assert "stage" not in locks[consumer]


def test_lilv_release_locks_match_imported_recipes():
    locks = source_locks(ROOT)
    for name in ("lilv", "lv2", "sord", "sratom"):
        lock = locks[name]
        spec = (ROOT / "packages" / name / f"{name}.spec").read_text()
        version_line = next(line for line in spec.splitlines() if line.startswith("Version:"))
        assert version_line.split()[1] == lock["version"]
        assert lock["filename"] == f'{name}-{lock["version"]}.tar.xz'
        assert lock["url"] == (
            f'https://lv2plug.in/spec/{lock["filename"]}'
            if name == "lv2"
            else f'https://download.drobilla.net/{lock["filename"]}'
        )
