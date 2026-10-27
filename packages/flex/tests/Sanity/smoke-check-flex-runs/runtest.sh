#!/usr/bin/env bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/flex/Sanity/smoke-check-flex-runs
#   Description: Show your version. Build a one-file project.
#   Author: Vaclav Kadlcik <vkadlcik@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2015 Red Hat, Inc.
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

PACKAGE="flex"

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm $PACKAGE
        yum -y install bison gcc
        rlRun "TmpDir=\$(mktemp -d)" 0 "Creating tmp directory"
        rlRun "cp count_chars_and_lines.l calc-lexer.l calc-grammar.y expected_calc_output.txt $TmpDir"
        rlRun "pushd $TmpDir"
    rlPhaseEnd

    rlPhaseStartTest 'Show version'

        rlRun -t -s 'flex -V'
        rlAssertNotGrep '^STDERR:' $rlRun_LOG
        rlAssertGrep '^STDOUT: flex [0-9]' $rlRun_LOG

    rlPhaseEnd

    rlPhaseStartTest 'Flex works standalone'

        rlRun 'flex -o count_chars_and_lines.c count_chars_and_lines.l'
        rlRun 'gcc -o count_chars_and_lines count_chars_and_lines.c'
        rlAssertExists 'count_chars_and_lines'
        rlRun -t -s 'echo -e "nazdar\nbazar" | ./count_chars_and_lines'
        rlAssertNotGrep '^STDERR:' $rlRun_LOG
        rlAssertGrep '^STDOUT: chars: 13$' $rlRun_LOG
        rlAssertGrep '^STDOUT: lines: 2$' $rlRun_LOG

    rlPhaseEnd

    rlPhaseStartTest 'Flex works with Bison'

        rlRun 'bison -d calc-grammar.y'
        rlRun 'flex calc-lexer.l'
        rlRun 'gcc -o calc calc-grammar.tab.c lex.yy.c'
        rlAssertExists 'calc'
        rlRun -t -s 'echo -e "1 + 2 * 3\n1 - 666 / 3\n42" | ./calc'
        rlAssertNotDiffer expected_calc_output.txt $rlRun_LOG

    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "popd"
        rlRun "rm -r $TmpDir" 0 "Removing tmp directory"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
