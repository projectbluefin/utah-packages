#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh for iSCSI target/initiator test
#   Description: Set up and Log into an iSCSI target locally.
#   Author: Andy Walsh <awalsh@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2019 Red Hat, Inc.
#
#   This program is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation, either version 2 of
#   the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#   PURPOSE.  See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see http://www.gnu.org/licenses/.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Set up a target IQN to use through the test.
targetIQN=iqn.2019-03.com.redhat.test:testtargetname
targetIP=127.0.0.1

# Minimum size required for loopback device.  Sometimes software (like VDO)
# needs more than ~10G.
minimumSize=15

rlJournalStart

rlPhaseStartSetup
        rlRun "TmpDir=\$(mktemp -d)" 0 "Creating tmp directory"
        rlRun "pushd $TmpDir"

        # Determine the size of the loopback device we're going to use
        # (Free space on rootfs minus 1G)
        loopbackSize=$(($(df --sync --output=avail / | tail -1) * 1024 - 1024*1024*1024))
        if [ ${loopbackSize} -lt $((1024*1024*1024*${minimumSize})) ]; then
          rlDie "Not enough space to create the loopback device"
        fi

        # Create the backing store and then set up the loopback device.
        rlRun "truncate -s ${loopbackSize} $TmpDir/loop0.bin" 0 "Laying out loopfile backing"
        rlRun "losetup /dev/loop0 $TmpDir/loop0.bin" 0 "Creating loopdevice"

        # Check whether we have the iscsi utilities installed, and if we don't,
        # then install them.  If this is being tested in OSCI, I believe that
        # the package will be pre-installed when we get to this point.
        if ! rlCheckRpm iscsi-initiator-utils; then
                yum install -y iscsi-initiator-utils
        fi

        if ! rlCheckRpm targetcli; then
                yum install -y targetcli
        fi

        if [ -f /etc/iscsi/initiatorname.iscsi ]; then
            . /etc/iscsi/initiatorname.iscsi
        else
            echo "InitiatorName=`/usr/sbin/iscsi-iname`" > /etc/iscsi/initiatorname.iscsi
            . /etc/iscsi/initiatorname.iscsi
        fi

        # Make sure the target service is running.
        rlRun "systemctl start target"
rlPhaseEnd

rlPhaseStartTest
        # Gather some system information for debug purposes
        rlRun "uname -a"
rlPhaseEnd

rlPhaseStartTest "Set up target"
    rlRun "targetcli backstores/block create name=loopback_device dev=/dev/loop0"
    rlRun "targetcli iscsi/ create ${targetIQN}"
    rlRun "targetcli iscsi/${targetIQN}/tpg1/acls create ${InitiatorName}"
    rlRun "targetcli iscsi/${targetIQN}/tpg1/luns create lun=100 /backstores/block/loopback_device"
rlPhaseEnd

rlPhaseStartTest "Set up initiator (Log into target)"
    rlRun "iscsiadm --mode discovery --type sendtargets --portal ${targetIP}"
    rlRun "iscsiadm --mode node --target ${targetIQN} -l"

    # Occasionally logging into the iSCSI target and checking for the LUNs
    # being presented and handled by udev seems to falsely cause the next check
    # to fail.  Adding a short sleep seems to fix that.
    sleep 1

    if [ ! -L /dev/disk/by-path/ip-${targetIP}\:3260-iscsi-${targetIQN}-lun-100 ]; then
        rlFail "iSCSI LUN not found"
    fi
rlPhaseEnd

rlPhaseStartCleanup
        # Log out of the target and tear down the iSCSI target configuration
        rlRun "iscsiadm --mode node -u"
        rlRun "targetcli iscsi/ delete ${targetIQN}"
        rlRun "targetcli backstores/block delete loopback_device"

        rlRun "losetup -d /dev/loop0" 0 "Deleting loopdevice"
        rlRun "rm -f $TmpDir/loop0.bin" 0 "Removing loopfile backing"
        rlRun "popd"
        rlRun "rm -r $TmpDir" 0 "Removing tmp directory"
rlPhaseEnd

rlJournalPrintText
rlJournalEnd
