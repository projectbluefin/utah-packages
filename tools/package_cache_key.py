#!/usr/bin/env python3
"""The tag under which one package's built RPMs are cached.

The factory's only skip mechanism is the published consumer repository, and
publication is atomic: it needs every stage, plus precedence, plus the
Hummingbird-only transaction. So a failing gate freezes the witness, and
everything outside it rebuilds from scratch on every run. The witness has been
at 67 packages since 2026-08-30; webkitgtk, which is not in it, built 20
times on 19 September alone at 182 minutes a build, with byte-identical inputs
(issue #177).

This is the other half of the answer, modelled on projectbluefin/utah's
scripts/kernel-cache-tag.sh: a cache that answers "have we already built this
exact thing", kept strictly separate from "is the repository coherent enough to
install from". Nothing installs from the cache. Only tools/rebuild_plan.py reads
it, and a hit is materialised as this stage's ordinary artifact, so precedence,
the transaction check and publish see an identical repository either way. That
property is what makes a hit safe to trust: it changes how the RPMs were
obtained, never what the run validates.

Why keying on the recipe alone would be wrong
---------------------------------------------
A stage-5 package builds in a root containing earlier stages' fresh output. A
key over the spec alone would hand back an RPM linked against different
libraries than this run produced -- precisely the incoherence the publish gate
exists to catch, arriving through the cache instead. So the resolved build root
is part of the key, and the key is therefore computed *after* dnf has resolved
builddep rather than before. That costs the resolution (about a minute) and
saves the compile.

Why the chain holds across stages
---------------------------------
It only works if an unchanged recipe yields an unchanged NEVR, or every stage's
resolved root would differ from the last run's and nothing would ever hit. It
does: many specs use %autorelease, which rpmautospec derives from the
committed packages/<name>/changelog and not from a build counter. Confirmed
empirically -- libical-3.0.20-1.hum1.bfin came out with the identical NEVR in
run 35413902261 and run 35445712318, twelve hours and many commits apart.

Hashing whole files, comments included, is deliberate, for the reason
kernel-cache-tag.sh gives: it can only ever rebuild something that did not need
rebuilding, never reuse something stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Bumped when the meaning of the key changes, so an old cache entry computed
# under different rules can never be mistaken for a current one.
SCHEMA = "1"

# The tag is the key and nothing else. A 32-character hex digest always matches
# the OCI tag grammar ([a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}), so the tag can never
# be invalid and there is nothing to validate.
#
# An earlier revision prefixed the package name -- utah-packages-cache:nautilus-<key>
# -- for legibility in the registry. It was removed because the prefix bought
# nothing the key does not already carry (the package name is inside the hash,
# see cache_key) while introducing a failure mode the bare key cannot have: RPM
# names are laxer than OCI tags, `gtk+` and `libstdc++` are legal packages and
# illegal tag components, and a future import would have silently produced a
# mangled tag and a permanent cache miss that reads as a correctness bug.
#
# Legibility is better served where it is actually needed. The build log already
# prints the package and the key it computed, which is what you read when a
# build you expected to hit did not, and the push step sets these labels on the
# cache image so `skopeo inspect` answers "what is this entry" without a side
# database:
#
#     org.opencontainers.image.title      = <package>
#     org.opencontainers.image.version    = <nevr>
#     org.opencontainers.image.revision   = <the commit built from>
#     org.projectbluefin.factory.disttag  = <.humN.bfin[.N]>
#
# Browsing a tag list was never the way to answer that question anyway.


def recipe_digest(package_dir: Path) -> str:
    """Every file in the recipe, by sorted relative path.

    Paths are hashed alongside contents so a rename is a change, and the
    directory is walked rather than globbed for *.spec so patches, the
    changelog (which %autorelease reads), sources and keyrings all count.
    """
    digest = hashlib.sha256()
    files = sorted(
        (path for path in package_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(package_dir).as_posix(),
    )
    if not files:
        raise ValueError(f"no files under {package_dir}")
    for path in files:
        digest.update(path.relative_to(package_dir).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def normalise_root(nevras: list[str]) -> list[str]:
    """The resolved build root as a stable, order-independent list.

    dnf reports installs in transaction order, which varies between runs for
    reasons that do not change the result, so sorting is what makes the key
    stable. Duplicates collapse: the same NEVRA twice is the same root.
    """
    return sorted({item.strip() for item in nevras if item.strip()})


def cache_key(
    *,
    package: str,
    recipe: str,
    buildroot_digest: str,
    factory_digest: str,
    resolved_root: list[str],
    disttag: str,
) -> str:
    """The cache tag for one package built under one exact set of inputs.

    Every field changes what lands in the RPMs:
      package           -- the name, so two recipes cannot collide
      recipe            -- spec, patches, sources, changelog
      buildroot_digest  -- a different compiler produces a different binary
      factory_digest    -- what the root could install from the factory
      resolved_root     -- what it actually installed, post-resolution
      disttag           -- .humN.bfin[.N], which lands in the Release
    """
    payload = json.dumps(
        {
            "schema": SCHEMA,
            "package": package,
            "recipe": recipe,
            "buildroot": buildroot_digest,
            "factory": factory_digest,
            "root": normalise_root(resolved_root),
            "disttag": disttag,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:32]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package")
    parser.add_argument("--buildroot-digest", required=True)
    parser.add_argument("--factory-digest", default="")
    parser.add_argument("--disttag", required=True)
    parser.add_argument(
        "--resolved-root",
        required=True,
        help="File of NEVRAs installed for builddep, one per line, or - for stdin",
    )
    args = parser.parse_args()

    package_dir = ROOT / "packages" / args.package
    if not package_dir.is_dir():
        print(f"no recipe at {package_dir}", file=sys.stderr)
        return 1

    if args.resolved_root == "-":
        nevras = sys.stdin.read().splitlines()
    else:
        nevras = Path(args.resolved_root).read_text().splitlines()
    if not normalise_root(nevras):
        # An empty root means the resolution step did not report, and a key over
        # nothing would collide across genuinely different roots. Refuse rather
        # than emit a key that could serve a wrong RPM.
        print(
            "resolved build root is empty; refusing to compute a cache key",
            file=sys.stderr,
        )
        return 1

    key = cache_key(
        package=args.package,
        recipe=recipe_digest(package_dir),
        buildroot_digest=args.buildroot_digest,
        factory_digest=args.factory_digest,
        resolved_root=nevras,
        disttag=args.disttag,
    )
    print(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
