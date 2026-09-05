#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /CoreOS/setools/Regression/bz1820078-The-setools-package-doesn-t-install-any-tools
#   Description: Make sure setools requires setools-console and setools-gui
#   Author: Vit Mojzis <vmojzis@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2020 Red Hat, Inc.
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
        rlRun "dnf -y remove ${PACKAGE} ${PACKAGE}-gui ${PACKAGE}-console"
        OUTPUT_FILE=`mktemp`
    rlPhaseEnd

    rlPhaseStartTest "bz#1820078"
        rlRun "dnf -y install ${PACKAGE}" 0
        rlAssertRpm "${PACKAGE}-gui"
        rlAssertRpm "${PACKAGE}-console"
        # make sure that setools-* packages do not require setools
        rlRun "rpm -q --whatrequires ${PACKAGE} >& ${OUTPUT_FILE}" 0,1
        rlRun "grep -i \"${PACKAGE}-\" ${OUTPUT_FILE}" 1
        if [ $? -ne 1 ]; then rlRun "cat \"${OUTPUT_FILE}\""; fi
    rlPhaseEnd

    rlPhaseStartCleanup
        rm -f ${OUTPUT_FILE}
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
