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
    local exit_status=1
    
    Multipath_installation || Fail "fail to install device-mapper-multipath"
    Print_kernel_info
    Print_multipath_pkginfo
    
    local stdout stderr

    Log "create the multipathed disk via scsi_debug"
    _init || Fail "fail to create the multipathed disk"
    Cmd "multipath -ll"
    Log "fail the multipathed disk"
    Cmd "echo 0 > /sys/bus/pseudo/drivers/scsi_debug/max_luns"
    Log "check the output of multipath  & multipath -ll $mpath"
#will print the unexpected output if the issue is still there
#multipath to scan disks
    Cmd "multipath ; multipath -ll $mpath" 
    stdout=${_STDOUT}
    stderr=${_STDERR}
#mark as pass if no scsi_id error message observered
    echo $stdout $stderr | grep '/lib/udev/scsi_id exitted' 1>/dev/null || exit_status=0 
    Cmd "echo 2 > /sys/bus/pseudo/drivers/scsi_debug/max_luns"
    Cmd "multipath ; multipath -ll $mpath" 
    _destroy  

    return $exit_status
}

main || Fail "still print the message: scsi_id exitted while scanning the failed path"

Pass

