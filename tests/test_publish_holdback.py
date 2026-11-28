#!/usr/bin/env python3
"""Regression test: a publication holds back what would break it, and publishes the rest.

Run 44224171778 built libnfs 8.0.0 (libnfs.so.18) in wave 0 and its
consumers, gvfs and qemu, in waves 10 and 12. Every publication of that run
failed its consumer transaction on

    nothing provides libnfs.so.17()(64bit) needed by gvfs-nfs-1.62.0-1.hum1.bfin

so 491 source packages that built and broke nothing were published by none
of them. ``tools/publish_holdback.py`` decides, from repository metadata,
which accepted builds to hold back so the candidate still resolves. This
proves:

* a build that drops a capability a published package still needs is held,
  and the published build it would have replaced stays -- which is what the
  old consumer was linked against;
* a hold follows direct BuildRequires edges of the build graph, restricted to this
  publication: what it built against a held library is held too;
* a Requires the published repository already left unmet is never a reason
  to hold anything, and Hummingbird's provides count;
* a new build that needs something nothing provides is held itself;
* the acceptance fixture, cut from run 44224171778's own metadata, holds
  libnfs alone from the wave-0 publication, and libnfs with gvfs from a
  publication through wave 10 (qemu not yet rebuilt);
* the publication workflow runs the hold before it assembles, and the final
  publication fails the run after pushing whenever something was held.
"""
from __future__ import annotations

import gzip
import http.client
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from xml.etree import ElementTree
from xml.sax.saxutils import quoteattr

