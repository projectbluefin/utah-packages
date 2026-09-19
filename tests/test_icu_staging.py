"""A factory package must not be built against Fedora's ICU 77.

Hummingbird ships libicu 77.1 beside 78.3 under one package name, so a build
root installs exactly one. dnf picks the newest unless something in the root
*requires* libicuuc.so.77 -- and then it downgrades, libicu-devel follows the
base to match (icu.spec: `Requires: lib%{name}%{?_isa} = %{version}-%{release}`,
so there is no split to exploit), and whatever is built there links ICU 77.
The Hummingbird-only consumer transaction excludes ICU 77, so that package is
then uninstallable and publication fails.

Run 35413902261 is the worked example, and the chain runs entirely through the
factory's own output:

    samba-core-libs-4.24.6-1.fc44 (Fedora)  requires libicuuc.so.77
      -> localsearch (stage 4) resolved samba from Fedora, because the
         factory's samba was stage 6 and did not exist yet. Its root
         installed libicu-77.1-2.1.hum1 over five available 78.3 builds,
         and localsearch-3.12~beta-1.hum1.bfin came out requiring .so.77.
      -> nautilus (stage 6) requires localsearch, so its root downgraded to
         ICU 77 as well, and nautilus-51~beta-1.hum1.bfin required .so.77.
      -> publish step 6 refused nautilus: no ICU 77 in the consumer set.

The factory's own samba is clean -- it built against libicu-78.3-1.hum1.bfin
with no .so.77 anywhere in its root. It was simply built too late to be used.
So the fix is ordering, not exclusion: excluding libicu 77 from the build root
was tried and removed in de4ac4d, because Fedora packages the root legitimately
needs (libical) require .so.77 and excluding it strands them outright.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    entry["name"]: entry.get("stage", 0)
    for entry in json.loads((ROOT / "config/upstream-sources.json").read_text())["packages"]
}

# Factory packages that rebuild a Fedora package whose Fedora build requires
# libicuuc.so.77, paired with the packages whose build roots pull them in. The
# rebuild must land in a strictly earlier stage than every consumer, or the
# consumer resolves Fedora's ICU-77 build instead and inherits the requirement.
ICU_77_REBUILDS = {
    "samba": ("localsearch", "nautilus"),
}


class IcuStagingTests(unittest.TestCase):
    def test_icu_77_rebuilds_precede_every_consumer(self):
        for rebuild, consumers in ICU_77_REBUILDS.items():
            for consumer in consumers:
                with self.subTest(rebuild=rebuild, consumer=consumer):
                    self.assertLess(
                        STAGES[rebuild], STAGES[consumer],
                        f"{rebuild} (stage {STAGES[rebuild]}) must build before "
                        f"{consumer} (stage {STAGES[consumer]}), or {consumer} "
                        f"resolves Fedora's ICU-77 {rebuild} and links ICU 77",
                    )

    def test_each_rebuild_still_follows_its_own_factory_dependencies(self):
        """Moving a package earlier must not outrun what it is built from.

        samba BuildRequires the factory's libtevent, libtalloc, libtdb and icu.
        Pulling samba forward is only correct if those still precede it.
        """
        required_before = {
            "samba": ("libtevent", "libtalloc", "libtdb", "icu", "libxcrypt"),
        }
        for pkg, deps in required_before.items():
            for dep in deps:
                with self.subTest(pkg=pkg, dep=dep):
                    self.assertLess(
                        STAGES[dep], STAGES[pkg],
                        f"{pkg} (stage {STAGES[pkg]}) is built from {dep} "
                        f"(stage {STAGES[dep]}); the dependency must come first",
                    )

    def test_libtevent_precedes_samba_and_follows_libtalloc(self):
        self.assertLess(STAGES["libtalloc"], STAGES["libtevent"])
        self.assertLess(STAGES["libtevent"], STAGES["samba"])


if __name__ == "__main__":
    unittest.main()
