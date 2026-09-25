#!/bin/bash
# A hermetic mock build, the way Hummingbird's ci/build_rpms.sh --hermetic
# does it: resolve the build root once and record it, then build offline from
# exactly that record.
#
#   hermetic_build.sh lock    online: render the mock config, let mock
#                             resolve every BuildRequires (dynamic ones
#                             included) and write buildroot_lock.json
#   hermetic_build.sh build   materialize the lock into a local repository,
#                             then build with no network at all
#
# Run by build-stage.yml inside the shared build root (utah-buildroot:run),
# privileged, with /work, /packages, /repos (config) and /tools mounted.
# Between the two phases the workflow computes the package cache key from
# the lock, so a cache hit skips the offline build entirely.
#
# Environment: PACKAGE, FACTORY_REPO, DIST_BUMP, BUILDROOT_ICU77,
# BOOTSTRAP_IMAGE (the pinned build root, from config/buildroot-image).
#
# Outputs under /work/hermetic: mock.cfg and mock.cfg.sha256, the lockfile
# lock/buildroot_lock.json with the SRPM mock built beside it, repo/ (build
# phase); /work/cache/root and /work/cache/disttag for the cache key; RPMs in
# /work/result.
set -euo pipefail
phase=${1:?lock or build}
H=/work/hermetic
mkdir -p "$H" /work/cache /work/result /work/reports

install_tools() {
  dnf -y -q install mock createrepo_c rpm-build python3 >/dev/null
  # mock builds as the user who invoked it. Invoked as root, the whole
  # build ran as root, and flac's %check refused it -- "iterator claims file
  # is writable when tester thinks it should not be; are you running as
  # root?" -- exactly the failure the container lane's mockbuild user fixed.
  # Hummingbird runs its mock as mockbuilder for the same reason.
  id -u mockbuilder >/dev/null 2>&1 || useradd -m -G mock mockbuilder
  mkdir -p "$H" /work/result /work/cache /work/staged
  chown -R mockbuilder:mock "$H" /work/result /work/cache /work/staged
  # mock pulls the bootstrap image with podman inside this container. The
  # container root is overlayfs, which podman cannot stack overlay on, so
  # its storage lives on the volume build-stage.yml mounts there.
  mkdir -p /etc/containers
  printf "[storage]\ndriver = \"overlay\"\ngraphroot = \"/var/lib/containers/storage\"\n" \
    > /etc/containers/storage.conf
}

render_config() {
  PRIOR=
  STAGES=
  if [ -n "$(find /work/prior -name "*.rpm" -print -quit 2>/dev/null)" ]; then
    createrepo_c -q /work/prior
    PRIOR=$(find /work/prior -name "*.rpm" -type f -print0 \
      | xargs -0 -r rpm -qp --qf "%{NAME}\n" 2>/dev/null | sort -u | paste -sd, -)
    STAGES=/work/prior
  fi
  HB_EXTRA=
  if [ "${BUILDROOT_ICU77:-false}" != true ]; then
    HB_EXTRA="libicu-77.*-*hum1,libicu-devel-77.*-*hum1"
  fi
  python3 /tools/mock_config.py \
    --output "$H/mock.cfg" \
    --factory-repo "${FACTORY_REPO:-}" \
    --stages-dir "$STAGES" \
    --prior-built "$PRIOR" \
    --bootstrap-image "$BOOTSTRAP_IMAGE" \
    --hummingbird-exclude "$HB_EXTRA" >/dev/null
  sha256sum "$H/mock.cfg" | tee "$H/mock.cfg.sha256"
}

