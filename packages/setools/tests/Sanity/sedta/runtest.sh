#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /CoreOS/setools/Sanity/sedta
#   Description: Does sedta work as expected? Does it support all features?
#   Author: Milos Malik <mmalik@redhat.com>
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

PACKAGE="setools"

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm ${PACKAGE}-console-analyses
        OUTPUT_FILE=`mktemp`
        rlRun "semodule -i testpolicy.cil"
        rlRun "semodule -l | grep testpolicy"
    rlPhaseEnd

    rlPhaseStartTest "invalid values"
        rlRun "sedta -s unknown_t >& ${OUTPUT_FILE}" 1
        rlRun "grep -i 'not a valid type' ${OUTPUT_FILE}"
        rlRun "sedta -s apmd_t -t unknown_t -S >& ${OUTPUT_FILE}" 1
        rlRun "grep -i 'not a valid type' ${OUTPUT_FILE}"
        rlRun "sedta -s unknown_t -p /etc/selinux/unknown/policy/policy.31 >& ${OUTPUT_FILE}" 1
        rlRun "grep -i 'no such file or directory' ${OUTPUT_FILE}"
        rlRun "sedta -s apmd_t -t var_lib_t -A -1 >& ${OUTPUT_FILE}" 1
        rlRun "grep -i 'must be positive' ${OUTPUT_FILE}"
        rlRun "sedta -s xyz_t >& ${OUTPUT_FILE}"
        rlRun "grep -i '^0.*transition.*found' ${OUTPUT_FILE}"
    rlPhaseEnd

    rlPhaseStartTest "valid values"
        # transitivity
        rlRun "sedta -s first_t -t second_t -S >& ${OUTPUT_FILE}"
        rlRun "grep -i '^1 domain transition path.*found' ${OUTPUT_FILE}"
        rlRun "sedta -s second_t -t third_t -S >& ${OUTPUT_FILE}"
        rlRun "grep -i '^1 domain transition path.*found' ${OUTPUT_FILE}"
        rlRun "sedta -s first_t -t third_t -S >& ${OUTPUT_FILE}"
        rlRun "grep -i '^1 domain transition path.*found' ${OUTPUT_FILE}"
        # reflexivity
        rlRun "sedta -s first_t -t first_t -S >& ${OUTPUT_FILE}"
        rlRun "grep -i '^1 domain transition path.*found' ${OUTPUT_FILE}"
        rlRun "sedta -s second_t -t second_t -S >& ${OUTPUT_FILE}"
        rlRun "grep -i '^1 domain transition path.*found' ${OUTPUT_FILE}"
        rlRun "sedta -s third_t -t third_t -S >& ${OUTPUT_FILE}"
        rlRun "grep -i '^1 domain transition path.*found' ${OUTPUT_FILE}"
        # path is longer than limit
        rlRun "sedta -s first_t -t third_t -A 1 >& ${OUTPUT_FILE}"
        rlRun "grep -i '^0 domain transition path.*found' ${OUTPUT_FILE}"
        # non-existent relation
        rlRun "sedta -s first_t -t third_t -S -r >& ${OUTPUT_FILE}"
        rlRun "grep -i '^0 domain transition path.*found' ${OUTPUT_FILE}"
        # non-existent relation
        rlRun "sedta -s third_t -t first_t -S >& ${OUTPUT_FILE}"
        rlRun "grep -i '^0 domain transition path.*found' ${OUTPUT_FILE}"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "semodule -r testpolicy"
        rlRun "semodule -l | grep testpolicy" 1
        rm -f ${OUTPUT_FILE}
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd

