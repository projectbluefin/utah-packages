#!/bin/bash
# Run inside the build root (utah-buildroot:run) by rebuild-rpms.yml prepare.
# For every recipe under /packages, rpmspec reports what it BuildRequires,
# the subpackages it produces, and what it explicitly Provides. One directory
# per package lands in /out: br, names, provides, rc (three exit codes), err.
# tools/build_graph.py turns those into the wave order and the reverse
# dependencies an incremental run drags along.
#
# rpmspec needs the macros a spec uses to evaluate its conditionals, so the
# common macro packages are installed first; a spec that still fails to
# parse is reported by name and simply has no edges.
set -u
dnf -y -q install --skip-unavailable \
  rpm-build redhat-rpm-config python3-rpm-macros pyproject-rpm-macros \
  cargo-rpm-macros golang-rpm-macros meson cmake-rpm-macros fonts-rpm-macros \
  qt6-rpm-macros perl-macros systemd-rpm-macros mingw-filesystem-base \
  ocaml-srpm-macros >/tmp/macros.log 2>&1 || cat /tmp/macros.log >&2

extract() {
  dir=$1
  name=$(basename "$dir")
  spec=$(find "$dir" -maxdepth 1 -name "*.spec" -print -quit)
  [ -n "$spec" ] || return 0
  row=/out/$name
  mkdir -p "$row"
  : > "$row/rc"
  rpmspec -q --buildrequires --define "_sourcedir $dir" "$spec" > "$row/br" 2> "$row/err"
  echo $? >> "$row/rc"
  rpmspec -q --qf "%{NAME}\n" --define "_sourcedir $dir" "$spec" > "$row/names" 2>> "$row/err"
  echo $? >> "$row/rc"
  rpmspec -q --provides --define "_sourcedir $dir" "$spec" > "$row/provides" 2>> "$row/err"
  echo $? >> "$row/rc"
}
export -f extract
find /packages -mindepth 1 -maxdepth 1 -type d -print0 \
  | xargs -0 -r -n 1 -P "$(nproc)" bash -c 'extract "$1"' _
echo "extracted $(find /out -mindepth 1 -maxdepth 1 -type d | wc -l) recipes"
