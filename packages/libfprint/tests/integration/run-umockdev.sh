#!/usr/bin/bash
set -u

# Switch into the tests directory
cd /usr/share/installed-tests/libfprint-2 || exit 1

# check if we need to install additional packages
# which is the case if we are on RHEL 8
source /etc/os-release || exit 1

if [[ "$ID" = *"rhel"* ]] && [[ "$VERSION_ID" == *"8"* ]]; then
    dnf config-manager -y --add-repo umockdev.repo
    dnf install -y umockdev-devel python3-gobject-base
    pip3 install python-dbusmock
fi

# Each directory in /usr/share/installed-tests/libfprint-2 is a umockdev based test
# discover them
declare -a TESTS=()
for f in *; do
    test -d $f && TESTS+=( "$f" )
done

export FP_DEVICE_EMULATION=1

# execute all the tests, one by one
RESULT=0
for test in ${TESTS[@]}; do
    echo "$test"
    /usr/libexec/installed-tests/libfprint-2/umockdev-test.py "$test"
    RES=$?
    echo "$test finished with return code $RES"
    echo ""
    # Ignore skipped tests
    if [ $RES -ne 0 -a $RES -ne 77 ]; then
        RESULT=1
    fi
done

exit $RESULT
