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


# filename: loop.sh

# USAGE

test x$LXT_MPATH = x || return
LXT_MPATH=1

#source /mnt/tests/kernel/storage/include/bash_modules/lxt/tc.sh

# make sure multipathd is running
get_mpath_disks()
{
    multipathd_running || texit "multipathd is not running" 
    multipathd -k'show maps' 2>/dev/null | grep '^mpath' | awk '{print
"/dev/mapper/" $1}'
    return 0
}

# make sure multipathd is running
get_wwid_of_disk()
{
# we should not use scsi_id or /dev/disk/by-id to get the wwid
# since multipath could replace the white spaces of wwid if 
# having white spaces. we should use 
# multipathd show paths format %w %d 
# to get the wwid

    for dev in `ls /dev/disk/by-id/*`
    do
        if readlink $dev | grep -qw "$disk$" 
        then
            wwid=$(basename $dev | sed 's/^[^-]*-//g')
            break
        fi
    done
    if test X$wwid = X
    then
        wwid=$(/lib/udev/scsi_id --page=0x83 --whitelisted --device=/dev/$disk)
    fi
    echo $wwid

#    multipathd_running || texit "multipathd is not running" 
#    local disk=$1
#    local wwid=$(multipathd show paths format %d,%w | grep "^$disk\s*," | \
#        awk -F, '{ print $2 }' | sed 's/\s//g')
#    echo $wwid
}

get_scsi_id()
{
    dev=$1
    wwid=$(/lib/udev/scsi_id --page=0x83 --whitelisted --device=$dev --replace-whitespace)
    echo $wwid
}

# make sure multipathd is running
get_mpath_disk_by_scsi_device()
{
#    multipathd_running || texit "multipathd is not running" 
    local disk=$1
    local mpath=$(multipathd show paths raw format "%d,%m" | grep "^$disk\s*," \
        | awk -F, '{ print $2 }' | sed 's/\s//g')
    echo $mpath
}

# make sure multipathd is running
get_major_minor_by_scsi_device()
{
    multipathd_running || texit "multipathd is not running" 
    local disk=$1
    local mm=$(multipathd show paths format %d,%D | grep "^$disk\s*," | \
        awk -F, '{ print $2 }' | sed 's/\s//g')
    echo $mm
}

# make sure multipathd is running
get_hcil_by_scsi_device()
{
    multipathd_running || texit "multipathd is not running" 
    local disk=$1
    local hcil=$(multipathd show paths format %d,%i | grep "^$disk\s*," | \
        awk -F, '{ print $2 }' | sed 's/\s//g')
    echo $hcil
}

# make sure multipathd is running
is_mpath()
{
    multipathd_running || texit "multipathd is not running" 
    local mpath=$1
    multipathd show maps format %n | grep -w "^$mpath" &> /dev/null
}

multipathd_running()
{
    pidof multipathd &> /dev/null && return 0
    return 1
}

# will set find_multipaths no and start multipathd
setup_multipath()
{
    trun "rpm -q device-mapper-multipath || yum install -y device-mapper-multipath" || texit "fail to install multipath"
    test -f /etc/multipath.conf && cp /etc/multipath.conf /etc/multipath.conf.storage_qe 
    trun "mpathconf --enable --find_multipaths n --with_multipathd y" 
    trun "multipath -r"
}

clear_multipath()
{
    tlog "disable multipath and remove the mpath devices"
    tlog "revert back the multipath.conf if has backup file"
    test -f /etc/multipath.conf.storage_qe && cp /etc/multipath.conf.storage_qe /etc/multipath.conf &>/dev/null
    ( multipath -q && multipath -F ) &>/dev/null
    stop_multipathd
}

get_unused_mpath()
{
    multipathd_running &>/dev/null || texit "multipathd is not running" 
    rootdisk=$(get_root_disk)
    rootmpath=$(get_mpath_disk_by_scsi_device $rootdisk)
    if is_null $rootmpath; then
        $maps=$(multipathd show maps format "%n" | grep -v name)
    else 
        $maps=$(multipathd show maps format "%n" | grep -v name | grep -v $rootmpath)
    fi
    
    echo $maps
}

stop_multipathd() {
    tlog "stop multipathd"
    ( pidof multipathd && service multipathd stop || pkill multipathd ) &>/dev/null
}
