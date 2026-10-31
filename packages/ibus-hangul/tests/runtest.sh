#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

NAME=ibus-hangul
XFWB_SCRIPT=$(pwd)/xwfb-script.sh

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm ${NAME}
        rlAssertRpm gnome-desktop-testing
        rlAssertRpm gnome-shell-extension-no-overview
        rlAssertBinaryOrigin gnome-desktop-testing-runner gnome-desktop-testing
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "pushd $tmp"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun -t -l "pushd /usr/libexec/installed-tests/ibus-hangul" \
              0 "Change to directory of installed tests"
        if [ -z "${DISPLAY:-}" ]; then
            rlLogInfo "DISPLAY is empty or unset."
            rlLogInfo "Therefore, use xfwb-run to run the graphical ibus-hangul test:"
            rlRun -t -s "xwfb-run -c mutter -e $tmp/xwfb-run.log -n 99 $XFWB_SCRIPT" \
                  0 "Running ibus-hangul test in xfwb-run"
            echo "==== START of `cat ${rlRun_LOG}`: log of xwfb-run ===="
            cat ${rlRun_LOG}
            echo "==== END of `cat ${rlRun_LOG}`: log of xwfb-run ===="
            rlAssertNotGrep FAIL ${rlRun_LOG}
            rlGetTestState
            rlLog "Total number of failed asserts: ${ECODE}"
            rlFileSubmit ${rlRun_LOG}
            rlFileSubmit xwfb-run.log
        fi
        rlGetTestState
        rlLog "Total number of failed asserts: ${ECODE}"
        rlRun "popd" 0
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $tmp" 0 "Remove tmp directory"
    rlPhaseEnd
rlJournalEnd
