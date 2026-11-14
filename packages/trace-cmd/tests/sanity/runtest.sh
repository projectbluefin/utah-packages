#!/bin/bash
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Description: Basic sanity test for trace-cmd
#   Author: Ziqian SUN (Zamir) <zsun@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# Copyright (c) 2018 Red Hat, Inc. All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Include rhts environment
. /usr/bin/rhts-environment.sh
. /usr/share/beakerlib/beakerlib.sh

if ! mount | grep -q debugfs ; then
    mount -t debugfs nodev /sys/kernel/debug
fi

trace-cmd reset
rlJournalStart
    for TRACER in $(cat /sys/kernel/debug/tracing/available_tracers) ; do
        rlPhaseStartTest "Enable ${TRACER} using trace-cmd"
            rlRun "trace-cmd start -p ${TRACER}"
            rlAssertEquals "Check current tracer" "$(cat /sys/kernel/debug/tracing/current_tracer)" "${TRACER}"
            rlAssertEquals "Check tracing status" "$(cat /sys/kernel/debug/tracing/tracing_on)" "1"
            rlRun "trace-cmd stop"
            rlAssertEquals "Check tracing status" "$(cat /sys/kernel/debug/tracing/tracing_on)" "0"
            rlRun "trace-cmd reset"
        rlPhaseEnd
        if [[ "${TRACER}" == "function" ]]; then
            rlPhaseStartTest "Test trace-cmd show"
                rlRun "trace-cmd start -p ${TRACER}"
                rlWatchdog "trace-cmd show | grep -v '^#' > trace-cmd-show-function.log" 5 INT
                rlAssertGreater "At least one line of trace data" $(cat trace-cmd-show-function.log | wc -l) 1
                rlRun "trace-cmd stop"
                rlRun "trace-cmd reset"
                rlFileSubmit trace-cmd-show-function.log
                rm -f trace-cmd-show-function.log
            rlPhaseEnd
        fi
    done
rlJournalEnd
