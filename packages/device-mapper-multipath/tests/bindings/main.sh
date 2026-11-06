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

#set -x
source ../include/tc.sh || exit 200
tlog "running $0"

cleanup ()
{
    local retries
    if pidof multipathd; then
        tlog "stopping multipathd"
        trun "systemctl stop multipathd.service || pkill multipathd"
        sleep 1
    fi
    retries=10
    while pidof multipathd; do
        ((retries--))
        if [[ $retries -le 0 ]]; then
            tfail_ "failed to stop multipath"
            tend
        fi
        tlog "waiting for multipathd to stop"
        sleep 2
        pidof multipathd && pkill multipathd
    done
    trun "multipath -l -v1"
    retries=10
    while [[ -n `multipath -l -v1` ]]; do
        ((retries--))
        if [[ $retries -le 0 ]]; then
            tfail_ "failed to remove deviece"
            tend
        fi
        tlog "removing multipath device"
        trun "udevadm settle"
        trun "multipath -DF"
        sleep 2
    done
    if lsmod | grep -q "^scsi_debug"; then
        tlog "removing scsi_debug module"
        tok "rmmod scsi_debug"
    fi
    trun "rm -f /etc/multipath.conf"
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

setup_config ()
{
    trun "mpathconf --enable --user_friendly_names y"
    sed -i '/^blacklist[[:space:]]*{/ a\
	device {\
		vendor ".*"\
		product ".*"\
	}
' /etc/multipath.conf
    cat << _EOF_ >> /etc/multipath.conf

blacklist_exceptions {
        device {
                vendor Linux
                product scsi_debug
        }
}
_EOF_
    trun "cat /etc/multipath.conf"
}

do_reconfigure ()
{
    tok "multipathd reconfigure"
    sleep 5
}

rpm -q device-mapper-multipath || dnf install -y device-mapper-multipath
cleanup
setup_config
trun "rm -r /etc/multipath/bindings"
trun "modprobe scsi_debug vpd_use_hostno=0 add_host=2"
sleep 5
trun "systemctl start multipathd.service"
while multipathd show daemon | grep -qv idle; do
    tlog "waiting for multipathd to start"
    sleep 1
done

trun 'multipathd show maps raw format "%n"'
mpath_name=`multipathd show maps raw format "%n" | head -1`
assert "[[ -n $mpath_name ]] && [[ $mpath_name != ok ]]"
new_alias="mpath_test_$$"

trun "sed -i 's/$mpath_name/$new_alias/' /etc/multipath/bindings"
do_reconfigure
trun 'multipathd show maps raw format "%n"'
mpath_name=`multipathd show maps raw format "%n" | head -1`
assert "[[ $mpath_name = $new_alias ]]"

cleanup
tend
