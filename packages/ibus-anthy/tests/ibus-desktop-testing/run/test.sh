#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
    rlPhaseStartTest
        rlRun -t "/usr/bin/ibus-desktop-testing-runner --runner gnome --tests ibus-anthy --no-graphics --lang ja_JP.UTF-8"
    rlPhaseEnd
    rlPhaseStartCleanup
        rlRun "echo test-suite.log"
        rlRun "cat test-suite.log"
        rlRun "echo /export/home/itestuser/test-autostart.log"
        rlRun "cat /export/home/itestuser/test-autostart.log"
    rlPhaseEnd
rlJournalEnd