lock() {
  install_tools
  render_config
  staged=/work/staged/$PACKAGE
  rm -rf "$staged" "$H/lock"
  mkdir -p "$staged"
  cp -a "/packages/$PACKAGE/." "$staged/"
  cp -a "/work/sources/$PACKAGE/." "$staged/"
  spec=$(find "$staged" -maxdepth 1 -name "*.spec" -print -quit)
  # The disttag is Hummingbird's release tag, which a fresh mock root only
  # knows after it has resolved. Resolve with the shape of it, read the real
  # tag from the lock, and build with that.
  chown -R mockbuilder:mock "$staged"
  runuser -u mockbuilder -- mock -r "$H/mock.cfg" --calculate-build-dependencies \
    --spec "$spec" --sources "$staged" --resultdir "$H/lock" \
    --define "dist .hum1.bfin${DIST_BUMP:-}"
  test -s "$H/lock/buildroot_lock.json"
  python3 - "$H/lock/buildroot_lock.json" <<'PY'
import json, re, sys
lock = json.load(open(sys.argv[1]))
rpms = lock["buildroot"]["rpms"]
def nevra(r):
    epoch = f"{r['epoch']}:" if r.get("epoch") else ""
    return f"{r['name']}-{epoch}{r['version']}-{r['release']}.{r['arch']}"
open("/work/cache/root", "w").write("".join(sorted(nevra(r) + "\n" for r in rpms)))
tags = sorted({m.group(0) for r in rpms if (m := re.search(r"hum\d+$", r["release"]))})
if not tags:
    sys.exit("no Hummingbird package in the locked root; cannot derive a disttag")
print(f"locked {len(rpms)} packages; Hummingbird tag {tags[0]}")
open("/work/cache/humtag", "w").write(tags[0] + "\n")
PY
  printf ".%s.bfin%s\n" "$(cat /work/cache/humtag)" "${DIST_BUMP:-}" > /work/cache/disttag
  ls "$H"/lock/*.src.rpm
}

materialize() {
  # mock-hermetic-repo downloads over HTTP(S) and saves the bootstrap image;
  # it cannot read file:// URLs, which is where the earlier stages and the
  # published factory live. Split the lock: the network half goes through
  # it, the local half is copied, and one repository is made of both.
  rm -rf "$H/repo"
  python3 - "$H/lock/buildroot_lock.json" "$H/lock/remote.json" "$H/local.txt" <<'PY'
import json, sys
from urllib.parse import unquote, urlparse
lock = json.load(open(sys.argv[1]))
local, remote = [], []
for r in lock["buildroot"]["rpms"]:
    (local if r["url"].startswith("file://") else remote).append(r)
lock["buildroot"]["rpms"] = remote
json.dump(lock, open(sys.argv[2], "w"))
open(sys.argv[3], "w").write("".join(unquote(urlparse(r["url"]).path) + "\n" for r in local))
print(f"{len(remote)} to download, {len(local)} already local")
PY
  mock-hermetic-repo --lockfile "$H/lock/remote.json" --output-repo "$H/repo" 2>&1 | tail -3
  while read -r path; do
    [ -n "$path" ] || continue
    cp "$path" "$H/repo/"
  done < "$H/local.txt"
  createrepo_c -q "$H/repo"
  echo "hermetic repository: $(find "$H/repo" -maxdepth 1 -name "*.rpm" | wc -l) RPMs"
}

build() {
  install_tools
  materialize
  srpm=$(find "$H/lock" -maxdepth 1 -name "*.src.rpm" -print -quit)
  disttag=$(cat /work/cache/disttag)
  # No network from here on: a new network namespace has no interface but
  # loopback, so neither mock nor anything in %build can reach out. mock
  # --hermetic-build itself installs only from the local repository.
  build_offline() {
    rm -rf /work/result/*
    unshare --net -- runuser -u mockbuilder -- mock --hermetic-build "$H/lock/buildroot_lock.json" "$H/repo" \
      --resultdir /work/result \
      --define "dist $disttag" \
      --define "debug_package %{nil}" \
      --define "__debug_install_post %{nil}" \
      "$srpm"
  }
  # A failed %check is retried once, as in the other lanes.
  status=0
  build_offline || status=$?
  if [ "$status" -ne 0 ] && grep -qE "Bad exit status from .*\(%check\)" /work/result/build.log 2>/dev/null; then
    echo "::warning title=flaky %check retry::$PACKAGE failed in %check (exit $status); retrying the build once"
    mkdir -p "/work/reports/check/$PACKAGE/attempt-1"
    cp /work/result/*.log "/work/reports/check/$PACKAGE/attempt-1/" || true
    status=0
    build_offline || status=$?
    if [ "$status" -eq 0 ]; then
      echo "::warning title=flaky %check::$PACKAGE failed %check once and passed on retry"
      printf "%s\n" "$PACKAGE" > /work/reports/flaky-check
    fi
  fi
  if [ "$status" -ne 0 ]; then
    mkdir -p "/work/reports/check/$PACKAGE"
    cp /work/result/*.log "/work/reports/check/$PACKAGE/" 2>/dev/null || true
    chmod -R a+rX /work/reports/check || true
    exit "$status"
  fi
  # mock leaves the SRPM beside the binaries; the repository ships binaries.
  rm -f /work/result/*.src.rpm
  find /work/result -name "*.rpm" -type f -print0 | \
    xargs -0 -r rpm -qp --qf "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n"
  test -n "$(find /work/result -name "*.rpm" -type f -print -quit)"
  chmod -R a+rX /work/result /work/hermetic
}

case "$phase" in
  lock) lock ;;
  build) build ;;
  *) echo "unknown phase $phase" >&2; exit 2 ;;
esac
