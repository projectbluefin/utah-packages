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

# Author: LiLin <lilin@redhat.com>
source ../include/tc.sh || exit 200

cleanup()
{
    sleep 5
    udevadm settle
    trun "multipath -DF"
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

tlog "running $0"
rpm -q device-mapper-multipath || dnf install -y device-mapper-multipath
trun "multipathd disablequeueing maps"
cleanup
trun "service multipathd stop"
trun "rm -f /etc/multipath.conf"
trun "mpathconf --enable"
trun "modprobe scsi_debug vpd_use_hostno=0 add_host=2 opts=2"
sleep 5
trun "multipath"
sleep 5
trun "multipath -l"
mpathdev=`multipath -l | grep scsi_debug | awk '{print $1}' | head -1`
assert "[[ -n \"$mpathdev\" ]]"
before_active=`multipath -l $mpathdev | grep "active undef" | wc -l`
tlog "before active = ${before_active}"

IO_error=`dd if=/dev/zero of=/dev/mapper/$mpathdev bs=1024 seek=2330 count=10 2>&1 | grep -o "Input/output error" `
assert "[[ -n \"$IO_error\" ]]"
after_active=`multipath -l $mpathdev | grep "active undef" | wc -l`
tlog "after active = ${after_active}"
assert "[[ \"$before_active\" -eq \"$after_active\" ]]"
cleanup
tend
