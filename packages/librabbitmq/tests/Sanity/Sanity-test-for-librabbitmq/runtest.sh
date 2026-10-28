#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /CoreOS/librabbitmq/Sanity/Sanity-test-for-librabbitmq
#   Description: Tests the sanity
#   Author: Than Ngo <than@redhat.com>, Brock Organ <borgan@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2019 Red Hat, Inc.
#
#   This copyrighted material is made available to anyone wishing
#   to use, modify, copy, or redistribute it subject to the terms
#   and conditions of the GNU General Public License version 2.
#
#   This program is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#   PURPOSE. See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public
#   License along with this program; if not, write to the Free
#   Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
#   Boston, MA 02110-1301, USA.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PACKAGES="librabbitmq librabbitmq-devel"

# source the test script helpers
. /usr/share/beakerlib/beakerlib.sh || exit 1

rlJournalStart
        rlPhaseStartSetup
                for p in $PACKAGES ; do
                        rlAssertRpm $p
                done
                rlRun "TmpDir=\$(mktemp -d)" 0 "Creating tmp directory"
                rlRun "pushd $TmpDir"
        rlPhaseEnd

        rlPhaseStartTest "Smoke, sanity and function tests"
                for o in $(ls -1 /usr/lib64/librabbitmq.so*) ; do 
                        rlRun "ldd $o" 0 "validate the shared objects"
                        rlRun "objdump -T $o" 0 "validate the shared objects"
                done
                rlRun "head /usr/share/doc/librabbitmq-devel/README.md" 0 "correct form for doc file"
                rlRun "head /usr/share/licenses/librabbitmq/LICENSE" 0 "correct form for doc file"
        rlPhaseEnd

        rlPhaseStartCleanup
                rlRun "popd"
                rlRun "rm -fr $TmpDir" 0 "Removing tmp directory"
        rlPhaseEnd
rlJournalPrintText
rlJournalEnd
