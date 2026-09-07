#!/usr/bin/env bash
# Give one local build the earlier-stage RPMs its CI lane would have had.
#
# tools/build-rpm.sh turns /work/prior into a [stages] repository and excludes
# every name it finds there from Fedora, which is how a late-stage package
# links what the factory just built rather than what Fedora happens to ship.
# In CI that directory is seeded from the `:building` accumulator. A local
# `just build` has nothing there at all, so a package whose dependencies moved
# soname resolves against Fedora and produces RPMs the runtime cannot install:
# ffmpeg linked libvpx.so.9 and liboapv.so.2 when the factory had already
# published so.12 and so.3.
#
# Debuginfo and debugsource are skipped. No BuildRequires ever names one, and
# they are more than half the bytes.
set -euo pipefail

usage() {
  echo "Usage: $0 PACKAGE INPUT [INPUT ...]" >&2
  echo "An INPUT is either a repository image reference or a directory of RPMs." >&2
}

package=${1:-}
shift || true
[[ -n $package && $# -gt 0 ]] || { usage; exit 2; }
[[ $package =~ ^[a-zA-Z0-9][a-zA-Z0-9+_.-]*$ ]] || { usage; exit 2; }

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
prior="${FACTORY_WORK:-work}/local/$package/prior"
mkdir -p "$prior"

copy_rpms() {
  # Later inputs win, so a locally rebuilt RPM replaces the published copy of
  # the same name -- the same ordering the composed repository uses.
  local from=$1
  find "$from" -name '*.rpm' -type f \
    ! -name '*debuginfo*' ! -name '*debugsource*' \
    -exec cp -f -t "$prior" {} +
}

for source in "$@"; do
  if [[ -d $source ]]; then
    copy_rpms "$source"
    continue
  fi
  if ! podman image exists "$source"; then
    podman pull "$source"
  fi
  # Mount the image rather than copying it out: a repository image is several
  # gigabytes and only a fraction of it is wanted here.
  podman run --rm \
    --mount "type=image,source=$source,destination=/input" \
    -v "$root/$prior:/prior:Z" \
    quay.io/fedora/fedora:44 \
    find /input -name '*.rpm' -type f \
      ! -name '*debuginfo*' ! -name '*debugsource*' \
      -exec cp -f -t /prior {} +
done

count=$(find "$prior" -name '*.rpm' -type f | wc -l)
echo "seeded $prior with $count RPMs"
