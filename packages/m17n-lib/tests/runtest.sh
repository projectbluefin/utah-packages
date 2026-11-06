#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

NAME=m17n-lib

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm ${NAME}
        rlAssertRpm ${NAME}-devel
        rlAssertRpm glibc-locale-source
        rlShowPackageVersion ${NAME}
        rlRun -t -l "VERSION=$(rpm -q ${NAME} --queryformat='%{version}')" 0 "Get VERSION"
        FEDORA_VERSION=$(rlGetDistroRelease)
        rlLog "FEDORA_VERSION=${DISTRO_RELEASE}"
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "cp hello.txt old.png $tmp" 0 "Copy files needed for tests"
        rlRun "pushd $tmp"
        rlFetchSrcForInstalled "${NAME}"
        rlRun "rpm --define '_topdir $tmp' -i *src.rpm"
        rlRun -t -l "mkdir BUILD" 0 "Creating BUILD directory"
        rlRun -t -l "rpmbuild --noclean --nodeps --define '_topdir $tmp' -bp $tmp/SPECS/*spec"
        if [ -d BUILD/${NAME}-${VERSION}-build ]; then
            rlRun -t -l "pushd BUILD/${NAME}-${VERSION}-build/${NAME}-${VERSION}"
        else
            rlRun -t -l "pushd BUILD/${NAME}-${VERSION}"
        fi
        rlRun "set -o pipefail"
        rlRun -t -l "./bootstrap.sh"
        rlRun -t -l "./configure --prefix=/usr"
        rlRun -t -l "make check"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "pushd $tmp"
        rlGetTestState
        rlLog "Number of failed asserts so far: ${ECODE}"
        rlRun -t -l "OLD_SIZE=$(stat -c \"%s\" old.png)" \
              0 "Get size of old.png"
        rlLog "Old size is ${OLD_SIZE}"
        rlRun -t -l "m17n-dump hello.txt" \
              0 "Create a new png"
        rlFileSubmit hello.txt.png
        rlRun -t -l "NEW_SIZE=$(stat -c \"%s\" hello.txt.png)" \
              0 "Get size of hello.txt.png"
        rlLog "New size is ${NEW_SIZE}"
        rlRun -t -l "file old.png hello.txt.png" \
              0 "Log output of file command"
        rlRun -t -l "echo $(fc-match)" \
              0 "Show which font was used"
        rlAssertGreater "New size should be greater than 1000" ${NEW_SIZE} 1000
        rlGetTestState
        rlLog "Number of failed asserts so far: ${ECODE}"
        rlRun "popd" 0
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $tmp" 0 "Remove tmp directory"
    rlPhaseEnd
rlJournalEnd
