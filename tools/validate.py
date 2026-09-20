#!/usr/bin/env python3
"""Validate package-factory configuration."""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import inventory


def check_provenance(path: Path, data: dict) -> None:
    required = {"package", "branch", "remote", "commit", "tree", "imported_at"}
    if set(data) != required:
        raise SystemExit(f"invalid upstream provenance: {path}")
    if data["branch"] not in ("rawhide", "upstream"):
        raise SystemExit(f"only rawhide or upstream imports are supported: {path}")
    if data["branch"] == "upstream":
        # Direct-upstream recipes (e.g. liblc3plus, libfreeaptx,
        # pipewire-libs-extra) are imported from the project's own release
        # repository rather than Fedora dist-git. They carry a remote and
        # imported_at but no dist-git commit/tree; the verified source lock
        # lives in config/upstream-sources.json instead.
        for key in ("commit", "tree"):
            if data[key]:
                raise SystemExit(f"upstream import must not carry {key}: {path}")
    else:
        # Fedora dist-git imports pin the exact rawhide snapshot.
        for key in ("commit", "tree"):
            if not data[key]:
                raise SystemExit(f"rawhide import must carry {key}: {path}")


# Upstream provenance: every direct-source entry in config/upstream-sources.json
# must fetch its payload from upstream; a Fedora host must never sit in the
# primary ``url`` position. Fedora's lookaside is still allowed as a
# ``fallback_urls`` entry.
FEDORA_HOSTS = {"src.fedoraproject.org", "fedoraproject.org"}

# Structural exemptions: packages that cannot be re-pinned to a verbatim
# upstream archive because they are built from vendored Go source, ship
# a recipe file rather than a release tarball, or are patched by Fedora
# so the upstream sdist no longer matches the locked hash.
STRUCTURAL_FEDORA_EXCEPTIONS = {
    "containerd": "built from vendored Go source (gosource), no upstream tarball",
    "runc": "built from vendored Go source (gosource), no upstream tarball",
    "mozc": "built from vendored Go source (gosource), no upstream tarball",
    "alsa-firmware": "built from ftp.fedoraproject.org source, no upstream tarball",
    "alsa-tools": "built from ftp.fedoraproject.org source, no upstream tarball",
    "kde-filesystem": "no upstream tarball; ships a recipe file (teamnames)",
    "kf5": "no upstream tarball; ships a recipe file (macros.kf5)",
    "python-psutil": "Fedora patches the sdist; upstream sdist sha does not match the lock",
    "python-argcomplete": "Fedora patches the sdist; upstream sdist sha does not match the lock",
    "python-dbus-next": "Fedora patches the sdist; upstream sdist sha does not match the lock",
    "python-pydantic-core": "Fedora patches the sdist; upstream sdist sha does not match the lock",
}

