#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
    rlPhaseStartSetup
        rlShowPackageVersion opencc
        rlRun -t -l "VERSION=$(rpm -q opencc --queryformat='%{version}')" 0 "Get VERSION"
        FEDORA_VERSION=$(rlGetDistroRelease)
        rlLog "FEDORA_VERSION=${DISTRO_RELEASE}"
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "pushd $tmp"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "set -o pipefail"
        rlRun "echo '测试'>input.txt" 0 "Generate input.txt"
        rlRun "opencc -i input.txt -o output.txt" 0 "Run opencc tool"
        rlRun "grep '測試' output.txt" 0 "Check output.txt"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $tmp" 0 "Remove tmp directory"
    rlPhaseEnd
rlJournalEnd
