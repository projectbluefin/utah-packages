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
import re
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
    # Fedora's samba-core-libs and libsmbclient both require libicuuc.so.77.
    # localsearch and nautilus reach them transitively; gvfs BuildRequires
    # libsmbclient-devel outright, and its stage-1 root installed
    # libicu-77.1-2.1.hum1 in run 35413902261 for exactly that reason.
    "samba": ("gvfs", "localsearch", "nautilus"),
    # Fedora's libical-3.0.20-7.fc44 requires libicuuc.so.77 directly. bluez
    # BuildRequires libical-devel and sat in the same stage as libical, so its
    # root took Fedora's copy -- confirmed in run 35413902261, which installed
    # libical-0:3.0.20-7.fc44 from fedora and then libicu-0:77.1-2.1.hum1.
    # The factory's own libical is clean: it built against libicu-78.3-8.hum1.
    "libical": ("bluez",),
    # Fedora's nautilus-50.x requires libicuuc.so.77 and libicui18n.so.77, and
    # also requires localsearch. nautilus-python is its only consumer here and
    # sat in the same stage 6, so its root had to take Fedora's nautilus -- and
    # could not. This one does not contaminate quietly, it fails the build:
    # localsearch (stage 4) was already excluded from Fedora by name, so the
    # root took the factory's, which requires libicui18n.so.78 and pins libicu
    # to 78.3. Run 35480019777 ended on
    #   package localsearch-3.12~beta-1.hum1.bfin from stages requires
    #   libicui18n.so.78, but none of the providers can be installed
    #   - cannot install both libicu-78.3-* and libicu-77.1-2.1.hum1
    #   - package nautilus-50.0-1.fc44 from fedora requires libicuuc.so.77
    # Ordering nautilus-python after nautilus settles it twice over: the
    # factory's nautilus is ICU 78 and, being built, is excluded from Fedora.
    "nautilus": ("nautilus-python",),
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
        (libxcrypt now comes directly from Hummingbird.) Pulling samba forward
        is only correct if the factory-owned dependencies still precede it.
        """
        required_before = {
            "samba": ("libtevent", "libtalloc", "libtdb", "icu"),
            # gvfs moved from stage 1 to 3 to land after samba; everything else
            # it is built from is stage 0, so nothing else constrains it.
            "gvfs": ("samba", "libnfs", "libsoup3", "libsecret", "udisks2"),
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


class IcuLinkerOrderingTests(unittest.TestCase):
    """Derive the rule rather than re-listing it each time one is found.

    Three contaminated packages were found one at a time -- localsearch and
    nautilus from the publish failure, gvfs by asking who consumes samba, bluez
    by asking which factory packages link ICU at all. That is three rounds of
    the same question, and the fourth would have been found the same slow way.

    The rule underneath: if the factory rebuilds a package X that links ICU,
    and another factory package consumes X, then the consumer must build in a
    strictly later stage. Otherwise the consumer resolves X from Fedora, whose
    build links whatever ICU Fedora used, and inherits that requirement.

    Not every same-stage pair is a live bug -- it only bites when Fedora's
    build of X actually requires libicuuc.so.77 -- but every such pair is a
    place where a Fedora ICU can enter a factory build root unnoticed, and the
    cost of ordering them correctly is a stage number.
    """

    PACKAGES = ROOT / "packages"

    @classmethod
    def setUpClass(cls):
        cls.provides, cls.subpackages = {}, {}
        for directory in sorted(cls.PACKAGES.iterdir()):
            spec = next(directory.glob("*.spec"), None)
            if spec is None:
                continue
            text = spec.read_text(errors="replace")
            match = re.search(r"^Name:\s*(\S+)", text, re.M)
            base = (match.group(1) if match else directory.name).replace(
                "%{name}", directory.name)
            names = {base}
            cls.provides.setdefault(base, directory.name)
            for sub in re.finditer(r"^%package\s+(-n\s+)?(\S+)", text, re.M):
                full = (sub.group(2) if sub.group(1)
                        else f"{base}-{sub.group(2)}").replace("%{name}", directory.name)
                cls.provides.setdefault(full, directory.name)
                names.add(full)
            cls.subpackages[directory.name] = names

    def icu_linkers(self) -> set[str]:
        found = set()
        for directory in sorted(self.PACKAGES.iterdir()):
            spec = next(directory.glob("*.spec"), None)
            if spec is None:
                continue
            for line in re.finditer(r"^BuildRequires:\s*(.+)$",
                                    spec.read_text(errors="replace"), re.M):
                if re.search(r"\blibicu-devel\b|\bicu\b|pkgconfig\(icu-",
                             line.group(1)):
                    found.add(directory.name)
                    break
        return found

    def test_no_factory_package_consumes_an_icu_linker_from_its_own_stage(self):
        linkers = self.icu_linkers()
        self.assertIn("samba", linkers, "the scan stopped finding known linkers")
        self.assertIn("libical", linkers)

        offenders = []
        for directory in sorted(self.PACKAGES.iterdir()):
            spec = next(directory.glob("*.spec"), None)
            if spec is None or directory.name not in STAGES:
                continue
            for line in re.finditer(r"^BuildRequires:\s*(.+)$",
                                    spec.read_text(errors="replace"), re.M):
                for dep in re.split(r"[,\s]+", line.group(1).strip()):
                    provider = self.provides.get(dep.strip())
                    if (provider in linkers and provider != directory.name
                            and STAGES.get(directory.name, 0) <= STAGES.get(provider, 0)):
                        offenders.append(
                            f"{directory.name} (stage {STAGES[directory.name]}) "
                            f"BuildRequires {dep.strip()} from {provider} "
                            f"(stage {STAGES[provider]})")
        self.assertEqual(
            sorted(set(offenders)), [],
            "these consumers build no later than the ICU-linking package they "
            "are built from, so they resolve it from Fedora and can inherit "
            "Fedora's ICU:\n  " + "\n  ".join(sorted(set(offenders))))



if __name__ == "__main__":
    unittest.main()
