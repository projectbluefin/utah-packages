#!/usr/bin/bash
set -u

# check if we need to install additional packages
# which is the case if we are on RHEL 8
source /etc/os-release || exit 1

if [[ "$ID" = *"rhel"* ]] && [[ "$VERSION_ID" == *"8"* ]]; then
    pip3 install python-dbusmock
fi

# Switch into the tests directory
cd ../fprintd-*/tests || exit 1

# Run actual test
exec python3 "$@"
