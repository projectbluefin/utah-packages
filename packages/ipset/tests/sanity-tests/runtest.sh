#!/bin/bash
# SPDX-License-Identifier: LGPL-2.1+
# ~~~
#   runtest.sh of ipset
#   Description: ipset tests.
#
#   Author: Susant Sahani <susant@redhat.com>
#   Copyright (c) 2018 Red Hat, Inc.
# ~~~

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

PACKAGE="ipset"

SERVICE_UNITDIR="/var/run/systemd/system"

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm $PACKAGE
        rlRun "systemctl stop firewalld" 0,5
        rlRun "setenforce 0" 0,1

        rlRun "[ -e /sys/class/net/veth-test ] && ip link del veth-test" 0,1

        rlRun "cp iperf3d.service $SERVICE_UNITDIR"
        rlRun "cp ipset-tests.py /usr/bin/"

        rlRun "systemctl daemon-reload"
    rlPhaseEnd

    rlPhaseStartTest
        rlLog "Starting ipset tests ..."
        rlRun "/usr/bin/python3 /usr/bin/ipset-tests.py"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "rm /usr/bin/ipset-tests.py"
        rlRun "[ -e /sys/class/net/veth-test ] && ip link del veth-test" 0,1

        rlRun "rm $SERVICE_UNITDIR/iperf3d.service"
        rlRun "systemctl daemon-reload"

        rlRun "setenforce 1" 0,1
        rlLog "ipset tests done"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd

rlGetTestState
