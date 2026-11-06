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

path=$(pwd)
source ../include/utils.sh || exit 1
source ../include/include.sh || exit 1
source ../include/tc.sh || exit 1
source ../include/mpath.sh || exit 1 
source ../include/scsi_debug.sh || exit 1 

#this script usually is only used by current case
#private global variables, lower case and no under line is okay 
mpath=

function _isconfig (){
    [ -z $mpath ] && return 2
    Cmd "multipath -ll $mpath"
}

function _init (){
#will improve this function
#should return the multipathed disk created by scsi_debug, don't consider the other mutipathed disks
#olnly append the black list exception to /etc/multipath.conf not override
    Setup_Multipath || Fail "failed to create multipathed device via scsi_debug" 
    mpath=$RETURN_STR

    _isconfig
}

function _destroy (){
    Cmd "multipathd disablequeueing maps"
    sleep 5
    Cmd "multipath -DF -R2"
    Cmd "service multipathd stop"
    sleep 5
    Cmd "udevadm settle"
    Cmd "modprobe -r scsi_debug"
}


# ---------------------------------------------------------#
# Mutipath_installation()
# Usage:
# check if multipath starts, if not install it with yum
# Parameter:
#   NULL
# Returns:
#   Return code:
#       0 on success
#       1 if something went wrong.
# ---------------------------------------------------------#
function Multipath_installation (){
    Cmd "rpm -qi device-mapper-multipath" && return 0
    Cmd "yum install -y device-mapper-multipath"
}


# ---------------------------------------------------------#
# Print_kernel_info()
# Usage:
# print the detail running kernel information. 
# Parameter: #   NULL
# Returns:
#   Return code:
#       0 on success
#       1 if something went wrong.
# ---------------------------------------------------------#
function Print_kernel_info (){
    Cmd "lsb_release -a"
    Cmd "uname -a"
}


# ---------------------------------------------------------#
# Print_multipath_pkginfo()()
# Usage:
# print the multipath pacakge information
# Parameter:
#   NULL
# Returns:
#   Return code:
#       0 on success
#       1 if something went wrong.
# ---------------------------------------------------------#
function Print_multipath_pkginfo (){
    Cmd "rpm -qi device-mapper-multipath"
    Cmd "rpm -qi kpartx"
}


# ---------------------------------------------------------#
# Setup_Multipath ()
# Usage:
#   return mpath_name if we have multipath devices, if not,
#   we use scsi_debug to create a multipath device.
# Parameter:
#   NULL
# Returns:
#   Return code:
#       0 on success
#       1 if something went wrong.
#   Return string:
#       RETURN_STR  # $mpath_name_list, like "mpath0 mpath1"
# ---------------------------------------------------------#

function Setup_Multipath (){
    RETURN_STR=''
    local mpath_name_list=$(dmsetup table \
        | perl -ne 'print "$1 " if /(mpath[a-z0-9]+):[0-9 ]+multipath.*/')
    if [ "CHK${mpath_name_list}" != "CHK" ];then
        mpath_name_list="$(echo ${mpath_name_list} | sed -e 's/ $//')"
        echo "INFO: Found multipath devices: ${mpath_name_list}"
#RHEL 5 will disable some wwn mpath if we install OS with ondisk=mapper/mpath0
# option, so we need to enable them all
        if [ "CHK$(uname -r | egrep "2\.6\.18.*el5")" != "CHK" ];then
            cat << AA > /etc/multipath.conf
defaults {
    user_friendly_names     yes
}
blacklist {
    device {
        vendor .*
        product .*
    }
}
blacklist_exceptions {
    device {
        vendor Linux
        product scsi_debug
    }
    device {
        vendor IQSTOR
        product .*
    }
    device {
        vendor NETAPP
        product .*
    }
    device {
        vendor HITACHI
        product .*
    }
}
AA
        service multipathd start
        sleep 5s #multipathd return premature
        multipath -r
        multipathd -k'reconfigure'
        sleep 5s
        mpath_name_list=$(dmsetup table \
            | perl -ne 'print "$1 " if /(mpath[a-z0-9]+):[0-9 ]+multipath.*/')
        fi
        if [ "CHK${mpath_name_list}" == "CHK" ];then
            echo -n "FATAL: still no mulipath devices setup,"
            echo " check code in Setup_Multipath()"
            RETURN_STR=''
            return 1
        fi
        RETURN_STR="${mpath_name_list}"
        return 0
    fi
#setup scsi_debug
    echo "INFO: Loading scsi_debug module for simulation of mpath"
    modprobe scsi_debug vpd_use_hostno=0 add_host=2

    echo "INFO: Waiting for udev to create /dev/sdX"
    sleep 15s #wait for udev to create /dev/sdX
    rpm -q device-mapper-multipath 2>/dev/null 1>/dev/null
    if [ $? -ne 0 ];then
        echo "INFO: Installing device-mapper-multipath via yum"
        yum -y install device-mapper-multipath
    fi
#enable multipath for scsi_debug.
    cat << AA > /etc/multipath.conf
defaults {
    user_friendly_names     yes
}
blacklist {
        device {
                vendor .*
                product .*
        }
}
blacklist_exceptions {
        device {
                vendor Linux
                product scsi_debug
        }
}
AA
    echo "INFO: /etc/multipath.conf updated"
    cat /etc/multipath.conf
    echo "INFO: Restarting multiapth and reload configuration"
    service multipathd restart
    sleep 5s #multipathd return premature
    multipathd -k'reconfig'
    sleep 5s

    mpath_name_list=$(dmsetup table | perl -ne 'print "$1 " if /(mpath[a-z0-9]+):[0-9 ]+multipath.*/')
    if [ "CHK${mpath_name_list}" != "CHK" ];then
        mpath_name_list="$(echo ${mpath_name_list} | sed -e 's/ $//')"
        echo "INFO: found mpath: ${mpath_name_list}"
        RETURN_STR="${mpath_name_list}"
        return 0
    fi
    return 1
} #end of functoin Setup_Multipath


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

