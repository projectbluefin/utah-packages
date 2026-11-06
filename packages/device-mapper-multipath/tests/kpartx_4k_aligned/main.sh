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

function gpt_partitioned_dev() {
    local dev=$1
    { for i in {1..4}; do
        echo -e "n\n\n\n+1M\n\n"
    done; echo w; echo y; } | gdisk $dev &> /dev/null
}

function extract_section_info_from_gdisk() {
    local dev=$1
    local node=$(basename $dev)
    gdisk -l $dev | awk -v dev=$node 'start==1{print dev $1,$2,$3};/Number/{start=1}'
}

function extract_section_info_from_kpartx() {
    local dev=$1
    kpartx -l $dev | awk '{ print $1, $NF, $NF+$4-1 }'
}

tlog "running $0"

rpm -q device-mapper-multipath || yum install -y device-mapper-multipath
rpm -q gdisk || yum install -y gdisk

# eliminate the possibility multipathd create device for new path
trun "service multipathd stop"

# create a device with 4k physical sector
trun "modprobe -r scsi_debug"
trun "modprobe scsi_debug sector_size=512 physblk_exp=3 &> /dev/null"

scsi_debug_dev=$(get_scsi_debug_devices)

trun "gpt_partitioned_dev $scsi_debug_dev"
sleep 3

trun "extract_section_info_from_gdisk $scsi_debug_dev"
result_of_gdisk=$tSTDOUT
trun "extract_section_info_from_kpartx $scsi_debug_dev"
result_of_kpartx=$tSTDOUT

tlog "result_of_kpartx=$result_of_kpartx"
tlog "result_of_gdisk=$result_of_gdisk"
tok '[[ "$result_of_kpartx" == "$result_of_gdisk" ]]'

sleep 3
trun "modprobe -r scsi_debug"

tend
