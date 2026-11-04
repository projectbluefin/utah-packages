#!/bin/bash
# Only the package this job built may leave it.
#
# publish_gate.py replaces published RPMs by the source name it reads from
# each uploaded binary's %{SOURCERPM} header, and the artifact a binary came
# from is forgotten on download (merge-multiple). Nothing in a lane checked
# that header against the package the job was asked to build. %build and
# %check run as the build user, and that user can write into the directory
# the lane uploads: mock copies out every *.rpm in RPMS/, and the container
# lane's _rpmdir is owned by it. A crafted RPM planted there with another
# package's %{SOURCERPM} would have publish delete that package and ship the
# plant in its place, signed.
#
# The name alone is compared: the hermetic lock SRPM is built with the
# placeholder disttag and the binaries with the resolved one, so their
# releases differ, and the name is the key publish replaces by.
#
#   check_rpm_source.sh <expected source name> <result dir>
set -euo pipefail

expected=$1
result=$2
test -n "$expected"

# The same reduction publish-repository.yml applies to %{SOURCERPM}:
# name-version-release.src.rpm -> name. Assigned, not read through a process
# substitution, so an rpm that cannot read a file fails this script instead
# of shortening the list.
sources=$(
  find "$result" -name '*.rpm' ! -name '*.src.rpm' -type f -print0 \
    | sort -z \
    | xargs -0 -r rpm -qp --nosignature --qf '%{SOURCERPM}\n' \
    | sed -e 's/-[^-]*-[^-]*\.src\.rpm$//' \
    | sort -u
)
offenders=()
while IFS= read -r source; do
  [ -z "$source" ] && continue
  [ "$source" = "$expected" ] || offenders+=("$source")
done <<<"$sources"
if [ "${#offenders[@]}" -gt 0 ]; then
  echo "::error title=foreign RPM in build output::$expected produced binaries claiming source package(s): ${offenders[*]}" >&2
  find "$result" -name '*.rpm' ! -name '*.src.rpm' -type f -print0 \
    | xargs -0 -r rpm -qp --nosignature --qf '  %{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}  from  %{SOURCERPM}\n' >&2
  exit 1
fi
echo "every binary RPM comes from source package $expected"
