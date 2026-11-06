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

# filename: function

# USAGE

test x$LXT_SCSI_DEBUG = x || return
LXT_SCSI_DEBUG=1


get_scsi_debug_devices ()
{
    ls /sys/block/sd* -d 2>/dev/null | while read dev; do
        dev=$(basename $dev);
        grep -qw scsi_debug /sys/block/$dev/device/model && echo "/dev/$dev" && break;
    done

    return 0
}
