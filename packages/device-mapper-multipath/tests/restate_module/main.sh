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
tlog "running $0"

cleanup ()
{
    trun "multipathd disablequeueing maps"
    trun "service multipathd stop"
    sleep 5
    trun "udevadm settle"
    trun "multipath -F"
    sleep 5
    trun "modprobe -r scsi_debug"
}

assert ()
{
    local cmd="$*"
    _trun_ "$cmd" 0
    if test $? -eq 0; then
        tpass_ "$cmd" ;
    else
        tfail_ "$cmd" ;
	cleanup ;
        tend ;
    fi
}

rpm -q device-mapper-multipath || yum install -y device-mapper-multipath
tlog "device-mapper-multipath is installed"
# cleanup existing devices
trun "rm /etc/multipath.conf"
trun "mpathconf --enable --with_module y --option max_polling_interval:10"
trun "mpathconf --option detect_pgpolicy_use_tpg:yes"
trun "service multipathd stop"
trun "multipath -F"
sleep 5
trun "modprobe -r scsi_debug"

#trun "service multipathd restart"
trun "service multipathd start"
trun "modprobe scsi_debug vpd_use_hostno=0 add_host=2"
sleep 5
mpathdev=`multipath -l | grep scsi_debug | awk '{print $1}' | head -1`
tlog "using multipathd device ${mpathdev}"
trun "multipath -ll ${mpathdev}"
pathcount=`multipathd show paths raw format "%m %t" | grep ${mpathdev} | grep "active" | wc -l`
tlog "Checking if active path count equals 2"
assert "[[ $pathcount -eq 2 ]]"

tlog "offline one path device"
pathname=`multipathd show paths raw format "%d %m %p" | grep ${mpathdev} | sort -k 3n | head -1 | awk '{print $1}'`
tlog "path to offline: ${pathname}"
trun "echo 'offline' > /sys/block/${pathname}/device/state"
tlog "waiting for multipathd to fail path"
sleep 15
trun "multipathd show paths"
pathcount=`multipathd show paths raw format "%m %t" | grep ${mpathdev} | grep "active" | wc -l`
tlog "Checking if active path count equals 1"
assert "[[ $pathcount -eq 1 ]]"

tlog "restore ${pathname}"
trun "echo 'running' > /sys/block/${pathname}/device/state"
sleep 10
#verified
multipathd_state=`service multipathd status | grep "Active: active (running)" | wc -l`
tlog "Checking if multipathd service is running"
assert "[[ $multipathd_state -eq 1 ]]"
pathcount=`multipathd show paths raw format "%m %t" | grep ${mpathdev} | grep "active" | wc -l`
tlog "Checking if active path count equals 2"
assert "[[ $pathcount -eq 2 ]]"
path_state=`multipathd show paths raw format "%d %t %T %o" | grep ${pathname} | grep "active ready running" | wc -l`
tlog "Checking state of ${pathname}"
assert "[[ $path_state -eq 1 ]]"

cleanup
tend