# Work remaining: packages with Fedora lookaside primary URLs tracked for
# per-package upstream release feed discovery in issue #134 (and unresolved
# entries from #42).
WORK_REMAINING_FEDORA_PRIMARY = {
    "fwupd": "upstream release URL could not be resolved to a verbatim artifact",
    "graphene": "upstream release URL could not be resolved to a verbatim artifact",
    "lcms2": "upstream release URL could not be resolved to a verbatim artifact",
    "livesys-scripts": "upstream archive sha does not match the lock",
    "samba": "upstream release URL could not be resolved to a verbatim artifact",
    "xmlrpc-c": "upstream release URL could not be resolved to a verbatim artifact",
    **{
        name: "tracked in issue #134 for upstream release feed discovery"
        for name in [
            "SDL3",
            "adwaita-icon-theme-legacy",
            "alsa-sof-firmware",
            "appstream",
            "aribb24",
            "bluez",
            "cdparanoia",
            "codec2",
            "desktop-file-utils",
            "device-mapper-persistent-data",
            "double-conversion",
            "enchant2",
            "fdk-aac-free",
            "ffmpeg",
            "flac",
            "flatpak",
            "flite",
            "gcr3",
            "glib-networking",
            "gnome-keyring",
            "gsm",
            "gssdp",
            "gupnp",
            "gupnp-igd",
            "gweather-locations",
            "hidapi",
            "highway",
            "hunspell",
            "hunspell-en",
            "hwinfo",
            "hyphen",
            "ilbc",
            "iputils",
            "jpegxl",
            "kde-settings",
            "lame",
            "libICE",
            "libSM",
            "libXdmcp",
            "libXfont2",
            "libXmu",
            "libXt",
            "libXv",
            "libaribcaption",
            "libasyncns",
            "libatasmart",
            "libayatana-ido",
            "libburn",
            "libdatrie",
            "libdecor",
            "libebur128",
            "libfyaml",
            "libgusb",
            "libimobiledevice",
            "libimobiledevice-glue",
            "libisofs",
            "liblc3",
            "libldac",
            "libmanette",
            "libnice",
            "libnvme",
            "libogg",
            "libplist",
            "libproxy",
            "libsass",
            "libshout",
            "libsndfile",
            "libtdb",
            "libtheora",
            "libusbmuxd",
            "libvdpau",
            "libvisual",
            "libvorbis",
            "libvpl",
            "libvpx",
            "libx86emu",
            "libxcvt",
            "libxkbfile",
            "libxmlb",
            "libxshmfence",
            "linux-firmware",
            "lm_sensors",
            "lpcnetfreedv",
            "lttng-ust",
            "mdadm",
            "mesa-demos",
            "mobile-broadband-provider-info",
            "mpg123",
            "msgraph",
            "mtdev",
            "noopenh264",
            "openapv",
            "opencore-amr",
            "openjpeg",
            "opus",
            "orc",
            "passim",
            "protobuf",
            "protobuf3",
            "python-annotated-types",
            "python-distro",
            "python-pam",
            "python-typing-inspection",
            "rest",
            "rtkit",
            "sbc",
            "setools",
            "setxkbmap",
            "snowball",
            "sound-theme-freedesktop",
            "soxr",
            "spandsp",
            "speex",
            "taglib",
            "twolame",
            "v4l-utils",
            "vo-amrwbenc",
            "volume_key",
            "wavpack",
            "wireplumber",
            "wsdd",
            "xcb-util",
            "xcb-util-image",
            "xcb-util-keysyms",
            "xcb-util-renderutil",
            "xcb-util-wm",
            "xdg-dbus-proxy",
            "xdg-user-dirs",
            "xevd",
            "xeve",
            "xhost",
            "xkbcomp",
            "xmodmap",
            "xorg-x11-server-Xwayland",
            "xorg-x11-xauth",
            "xorg-x11-xinit",
            "xprop",
            "xrdb",
            "xvidcore",
            "zvbi",
        ]
    },
}

FEDORA_PRIMARY_EXCEPTIONS = {
    **STRUCTURAL_FEDORA_EXCEPTIONS,
    **WORK_REMAINING_FEDORA_PRIMARY,
}


def _primary_url(entry: dict) -> str | None:
    if "url" in entry:
        return entry["url"]
    if "url_template" in entry and "version" in entry:
        return entry["url_template"].format(version=entry["version"])
    return None


def check_fedora_primary(root: Path) -> None:
    config_path = root / "config" / "upstream-sources.json"
    if not config_path.is_file():
        return
    config = json.loads(config_path.read_text())
    violations = []
    for entry in config.get("packages", []):
        url = _primary_url(entry)
        if not url:
            continue
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname or ""
        is_fedora = (
            hostname in FEDORA_HOSTS
            or hostname.endswith(".fedoraproject.org")
        )
        if (
            is_fedora
            and entry["name"] not in FEDORA_PRIMARY_EXCEPTIONS
        ):
            violations.append(entry["name"])
    if violations:
        raise SystemExit(
            "fedora-primary source url not allowed (exceptions are documented in tools/validate.py): "
            + ", ".join(sorted(violations))
        )


def main(root: Path = Path(".")) -> int:
    packages_dir = root / "packages"
    if not packages_dir.is_dir():
        return 0
    for directory in sorted(packages_dir.iterdir()):
        if not directory.is_dir():
            continue
        path = directory / ".hummingbird-upstream.json"
        if not path.is_file():
            raise SystemExit(f"missing upstream provenance: {path}")
        data = json.loads(path.read_text())
        check_provenance(path, data)
    records = inventory(root)
    missing_locks = sorted(record.name for record in records if not record.source_locked)
    missing_packit = sorted(record.name for record in records if not record.packit_configured)
    if missing_locks or missing_packit:
        if missing_locks:
            print(f"packages missing source locks: {', '.join(missing_locks)}")
        if missing_packit:
            print(f"packages missing Packit config: {', '.join(missing_packit)}")
        return 1
    check_fedora_primary(root)
    print(f"validated {len(records)} source RPMs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
