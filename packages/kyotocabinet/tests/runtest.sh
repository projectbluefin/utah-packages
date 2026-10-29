#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
    rlPhaseStartSetup
        rlShowPackageVersion kyotocabinet
        rlRun -t -l "VERSION=$(rpm -q kyotocabinet --queryformat='%{version}')" 0 "Get VERSION"
        FEDORA_VERSION=$(rlGetDistroRelease)
        rlLog "FEDORA_VERSION=${DISTRO_RELEASE}"
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "pushd $tmp"
        rlFetchSrcForInstalled "kyotocabinet"
        rlRun "rpm --define '_topdir $tmp' -i *src.rpm"
        rlRun -t -l "mkdir BUILD" 0 "Creating BUILD directory"
        rlRun -t -l "rpmbuild --noclean --nodeps --define '_topdir $tmp' -bp $tmp/SPECS/*spec"
        if [ -d BUILD/kyotocabinet-${VERSION}-build ]; then
            rlRun -t -l "pushd BUILD/kyotocabinet-${VERSION}-build/kyotocabinet-${VERSION}"
        else
            rlRun -t -l "pushd BUILD/kyotocabinet-${VERSION}"
        fi
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "set -o pipefail"
        rlRun -t -l "NOCONFIGURE=1 gnome-autogen.sh"
        rlRun -t -l "./configure --disable-opt --enable-lzo --enable-lzma"
        rlRun -t -l "make"
        rlRun -t -l "make check"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd; popd"
        rlRun "rm -r $tmp" 0 "Remove tmp directory"
    rlPhaseEnd
rlJournalEnd
