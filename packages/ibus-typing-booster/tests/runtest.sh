#!/bin/bash
. /usr/share/beakerlib/beakerlib.sh || exit 1

NAME=ibus-typing-booster
XFWB_SCRIPT=$(pwd)/xwfb-script.sh

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm ibus-typing-booster
        rlAssertRpm gnome-desktop-testing
        rlAssertRpm gnome-shell-extension-no-overview
        rlAssertBinaryOrigin gnome-desktop-testing-runner gnome-desktop-testing
        rlRun "tmp=\$(mktemp -d)" 0 "Create tmp directory"
        rlRun "pushd $tmp"
    rlPhaseEnd

#    rlPhaseStartTest
#        rlRun -t -l "ibus-desktop-testing-runner \
#          --no-graphics \
#          --runner=gnome \
#          --timeout=1500 \
#          --tests=${NAME} \
#          --output=${NAME}.log \
#          --result=test.log \
#          " 0 "Running ibus-typing-booster tests"
#        echo "==== ${NAME}.log: ===="
#        cat ${NAME}.log
#        echo "==== EOF ${NAME}.log: ===="
#        echo "==== test.log ===="
#        cat test.log
#        echo "==== EOF test.log: ===="
#        rlAssertNotGrep FAIL test.log
#        rlFileSubmit ibus-typing-booster.log
#        rlFileSubmit test.log
#    rlPhaseEnd

    rlPhaseStartTest
        rlRun -t -l "pushd /usr/libexec/installed-tests/ibus-typing-booster" \
              0 "Change to directory of installed tests"
        TEST_FILES="test_*.py"
        # When running locally with `tmt run -vvv -a provision -h local`
        # DISPLAY might be set here and XDG_SESSION_TYPE might be "x11".
        # In that case, all tests, including the graphical test_0_gtk.py
        # will run fine in this "for" loop. Otherwise the graphical
        # test_0_gtk.py in this for loop will be skipped:
        for test_file in ${TEST_FILES}
        do
            rlRun -t -s "./run_tests ${test_file}" 0
            echo "==== START of `cat ${rlRun_LOG}`: log of ${test_file} ===="
            cat ${rlRun_LOG}
            echo "==== END of `cat ${rlRun_LOG}`: log of ${test_file} ===="
            rlAssertNotGrep FAIL ${rlRun_LOG}
            rlGetTestState
            rlLog "Number of failed asserts so far: ${ECODE}"
            rlFileSubmit ${rlRun_LOG}
        done
        if [ -z "${DISPLAY:-}" ]; then
            rlLogInfo "DISPLAY is empty or unset."
            rlLogInfo "Therefore, use xfwb-run to run the graphical test_0_gtk.py:"
            rlRun -t -s "xwfb-run -c mutter -e $tmp/xwfb-run.log -n 99 $XFWB_SCRIPT" \
                  0 "Running test_0_gtk.py in xfwb-run"
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