from tools.publish_holdback import (
    Binary,
    binaries_from_primary,
    holdback,
    judged,
    main,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "holdback-44224171778"


def primary_xml(packages: list[dict]) -> bytes:
    """A primary.xml carrying just what the decision reads."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<metadata xmlns="http://linux.duke.edu/metadata/common" '
           'xmlns:rpm="http://linux.duke.edu/metadata/rpm" '
           f'packages="{len(packages)}">']
    for package in packages:
        name, source = package["name"], package["source"]
        ver, rel = package.get("ver", "1"), package.get("rel", "1.hum1.bfin")
        arch = package.get("arch", "x86_64")
        out.append('<package type="rpm">')
        out.append(f"<name>{name}</name><arch>{arch}</arch>")
        out.append(f'<version epoch="0" ver="{ver}" rel="{rel}"/>')
        out.append(f'<location href="{package.get("href", f"{name}-{ver}-{rel}.{arch}.rpm")}"/>')
        out.append("<format>")
        out.append(f"<rpm:sourcerpm>{source}-{ver}-{rel}.src.rpm</rpm:sourcerpm>")
        out.append("<rpm:provides>")
        for capability in package.get("provides", []):
            out.append(f"<rpm:entry name={quoteattr(capability)}/>")
        out.append("</rpm:provides><rpm:requires>")
        for capability in package.get("requires", []):
            out.append(f"<rpm:entry name={quoteattr(capability)}/>")
        out.append("</rpm:requires>")
        for path in package.get("files", []):
            out.append(f"<file>{path}</file>")
        out.append("</format></package>")
    out.append("</metadata>")
    return "\n".join(out).encode()


def binary(name, source, provides=(), requires=()):
    return Binary(name=name, source=source, nevra=f"{name}-1-1.x86_64",
                  provides=frozenset({name, *provides}), requires=frozenset(requires))


# The published repository before run 44224171778, as far as libnfs reaches.
SEED = [
    binary("libnfs", "libnfs", ["libnfs.so.17()(64bit)"], ["libc.so.6()(64bit)"]),
    binary("gvfs-nfs", "gvfs", [], ["libnfs.so.17()(64bit)", "gvfs-client"]),
    binary("gvfs-client", "gvfs", [], ["libglib-2.0.so.0()(64bit)"]),
    binary("qemu-block-nfs", "qemu", [], ["libnfs.so.17()(64bit)"]),
    binary("libass", "libass", ["libass.so.9()(64bit)"], ["libc.so.6()(64bit)"]),
]
HUMMINGBIRD = [
    binary("glibc", "glibc", ["libc.so.6()(64bit)"]),
    binary("glib2", "glib2", ["libglib-2.0.so.0()(64bit)"], ["libc.so.6()(64bit)"]),
]

NEW_LIBNFS = binary("libnfs", "libnfs", ["libnfs.so.18()(64bit)"], ["libc.so.6()(64bit)"])
NEW_LIBASS = binary("libass", "libass", ["libass.so.9()(64bit)"], ["libc.so.6()(64bit)"])
NEW_GVFS = [
    binary("gvfs-nfs", "gvfs", [], ["libnfs.so.18()(64bit)", "gvfs-client"]),
    binary("gvfs-client", "gvfs", ["libgvfscommon.so.0()(64bit)"], ["libglib-2.0.so.0()(64bit)"]),
]
NEW_QEMU = [binary("qemu-block-nfs", "qemu", [], ["libnfs.so.18()(64bit)"])]


def decide(built, *, seed=SEED, external=HUMMINGBIRD, install=None, dependents=None):
    """`install` None: the transaction installs every binary (consumer: built)."""
    return holdback(seed=seed, built=built, external=list(external),
                    accepted={b.source for b in built}, install=install,
                    dependents=dependents)


class HoldbackTests(unittest.TestCase):
    def test_a_moved_soname_is_held_while_a_published_consumer_needs_the_old_one(self):
        result = decide([NEW_LIBNFS, NEW_LIBASS])
        self.assertEqual(result.names(), ["libnfs"])
        reasons = " ".join(result.withheld["libnfs"])
        self.assertIn("gvfs-nfs", reasons)
        self.assertIn("qemu-block-nfs", reasons)
        self.assertIn("libnfs.so.17()(64bit)", reasons)

    def test_holding_it_leaves_the_old_consumer_resolving_against_the_old_build(self):
        # What the candidate looks like once libnfs is held: the seed's libnfs,
        # with its .so.17, is what gvfs-nfs and qemu-block-nfs resolve to.
        result = decide([NEW_LIBNFS, NEW_LIBASS])
        publishing = {"libass", "libnfs"} - set(result.withheld)
        candidate = [b for b in SEED if b.source not in publishing] + [NEW_LIBASS]
        provided = set().union(*(b.provides for b in candidate + HUMMINGBIRD))
        for b in candidate:
            self.assertLessEqual(set(b.requires), provided, b.name)
        self.assertIn(SEED[0], candidate)

    def test_a_hold_takes_what_this_publication_built_against_it(self):
        # Through wave 10: gvfs was rebuilt against libnfs.so.18, qemu (wave
        # 12) not yet, so the published qemu-block-nfs still needs .so.17.
        result = decide([NEW_LIBNFS, NEW_LIBASS, *NEW_GVFS])
        self.assertEqual(result.names(), ["gvfs", "libnfs"])
        self.assertEqual(result.withheld["gvfs"], [
            "built against libnfs, which is held back: "
            "gvfs-nfs-1-1.x86_64 needs libnfs.so.18()(64bit)"])

    def test_the_closure_is_transitive(self):
        # nautilus links a library only the new gvfs ships: holding gvfs
        # (because libnfs is held) holds nautilus in the next round.
        new_gvfs = [NEW_GVFS[0], binary("gvfs-client", "gvfs", ["libgvfscommon.so.1()(64bit)"])]
        nautilus = binary("nautilus", "nautilus", [], ["libgvfscommon.so.1()(64bit)"])
        result = decide([NEW_LIBNFS, *new_gvfs, nautilus])
        self.assertEqual(result.names(), ["gvfs", "libnfs", "nautilus"])
        self.assertGreaterEqual(result.rounds, 3)

    def test_a_dependent_that_still_resolves_against_the_held_build_is_not_held(self):
        # It BuildRequires gvfs, but needs nothing the published gvfs lacks:
        # holding it would publish less for no reason.
        nautilus = binary("nautilus", "nautilus", [], ["gvfs-client"])
        result = decide([NEW_LIBNFS, *NEW_GVFS, nautilus])
        self.assertEqual(result.names(), ["gvfs", "libnfs"])

    def test_the_build_graph_holds_what_its_requires_cannot_show(self):
        # A consumer of libnfs's headers or static library: built against
        # libnfs 8, but nothing in its Requires says so. The build graph does.
        nfs_tool = binary("nfs-tool", "nfs-tool", [], ["libc.so.6()(64bit)"])
        built = [NEW_LIBNFS, NEW_LIBASS, nfs_tool]
        self.assertEqual(decide(built).names(), ["libnfs"])
        result = decide(built, dependents={"libnfs": {"nfs-tool", "qemu"}})
        self.assertEqual(result.names(), ["libnfs", "nfs-tool"])
        self.assertIn("BuildRequires it", result.withheld["nfs-tool"][0])

    def test_the_graph_holds_only_direct_dependents(self):
        # nautilus BuildRequires gvfs, which BuildRequires libnfs, but nautilus
        # needs nothing only the new gvfs provides. Following the graph
        # through gvfs held 215 builds of run 44478890278 behind one failed
        # consumer of abseil-cpp; a real link is the metadata's to show.
        nautilus = binary("nautilus", "nautilus", [], ["gvfs-client"])
        result = decide([NEW_LIBNFS, *NEW_GVFS, nautilus],
                        dependents={"libnfs": {"gvfs", "qemu"}, "gvfs": {"nautilus"}})
        self.assertEqual(result.names(), ["gvfs", "libnfs"])
        # qemu BuildRequires libnfs too, but this publication did not build
        # it: there is nothing of it to hold.
        self.assertNotIn("qemu", result.withheld)

    def test_a_dependent_further_out_is_still_held_when_it_links_the_held_build(self):
        # One hop of graph, then the metadata: nautilus links a library only
        # the new gvfs ships, so it is held although its edge to libnfs is
        # two steps long.
        new_gvfs = [NEW_GVFS[0], binary("gvfs-client", "gvfs", ["libgvfscommon.so.1()(64bit)"])]
        nautilus = binary("nautilus", "nautilus", [], ["libgvfscommon.so.1()(64bit)"])
        result = decide([NEW_LIBNFS, *new_gvfs, nautilus],
                        dependents={"libnfs": {"gvfs"}, "gvfs": {"nautilus"}})
        self.assertEqual(result.names(), ["gvfs", "libnfs", "nautilus"])

    def test_built_against_a_held_build_counts_outside_the_transaction_too(self):
        # The transaction installs only libass, but gvfs-nfs must not ship
        # linked against a libnfs that is not shipped.
        result = decide([NEW_LIBNFS, NEW_LIBASS, *NEW_GVFS], install={"libass", "qemu-block-nfs"})
        self.assertEqual(result.names(), ["gvfs", "libnfs"])

    def test_once_every_consumer_is_rebuilt_nothing_is_held(self):
        # The final publication of that run, had it seen all its artifacts.
        result = decide([NEW_LIBNFS, NEW_LIBASS, *NEW_GVFS, *NEW_QEMU])
        self.assertEqual(result.names(), [])

    def test_a_requirement_the_seed_already_left_unmet_holds_nothing(self):
        seed = SEED + [binary("vala-devel", "vala", [], ["/usr/bin/valac-0.56"])]
        rebuilt = binary("vala-devel", "vala", [], ["/usr/bin/valac-0.56"])
        self.assertEqual(decide([rebuilt, NEW_LIBASS], seed=seed).names(), [])

    def test_hummingbird_satisfies_a_requirement(self):
        new = binary("libass", "libass", ["libass.so.9()(64bit)"], ["libfribidi.so.0()(64bit)"])
        fribidi = binary("fribidi", "fribidi", ["libfribidi.so.0()(64bit)"])
        self.assertEqual(decide([new], external=HUMMINGBIRD + [fribidi]).names(), [])
        held = decide([new])
        self.assertEqual(held.names(), ["libass"])
        self.assertIn("nothing provides", held.withheld["libass"][0])

    def test_a_dropped_subpackage_is_the_fault_of_the_build_that_dropped_it(self):
        new_gvfs = [binary("gvfs-nfs", "gvfs", [], ["libnfs.so.17()(64bit)"])]  # no gvfs-client
        seed = SEED + [binary("nautilus", "nautilus", [], ["gvfs-client"])]
        result = decide(new_gvfs, seed=seed)
        self.assertEqual(result.names(), ["gvfs"])
        self.assertIn("nautilus", result.withheld["gvfs"][0])

    def test_a_build_needing_only_a_held_build_is_held_in_a_later_round(self):
        # Holding libnfs removes the .so.18 the new gvfs-nfs needs.
        result = decide([NEW_LIBNFS, *NEW_GVFS])
        self.assertEqual(result.names(), ["gvfs", "libnfs"])
        self.assertGreaterEqual(result.rounds, 2)

    def test_an_empty_seed_publishes_what_resolves(self):
        result = decide([NEW_LIBNFS, NEW_LIBASS], seed=[])
        self.assertEqual(result.names(), [])

    def test_only_what_the_transaction_installs_is_judged(self):
        # Utah's contract installs gvfs-nfs, not qemu-block-nfs. Through wave
        # 10 gvfs is rebuilt against libnfs.so.18 and qemu is not: the
        # published qemu-block-nfs breaks, but nothing the transaction
        # installs needs it, so dnf would pass and nothing is held.
        through10 = [NEW_LIBNFS, NEW_LIBASS, *NEW_GVFS]
        self.assertEqual(decide(through10, install={"gvfs-nfs", "libass"}).names(), [])
        # Wave 0 alone: the contract's gvfs-nfs still needs .so.17.
        self.assertEqual(decide([NEW_LIBNFS, NEW_LIBASS], install={"gvfs-nfs"}).names(), ["libnfs"])
        # Reached through a Requires, not named: gvfs-nfs is pulled in by
        # something the contract names.
        seed = SEED + [binary("nautilus", "nautilus", [], ["gvfs-nfs"])]
        self.assertEqual(decide([NEW_LIBNFS], seed=seed, install={"nautilus"}).names(), ["libnfs"])
        # A consumer that does install qemu-block-nfs holds both.
        self.assertEqual(decide(through10, install={"qemu-block-nfs"}).names(), ["gvfs", "libnfs"])

    def test_a_devel_package_gaining_an_unmet_requires_outside_the_transaction_holds_nothing(self):
        devel = binary("libass-devel", "libass", [], ["pkgconfig(fribidi)"])
        self.assertEqual(decide([NEW_LIBASS, devel], install={"libass"}).names(), [])
        self.assertEqual(decide([NEW_LIBASS, devel]).names(), ["libass"])

    def test_a_package_the_transaction_names_that_a_build_dropped_holds_that_build(self):
        new_gvfs = [binary("gvfs-nfs", "gvfs", [], ["libnfs.so.17()(64bit)"])]  # no gvfs-client
        result = decide(new_gvfs, install={"gvfs-client"})
        self.assertEqual(result.names(), ["gvfs"])
        self.assertIn("the consumer transaction needs gvfs-client", result.withheld["gvfs"][0])

    def test_only_requirements_primary_xml_can_answer_are_judged(self):
        self.assertTrue(judged("libnfs.so.17()(64bit)"))
        self.assertTrue(judged("/usr/bin/python3"))
        self.assertTrue(judged("/etc/pam.d/system-auth"))
        self.assertFalse(judged("/usr/share/icons/hicolor"))
        self.assertFalse(judged("rpmlib(PayloadIsZstd)"))
        self.assertFalse(judged("(foo if bar)"))
        self.assertFalse(judged("config(gvfs)"))


class PrimaryTests(unittest.TestCase):
    def test_reads_provides_files_and_judged_requires_by_source(self):
        xml = primary_xml([
            {"name": "gvfs-nfs", "source": "gvfs", "provides": ["gvfs-nfs(x86-64)"],
             "requires": ["libnfs.so.17()(64bit)", "rpmlib(CompressedFileNames)", "/usr/share/x"],
             "files": ["/usr/libexec/gvfsd-nfs", "/usr/bin/gvfs-nfs"]},
            {"name": "gvfs", "source": "gvfs", "arch": "src"},
        ])
        [found] = binaries_from_primary(xml)
        self.assertEqual(found.source, "gvfs")
        self.assertEqual(found.requires, {"libnfs.so.17()(64bit)"})
        self.assertIn("/usr/bin/gvfs-nfs", found.provides)
        self.assertIn("gvfs-nfs", found.provides)
        self.assertEqual(found.nevra, "gvfs-nfs-1-1.hum1.bfin.x86_64")

    def test_bootstrap_builds_are_not_publishable(self):
        xml = primary_xml([{"name": "malcontent-libs", "source": "malcontent", "rel": "0.bootstrap.hum1.bfin"}])
        self.assertEqual(len(binaries_from_primary(xml)), 1)
        self.assertEqual(binaries_from_primary(xml, publishable_only=True), [])


def write_repo(directory: Path, primary: bytes) -> Path:
    """A repository directory whose repodata holds just this primary.xml."""
    repodata = directory / "repodata"
    repodata.mkdir(parents=True)
    with gzip.open(repodata / "primary.xml.gz", "wb") as handle:
        handle.write(primary)
    (repodata / "repomd.xml").write_text(
        '<repomd xmlns="http://linux.duke.edu/metadata/repo">'
        '<data type="primary"><location href="repodata/primary.xml.gz"/></data></repomd>')
    return directory


class Run44224171778Tests(unittest.TestCase):
    """Acceptance: run 44224171778's own metadata.

    Cut by ``fixtures/holdback-44224171778/cut.py`` from the run's real
    inputs: the primary.xml of the image it seeded from
    (ghcr.io/projectbluefin/utah-packages@sha256:744c4632), createrepo_c
    metadata over its RPM artifacts (wave 0, waves 0..10, and all thirteen
    waves), and Hummingbird's primary.xml -- reduced to libnfs, gvfs, qemu,
    gdm, forty wave-0 sources, and everything their Requires reach.

    The full, uncut inputs give the same answers, and dnf agrees with each
    (see the pull request): wave 0 holds libnfs alone and publishes the other
    415 sources; the whole run holds gdm, whose 51.0 needs a pam_oo7 that
    nothing provides because oo7 failed to build -- a second break that dnf,
    which reports only its first problem, never named -- and the two
    sources that BuildRequire it directly. autofs reaches gdm only through
    sssd and needs nothing only the new gdm provides, so it is not held.
    """

    GDM = ["gdm", "gnome-initial-setup", "sssd"]

    def run_cli(self, built: str, install: list[str] | None = None) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rows = json.loads(gzip.decompress((FIXTURE / "graph-rows.json.gz").read_bytes()))
            for recipe, files in rows.items():
                for name, text in files.items():
                    (tmp / "rows" / recipe).mkdir(parents=True, exist_ok=True)
                    (tmp / "rows" / recipe / name).write_text(text)
            seed = write_repo(tmp / "seed", gzip.decompress((FIXTURE / "seed-primary.xml.gz").read_bytes()))
            built_repo = write_repo(tmp / "built", gzip.decompress((FIXTURE / built).read_bytes()))
            external = tmp / "hummingbird.xml"
            external.write_bytes(gzip.decompress((FIXTURE / "hummingbird-primary.xml.gz").read_bytes()))
            names = (FIXTURE / "install.txt").read_text().split() + (install or [])
            (tmp / "install.txt").write_text("\n".join(names) + "\n")
            output = tmp / "withheld.json"
            argv = ["--seed", str(seed), "--built", str(built_repo), "--external", str(external),
                    "--install", str(tmp / "install.txt"), "--graph", str(tmp / "rows"),
                    "--output", str(output)]
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(argv), 0)
            result = json.loads(output.read_text())
            result["summary"] = out.getvalue()
            return result

    def test_publish0_holds_libnfs_and_publishes_the_rest_of_wave_0(self):
        result = self.run_cli("wave0-primary.xml.gz")
        self.assertEqual(sorted(result["withheld"]), ["libnfs"])
        self.assertEqual(result["withheld"]["libnfs"], [
            "gvfs-nfs-1.62.0-1.hum1.bfin.x86_64 needs libnfs.so.17()(64bit), "
            "which the new libnfs no longer provides"])
        self.assertIn("### Held back from this publication", result["summary"])

    def test_a_consumer_of_qemu_block_nfs_holds_libnfs_and_gvfs_built_against_it(self):
        # Through wave 10, gvfs is rebuilt against libnfs.so.18 and qemu (wave
        # 12) is not. A transaction that installs qemu-block-nfs needs the old
        # libnfs, so libnfs is held, and gvfs, which was linked against the
        # new one, is held with it. gdm is held for its own reason.
        result = self.run_cli("through10-primary.xml.gz", install=["qemu-block-nfs"])
        self.assertEqual(sorted(result["withheld"]), sorted(self.GDM + ["gvfs", "libnfs"]))
        self.assertIn("built against libnfs, which is held back", result["withheld"]["gvfs"][0])

    def test_through_wave_10_the_contract_needs_only_gdm_held(self):
        # gvfs-nfs is rebuilt and resolves against the new libnfs; the old
        # qemu-block-nfs breaks, but the contract does not install it.
        self.assertEqual(sorted(self.run_cli("through10-primary.xml.gz")["withheld"]), self.GDM)

    def test_the_whole_run_holds_gdm_and_what_was_built_against_it(self):
        result = self.run_cli("all-primary.xml.gz")
        self.assertEqual(sorted(result["withheld"]), self.GDM)
        self.assertEqual(result["withheld"]["gdm"], [
            "gdm-1:51.0-2.hum1.bfin.x86_64 needs pam_oo7, which nothing provides"])
        self.assertIn("built against gdm", result["withheld"]["sssd"][0])


class HummingbirdUnreadableTests(unittest.TestCase):
    """Hummingbird's metadata cannot be read: nothing is held back.

    publish-repository.yml promises this: the consumer transaction then
    decides the publication alone. Any other failure must still fail it.
    """

    def run_without_external(self, **fetch):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # No repodata: read_primary() returns None for both repositories,
            # so the only fetch_primary call is the one for Hummingbird.
            (tmp / "seed").mkdir()
            (tmp / "built").mkdir()
            output = tmp / "withheld.json"
            argv = ["--seed", str(tmp / "seed"), "--built", str(tmp / "built"),
                    "--install-all", "--output", str(output)]
            with patch("tools.rebuild_matrix.fetch_primary", **fetch), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
                code = main(argv)
            return code, json.loads(output.read_text()), err.getvalue()

    def test_an_unreachable_hummingbird_holds_nothing(self):
        code, result, err = self.run_without_external(
            side_effect=urllib.error.URLError("down"))
        self.assertEqual(code, 0)
        self.assertEqual(result, {"withheld": {}})
        self.assertIn("hold-back not decided", err)

    def test_a_cut_off_download_holds_nothing(self):
        # packages.redhat.com stalls mid-download under load; a connection
        # closed early makes read() raise IncompleteRead, not an OSError.
        code, result, err = self.run_without_external(
            side_effect=http.client.IncompleteRead(b"", 100))
        self.assertEqual(code, 0)
        self.assertEqual(result, {"withheld": {}})
        self.assertIn("hold-back not decided", err)

    def test_a_listing_that_does_not_parse_still_fails(self):
        # Only an unreadable Hummingbird fails open; a bad listing is a bug.
        with self.assertRaises(ElementTree.ParseError):
            self.run_without_external(return_value=b"<metadata")


if __name__ == "__main__":
    unittest.main()
