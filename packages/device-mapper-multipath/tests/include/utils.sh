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


#summary of this script:
#   this script is used to provide the generai utils for the automation script based on shell
#   all the global variables should be upper case and began with under line since this script will be used by many scripts
#   and we don't want the their value is be override by mistake


###############################global variables######################################

#the global variables should begin with under line plus some special keyword??
#global variables, can be used by other scripts
#the stdout and stderr of the cmd execution in Cmd function
#can get the exit status of the Cmd function by $?
_STDOUT=
_STDERR=
#if set to 1 will not print the stdout and stderr in the function Cmd
#should set them to 0 after using it
_IGNORE_STDOUT=0
_IGNORE_STDERR=0

#current hostname, same as the global variable HOSTNAME
#don't use readonly since we maybe source this file many times in the same shell environment
[ -z "$HOSTNAME" ] && HOSTNAME=$(hostname)

#private global variables, only used in current script
#temp dir and files used by Cmd to capture the stderr and exit status of cmd execution
_TEMP_DIR="/tmp/lstf"
[ -d $_TEMP_DIR ] || mkdir -p $_TEMP_DIR >& /dev/null ||  Fail "failed to mkdir $_TEMP_DIR" 

_TEMP_STDERR_FILE="$_TEMP_DIR/stderr.$$"
[ -e $_TEMP_STDERR_FILE ] || touch $_TEMP_STDERR_FILE || Fail "failed to create $_TEMP_STDERR_FILE"
_TEMP_RETURN_FILE="$_TEMP_DIR/return.$$"
[ -e $_TEMP_RETURN_FILE ] || touch $_TEMP_RETURN_FILE || Fail "failed to create $_TEMP_RETURN_FILE"

###############################################################################################

#private function
#print the formated date string

function _date_str (){
    date 2>/dev/null
}

###############################################################################################
#summary:
#   eval the paramters and format the output
#   don't support stderr redirection in the passed command 
#usage:
#   Cmd ls -a
#   if you don't want to print the stdout or stderr you can set the global variables _IGNORE_STDOUT and _IGNORE_STDERR, for example
#   _IGNORE_STDOUT=1  
#   Cmd ls -a
#   _IGNORE_STDOUT=0
#return:
#   return the exit status of paramter value execution
#   store the stdout and stderr to the global variables _STDOUT and _STDERR
###############################################################################################

function Cmd (){
#use the double qutoa to store all the arguments as a single string
    local cmd="$*"
    local date_str=$(_date_str)
    local stdout=$(eval $cmd 2>$_TEMP_STDERR_FILE; echo $? >$_TEMP_RETURN_FILE 2>/dev/null)

#why cannot get the exit status of the value of eval by this ?
#    local exit_status=$?
#remove the \n hence don't use this method
#    local exit_status=$(cat $_TEMP_RETURN_FILE)

    local exit_status=$(< $_TEMP_RETURN_FILE)
    local stderr=$(< $_TEMP_STDERR_FILE)

    _STDOUT=$stdout
    _STDERR=$stderr

#will not print the stdout and stderr if the 2 global variables set to 1
    [ $_IGNORE_STDOUT -eq 1 ] && stdout='redirect the stdout to /dev/null' 
    [ $_IGNORE_STDERR -eq 1 ] && stderr='redirect the stderr to /dev/null' 

    echo "[CMD][$date_str][$HOSTNAME]#$cmd" 
    echo "STDOUT:$stdout"
    echo "STDERR:$stderr"
    echo "RETURN:$exit_status"
    echo

    return $exit_status
}

###############################################################################################
#summary: 
#   print the formated log
#   consider filter the output through the level
#   level should be INFO, ERROR, WARNING, PASSED
#usage:
#   Log "msg" "level"
#   Log "msg"
#  don't use it like this : Log msg level
#return:
#   0
###############################################################################################

#should redirect io to stderr if log_level is error?

function Log (){
    local msg=$1
    local log_level=${2:-INFO}
    local date_str=$(_date_str)

    echo "[$log_level][$date_str]:$msg"
    echo 
    
    return 0
}

###############################################################################################
#summary: 
#   print the formated error message, call stack information and exit the program with 1
#usage:
#   Fail error_msg
#exit:
#   1
###############################################################################################

function Fail (){
    local msg=$*
    local stack=`caller 0`

    Log "$stack"
    Log "$msg" "ERROR"

    exit 1
}

###############################################################################################
#summary: 
#   print the formated passed message and exit the program with 0
#usage:
#   Pass 
#exit:
#   0
###############################################################################################

function Pass (){
    Log "Test case passed" "PASSED"
    
    exit 0
}

###############################################################################################
#summary: 
#   assert the expression, 
#   if the exiting status of the expression is not 0 fail the case and print the failed message
#   if 0 do nothing just return 0
#usage:
#   Assert "$exit_status -eq 0" "failed string" 
#   Assert "ls /dev/sdb" "failed string" 
#return/exit:
#   the exiting value of expression 
###############################################################################################

function Assert (){
#should consider the expr is integra or expression, script?
    local expr=$1
    local failed_msg=$2
    [ $expr ] || Fail "$failed_msg" 

    return 0
}

is_null()
{
    local string=$1
    string=$(echo $string | sed 's/\s//g')
    test -z $string
}

