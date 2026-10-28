#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /CoreOS/time/Sanity/maximum_RSS
#   Description: check if RSS usage is measured reasonable (in bug, reported value vas 4-times bigger)
#   Author: Ondrej Ptak <optak@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2015 Red Hat, Inc.
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

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

PACKAGES=${PACKAGES:-"time"}

rlJournalStart
    rlPhaseStartTest
       supposed_RSS=412024
       rlLogInfo "RSS usage of given script is suppose to be about $supposed_RSS kB"
       rlRun "maxRSS=$(/usr/bin/time -f %M perl -e '"x" x 400 x 1024 x 1024' 2>&1)" 0 "Measuring RSS usage"
       rlAssertGreater "RSS max usage should be < 450000" 450000 $maxRSS 
       rlAssertGreater "RSS max usage should be > 400000" $maxRSS 400000
       echo "$maxRSS/$supposed_RSS*100"
       coef=`echo "$maxRSS*100/$supposed_RSS" | bc`
       rlLogInfo "RSS value is $coef % of expected value"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
