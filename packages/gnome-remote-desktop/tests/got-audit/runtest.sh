#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /CoreOS/gnome-remote-desktop/Sanity/got-audit
#   Description: Check pointers in the server process GOT for signs of tampering
#   Author: Gordon Messmer <gordon.messmer@gmail.com>
#

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
    rlPhaseStartSetup
        rlRun "systemctl start --user gnome-remote-desktop-headless"
        rlRun "TestDir=\$(pwd)"
        rlRun "TmpDir=\$(mktemp -d)" 0 "Creating tmp directory"
        rlRun "pushd $TmpDir"
        rlRun "auditfile=\$(mktemp --tmpdir=${TmpDir})"
    rlPhaseEnd

    rlPhaseStartTest "Run GEF got-audit"
        rlRun "SERVICE_PID=\$( systemctl show --property=MainPID --user gnome-remote-desktop-headless.service | cut -f2 -d= )"
        rlRun "echo SERVICE_PID is '$SERVICE_PID'"
        [ -n "$SERVICE_PID" ] || rlFail "No service pid was found"
        rlRun "gdb-gef --pid '$SERVICE_PID' --command='$TestDir'/got-audit.gdb --batch > '$auditfile'"
        # Basic test: ensure that at least one symbol is found in libc.so,
        #  to verify that the report looks plausible.
        rlAssertGrep " : /.*/libc.so" "$auditfile"
        # Ensure the got-audit did not report any errors
        rlAssertNotGrep " :: ERROR" "$auditfile"
        rlRun "cp '$auditfile' '$TMT_TEST_DATA'/got-audit.txt"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "systemctl stop --user gnome-remote-desktop-headless"
        rlRun "popd"
        rlRun "rm -r $TmpDir" 0 "Removing tmp directory"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
