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
# along with this program.  If not, see <http://www.gnu.cp /etc/multipath.conf /etc/multipath.conf.$$org/licenses/>.

# Author: Lin Li   <lilin@redhat.com>

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

multipaths {
	multipath {
		wwid TEST_WWID
		alias test
	}
}
_EOF_
    trun "cat /etc/multipath.conf"
}

do_reconfigure ()
{
    trun "cat /etc/multipath.conf"
    tok "multipathd reconfigure"
    sleep 5
}

trun "rpm -q device-mapper-multipath || dnf install -y device-mapper-multipath"
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
trun 'multipathd show maps raw format "%n %w"'
# verify user_friendly_name
tok 'multipathd show maps raw format "%n" | head -1 | grep -q mpath'
wwid=`multipathd show maps raw format "%w" | head -1`
assert "[[ -n $wwid ]] && [[ $wwid != ok ]]"
sed -i 's/TEST_WWID/'"$wwid"'/' /etc/multipath.conf
do_reconfigure
trun 'multipathd show maps raw format "%n %w"'
# verify configured alias takes precedence over user_friendly_name
tok 'multipathd show maps raw format "%n" | head -1 | grep -q test'
trun "mpathconf --user_friendly_names n"
do_reconfigure
trun 'multipathd show maps raw format "%n %w"'
# verify configured alias takes precedence over wwid name
tok 'multipathd show maps raw format "%n" | head -1 | grep -q test'
sed -i 's/'"$wwid"'/TEST_WWID/' /etc/multipath.conf
do_reconfigure
trun 'multipathd show maps raw format "%n %w"'
tok 'multipathd show maps raw format "%n" | head -1 | grep -q '"$wwid"
cleanup
tend
