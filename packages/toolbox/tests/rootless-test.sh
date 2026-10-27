#!/usr/bin/env bash

set -exo pipefail

uname -r

loginctl enable-linger "$ROOTLESS_USER"

rpm -q containers-common-extra podman toolbox

su --whitelist-environment=$(cat ./tmt-envvars | tr '\n' ',') - "$ROOTLESS_USER" -c "whoami && cd /usr/share/toolbox/test/system && bats ."
