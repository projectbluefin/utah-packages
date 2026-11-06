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
	sleep 5
	trun "multipath -F"
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

rpm -q device-mapper-multipath || yum install -y device-mapper-multipath

# cleanup existing devices and restart
cleanup
trun "rm -f /etc/multipath.conf"
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

trun "cp /etc/multipath.conf /etc/multipath.conf.bak"
trun "service multipathd stop"
trun "service multipathd start"

trun "modprobe scsi_debug"
sleep 5
trun "multipath -ll"
pathcount=`multipathd show maps format %w | grep -v uuid | wc -l`
assert "[[ $pathcount -eq 1 ]]"
wwid=`multipathd show maps format %w | grep -v uuid`

# test missing closing quote on alias
cat << _EOF_ >> /etc/multipath.conf
multipaths {
	multipath {
		wwid "$wwid"
		alias "mypath
	}
}
_EOF_
tok "multipath 2>&1 | grep 'missing closing quotes on line'"
trun "multipath -r"
tok "multipath -ll | grep mypath"

# test no value for alias
trun "sed -i 's/alias.*$/alias/g' /etc/multipath.conf"
multipath
tok "multipath 2>&1 | grep \"missing value for option 'alias' on line\""
trun "multipath -r"
tok "multipath -ll | grep mpath"

# test missing starting quote on alias
trun "sed -i 's/alias.*$/alias mypath\"/g' /etc/multipath.conf"
tok "multipath 2>&1 |grep 'ignoring extra data starting with'"
trun "multipath -r"
tok "multipath -ll | grep mypath"

# test wrong quote on alias
trun "sed -i 's/alias.*$/alias <mypath>/g' /etc/multipath.conf"
tnot "multipath 2>&1 | grep config"
trun "multipath -r"
tok "multipath -ll | grep '<mypath>'"

# test value has a space
trun "sed -i 's/alias.*$/alias mypath test/g' /etc/multipath.conf"
tok "multipath 2>&1 |grep 'ignoring extra data starting with'"
trun "multipath -r"
tok "multipath -ll | grep mypath"

# test wrong alias keyword
trun "sed -i 's/alias.*$/alia mypath/g' /etc/multipath.conf"
tok "multipath 2>&1 | grep 'invalid keyword in the multipath section: alia'"
trun "multipath -r"
tok "multipath -ll | grep mpath"
trun "sed -i 's/alia.*$/alias mypath/g' /etc/multipath.conf"

# test no space between the section name and the open bracket that followed it
# fix issue about if a section doesn't have a space between the section name
# and the open bracket, that section isn't read in.
trun "sed -i 's/multipaths.*/multipaths{/g' /etc/multipath.conf"
tnot "multipath 2>&1 | grep config"
trun "multipath -r"
tok "multipath -ll |grep mypath"

# test wrong section keywords
trun "sed -i 's/multipaths.*/ultipaths {/g' /etc/multipath.conf"
tok "multipath 2>&1 | grep 'invalid keyword: ultipaths'"
trun "sed -i 's/defaults.*/efaults {/g' /etc/multipath.conf"
tok "multipath 2>&1 | grep 'invalid keyword: efaults'"
trun "sed -i 's/blacklist {/lacklist {/g' /etc/multipath.conf"
tok "multipath 2>&1 | grep 'invalid keyword: lacklist'"
trun "mv /etc/multipath.conf.bak /etc/multipath.conf"

cleanup
tend
