#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/bison/Sanity/basic-test
#   Description: bison basic test
#   Author: Edjunior Machado <emachado@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2021 Red Hat, Inc.
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

PACKAGE="bison"

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm $PACKAGE
        rlRun "TmpDir=\$(mktemp -d)" 0 "Creating tmp directory"
        rlRun "cp calc.y $TmpDir"
        rlRun "pushd $TmpDir"
    rlPhaseEnd

    rlPhaseStartTest
        # calc.y from http://git.savannah.gnu.org/cgit/bison.git/tree/examples/c/calc?h=v3.7.5
        rlRun -c "bison --defines --xml --graph=calc.gv -o calc.c calc.y"

        rlAssertExists "calc.c"
        rlAssertGrep "int yylex (void);" calc.c
        rlAssertExists "calc.h"
        rlAssertGrep "int yyparse (void);" calc.h

        rlRun -c "gcc -std=c99 -o calc calc.c"
        rlAssertExists "calc"

        rlAssertEquals "Testing if './calc <<< 1+2*3' is equal '7'" $(./calc <<< 1+2*3) 7
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $TmpDir" 0 "Removing tmp directory"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
