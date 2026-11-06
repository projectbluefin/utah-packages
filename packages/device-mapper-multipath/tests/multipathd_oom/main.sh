#!/bin/bash

# Copyright (c) 2016 Red Hat, Inc.
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

# Author: Lin Li   <lilin@redhat.com>


source ../include/ec.sh || exit 200

function main (){
    Multipath_installation || Fail "fail to install device-mapper-multipath"
    Print_kernel_info
    Print_multipath_pkginfo

    local exit_status=0
    local oom_adj oom_score_adj oom_score lock_file

#    Log "do not kill the mingetty and sshd by oom_killer"
#    Cmd "pidof mingetty"
#    local ttys=$_STDOUT
#    Cmd "pidof sshd"
#    ttys="$ttys $_STDOUT"
#    Cmd "for t in $ttys; do echo -1000 > /proc/\$t/oom_score_adj; done"

    Multipathd_start || Fail "fail to start multipathd"
    local pid=$(pidof multipathd)
#this bug is for 6.2 has oom_score_adj
    Cmd "[ -r /proc/$pid/oom_score_adj ]" || Fail "oom_score_adj not existing, do NOT support this kernel version"

    Cmd "cat /proc/$pid/oom_adj" 
    oom_adj=$_STDOUT
    Cmd "cat /proc/$pid/oom_score_adj" 
    oom_score_adj=$_STDOUT
    Cmd "cat /proc/$pid/oom_score" 
    oom_score=$_STDOUT

#should set the oom_adj to -17 and oom_score_adj to -1000 so that multipathd will never be selected to kill by oom_killer
    [ X"$oom_adj" = X"-17" ] || Fail "oom_adj is not -17"
    [ X"$oom_score_adj" = X"-1000" ] || Fail "oom_score_adj is not -1000"

# we don't need to test the real oom action. just check the oom_adj
    Multipathd_stop || Fail "fail to stop multipathd"
    return $exit_status
}

main || Fail "multipathd invokes oom_killer"

Pass
