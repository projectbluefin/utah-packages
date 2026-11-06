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



#----------------------------------------------------------------------------#
# Mp_Conf_Up_Def ()
# Usage:
#   Update default section of /etc/multipath.conf, will also reload conf.
# Parameter:
#   $config_change #config string want to change, like 'polling_interval 5'
# Returns:
#   Return code:
#       0 on success
#       1 if something went wrong.
#   Return string:
#       NULL
#----------------------------------------------------------------------------#

function Mp_Conf_Up_Def (){
    EX_USAGE=64 # Bad arg format
    if [ $# -lt 1 ]; then
        echo 'Usage: Mp_Conf_Up_Def $config_change'
        exit "${EX_USAGE}"
    fi
    RETURN_STR=''
    local multipath_conf_filename="/etc/multipath.conf"
    local config_change="$1"
    echo ${config_change}
    if [ "CHK${config_change}" == "CHK" ];then
        echo 'Usage: Mp_Conf_Up_Def $config_change'
        exit "${EX_USAGE}"
    fi
    python2 -c "
import sys
sys.path.append('"${MP_INCLUDE_PATH}"')
from mpconf import *
update_df_section('""${config_change}""')
"
#TODO: we need to check configuration before we return 0
    RETURN_STR=""
    return 0
} #end of functoin Mp_Conf_Up_Def


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
# Mutipathd_stop()
# Usage:
# check if multipathd stops, if not stop it
# Parameter:
#   NULL
# Returns:
#   Return code:
#       0 on success
#       1 if something went wrong.
# ---------------------------------------------------------#
function Multipathd_stop (){
#    { ! Cmd pidof multipathd ; } || Cmd "service multipathd stop"
    { ! Cmd pidof multipathd ; } || Cmd "kill -9 `pidof multipathd`"
}

# ---------------------------------------------------------#
# Mutipathd_start()
# Usage:
# check if multipathd is installed, if not start it
# Parameter:
#   NULL
# Returns:
#   Return code:
#       0 on success
#       1 if something went wrong.
# ---------------------------------------------------------#
function Multipathd_start (){
#    { Cmd pidof multipathd ; } || Cmd "service multipathd start"
    { Cmd pidof multipathd ; } || Cmd "multipathd"
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
