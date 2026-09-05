#!/usr/bin/env bash
# Run exactly the CI package build locally, keeping downloads and failure logs.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
usage() {
  echo 'Usage: build-package.sh PACKAGE [--deps-only] [--work DIR] [--engine podman|docker] [--no-fetch] [--keep-container]'
}
if [[ ${1:-} == --help ]]; then usage; exit 0; fi
PACKAGE=${1:?a configured package is required}; shift
[[ $PACKAGE =~ ^[a-zA-Z0-9][a-zA-Z0-9+_.-]*$ ]] || { usage >&2; exit 2; }
work="work/local/$PACKAGE"
engine=${CONTAINER_ENGINE:-podman}
BUILD_MODE=build
fetch=1
keep=0
while (($#)); do
  case $1 in
    --deps-only) BUILD_MODE=deps ;;
    --work) work=${2:?missing work directory}; shift ;;
    --engine) engine=${2:?missing container engine}; shift ;;
    --no-fetch) fetch=0 ;;
    --keep-container) keep=1 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done
RECIPE=$(python3 tools/recipe.py "$PACKAGE" dir)
RECIPE=${RECIPE#packages/}
RPM_DEFINES=$(python3 tools/recipe.py "$PACKAGE" defines)
DIST_BUMP=$(python3 tools/dist_bump.py "$PACKAGE")
PROMISED_SOURCES=$(python3 tools/promised_sources.py)
export PACKAGE RECIPE RPM_DEFINES DIST_BUMP PROMISED_SOURCES BUILD_MODE
mkdir -p "$work"
work=$(realpath "$work")
# Serialize users of a work directory; never race output or cache writers.
exec 9>"$work/.build.lock"
flock -n 9 || { echo "Another build owns $work" >&2; exit 1; }
mkdir -p "$work"/{result,prior,reports,logs,tools,sccache,dnf-cache}
# Keep previous results for inspection, but never count them as this build.
if [[ -n $(find "$work/result" -type f -print -quit) ]]; then
  previous=$(mktemp -d "$work/previous.XXXXXX")
  mv "$work/result" "$previous/result"
  mkdir "$work/result"
fi
if ((fetch)); then
  python3 tools/source_pipeline.py "$PACKAGE" --output "$work/sources" --report-dir "$work/reports"
fi
if [[ $(python3 tools/recipe.py "$PACKAGE" cache) == true && ! -x $work/tools/sccache ]]; then
  version=v0.16.0
  sha256=aec995a83ad3dff3d14b6314e08858b7b73d35ca85a5bcf3d3a9ec07dee35588
  archive="$work/tools/sccache.tar.gz"
  curl --fail --location --retry 3 "https://github.com/mozilla/sccache/releases/download/$version/sccache-$version-x86_64-unknown-linux-musl.tar.gz" --output "$archive"
  printf '%s  %s\n' "$sha256" "$archive" | sha256sum --check --strict
  tar -xzf "$archive" -C "$work/tools" --strip-components=1 "sccache-$version-x86_64-unknown-linux-musl/sccache"
fi
if [[ ! -f $work/tools/sccache.env ]]; then
  printf '%s\n' 'export SCCACHE_DIR=/work/sccache' 'export SCCACHE_CACHE_SIZE=6G' 'export SCCACHE_IDLE_TIMEOUT=0' > "$work/tools/sccache.env"
fi
# Bash reads scripts incrementally. Freeze this copy so editing the checkout
# during a long build cannot splice new text into the running shell program.
cp "$root/tools/build-rpm.sh" "$work/tools/build-rpm.sh"
expected_key=$(python3 tools/build_identity.py "$PACKAGE" --key-only)
container="utah-${PACKAGE}-$(date +%s)-$$"
args=(run --name "$container" --privileged)
((keep)) || args+=(--rm)
log="$work/logs/$(date -u +%Y%m%dT%H%M%SZ)-$BUILD_MODE.log"
echo "Building $PACKAGE ($BUILD_MODE); log: $log"
echo "Container: $container"
started=$SECONDS
set +e
"$engine" "${args[@]}" \
  -e PACKAGE -e RECIPE -e RPM_DEFINES -e DIST_BUMP -e PROMISED_SOURCES -e BUILD_MODE \
  -v "$work:/work:Z" -v "$work/dnf-cache:/var/cache/libdnf5:Z" \
  -v "$root/packages:/packages:ro,z" -v "$root/config:/repos:ro,z" \
  quay.io/fedora/fedora:44 bash /work/tools/build-rpm.sh 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
set -e
echo "Build finished with status $status in $((SECONDS-started))s; log: $log"
if ((keep)); then
  echo "Preserved $container; inspect with: $engine logs $container"
  echo "Copy the build tree with: $engine cp $container:/builddir/rpmbuild $work/rpmbuild"
fi
if ((status == 0)) && [[ $BUILD_MODE == build ]]; then
  if [[ $(python3 tools/build_identity.py "$PACKAGE" --key-only) != "$expected_key" ]]; then
    echo 'Build inputs changed during execution; retained RPMs but refusing to record a reusable identity.' >&2
    exit 1
  fi
  python3 tools/build_identity.py "$PACKAGE" --rpm-dir "$work/result" > "$work/result/$PACKAGE.build-key.json"
fi
exit "$status"
