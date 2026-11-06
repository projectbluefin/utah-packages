#!/bin/bash

# Copyright (c) 2021 Red Hat, Inc.
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

# Author: Benjamin Marzinski <bmarzins@redhat.com>

source ../include/ec.sh || exit 200
tlog "running $0"

cleanup ()
{
	trun "multipathd disablequeueing maps"
	sleep 5
	trun "multipath -DF"
	trun "service multipathd stop"
	sleep 5
	trun "udevadm settle"
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

# cleanup existing devices and restart
cleanup
trun "rm -f /etc/multipath.conf"
trun "rm -f /etc/multipath.conf.bak"
trun "rm -r /etc/multipath/bindings"
trun "mpathconf --enable --with_module y --with_multipathd n --find_multipaths n"
sed -i '/^blacklist[[:space:]]*{/ a\
	device {\n		vendor ".*"\n		product ".*"\n	}
' /etc/multipath.conf
if grep -qw blacklist_exceptions /etc/multipath.conf ; then
	sed -i '/^blacklist_exceptions[[:space:]]*{/ a\
	device {\n		vendor Linux\n		product scsi_debug\n	}
' /etc/multipath.conf
else
	cat << _EOF_ >> /etc/multipath.conf
blacklist_exceptions {
	device {
		vendor Linux
		product scsi_debug
	}
}
_EOF_
fi
trun "modprobe scsi_debug num_tgts=20 vpd_use_hostno=0"
sleep 5
trun "service multipathd start"
sleep 5
pathcount=`multipathd show paths raw format %w | wc -l`
assert "[[ $pathcount -eq 20 ]]"
wwids=`multipathd show paths raw format "	wwid %w" | sed '11,$d'`
wwids="${wwids//$'\n'/\\n}"
trun "multipath -DF"
trun "service multipathd stop"
sleep 5
tnot "pidof multipathd"
tok "cp /etc/multipath.conf /etc/mulitpath.conf.bak"
sed -i '/^blacklist[[:space:]]*{/ a\
'"$wwids"'
' /etc/multipath.conf
tok "rm -f /etc/multipath/bindings"
trun "service multipathd start"
sleep 5
mapcount=`multipathd show maps raw format %w | wc -l`
assert "[[ $mapcount -eq 10 ]]"
orig_maps=`multipathd show maps raw format "%n %w"`
trun "service multipathd stop"
sleep 5
tnot "pidof multipathd"
tok "mv -f /etc/mulitpath.conf.bak /etc/multipath.conf"
tok "rm -f /etc/multipath/bindings"
trun "service multipathd start"
sleep 5
mapcount=`multipathd show maps raw format %w | wc -l`
assert "[[ $mapcount -eq 20 ]]"
new_maps=`multipathd show maps raw format "%n %w" | sort`
tlog "Checking if devices have been renamed"
while IFS= read -r line; do
	echo "$new_maps" | grep "$line"
	assert "[[ $? -eq 0 ]]"
done <<< "$orig_maps"
bindings=`cat /etc/multipath/bindings | sed '/^#.*$/d' | sort`
tlog "Checking if devices match bindings"
assert "[[ \"$new_maps\" = \"$bindings\" ]]"
trun "service multipathd reload"
sleep 5
mapcount=`multipathd show maps raw format %w | wc -l`
assert "[[ $mapcount -eq 20 ]]"
reload_maps=`multipathd show maps raw format "%n %w" | sort`
tlog "Checking if devices change on reconfigure"
assert "[[ \"$new_maps\" = \"$reload_maps\" ]]"
cleanup
tend
