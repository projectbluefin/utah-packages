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

test x$LXT_TC = x || return
LXT_TC=1

#
# print the current date
# usage: d=$(tdate)
#
tdate () 
{
    date '+%T' 2>/dev/null
}

#
# print the log information
# usage: tlog "hello world" "WARNING"
#
tlog ()
{
    local msg=$1
    local log_level=${2:-INFO}
    local cur_date=$(tdate)

    echo "[$log_level][$cur_date]$msg"
    
    return 0
}

#
# run the cmd and format the log. return the exitint status of cmd
# use the global variables: tSTDOUT and tSTDERR to return the stdout and stderr
# usage: trun "ls"
#        trun "ls"; echo $?
#        stdout=$tSTDOUT
#        stderr=$tSTDERR
#
trun ()
{
    local cmd="$*"
    
    _trun_ "$cmd"
}

#
# verify the execution of command
# if the cmd return 0, mark this checkpoint failed and return 1
# if not, mark it passed and return 0
# usage: tnot "ls /not_existing"
#
tnot () {
    local cmd="$*"
    _trun_ "$cmd" 1
    if test $? -eq 0; then 
        tfail_ "$cmd" ;
    else
        tpass_ "$cmd" ;
    fi 
}

#
# verify the execution of command
# if the cmd return 0, mark this checkpoint passed and return 0
# if not, mark it failed and return 1
# usage: tok "ls /"
#
tok ()
{
    local cmd="$*"
    _trun_ "$cmd" 0
    if test $? -eq 0; then 
        tpass_ "$cmd" ;
    else
        tfail_ "$cmd" ;
    fi 
}

#
# verify the execution of command
# if the cmd return 0, mark this checkpoint passed and return 0
# if not, mark it failes and exit
# usage: terr "ls"
#
#terr ()
#{
#    tok "$*" || tend
#}

#
# verify the execution of command
# if the cmd return 0, will continue to run the script
# if not, mark it failes and exit
# usage: terr "ls"
#
terr ()
{
    local cmd="$*"
    _trun_ "$cmd" 0
    if test $? -ne 0; then 
        tfail_ "$cmd" ;
        tend ;
    fi 
}

#
# exit the program and print the log message
# usage: texit "error message" 100
# similar to the exception 
#
texit ()
{
    msg=$1
    err=$2
    is_null $err && err=1
    test $err -lt 1 || err=1 

    tlog "$msg" "ERROR"
    exit $2 
}

#
# print the test report, cleanup the testing bed and  close the testing. 
# usage: tend
#
tend ()
{
    local pcount=$(wc -l $tPASS_FILE | awk '{print $1}')
    local fcount=$(wc -l $tFAIL_FILE | awk '{print $1}')
    local total=$(( $pcount + $fcount ))

    echo "#################################Test Report###############################"
    echo "TOTAL   : $total" 
    echo "PASSED  : $pcount" 
    echo "FAILED  : $fcount" 
    cat $tPASS_FILE $tFAIL_FILE
    echo "###########################End of running $0########################"

#cleanup
    rm -f $tPASS_FILE $tFAIL_FILE $tRETURN_FILE $tSTDERR_FILE 
#   rm -rf $LXT_TMP_DIR
	if [[ $pcount -eq 0 ]] && [[ $total -eq 0 ]];then
	  exit 0
    fi
    test $pcount -eq 0 && exit 1
    test $pcount -eq $total && exit 0 
    exit 1
}

#
# private function
#

#
# print the error message and call stack. return 1
#
tfail_ ()
{
    local msg=$*
    tlog "$msg" "ERROR" >>$tFAIL_FILE 

    return 1
}

#
# print the sucessful message. return 0
#
tpass_ ()
{
    local msg=$*
    tlog "$msg" "PASS" >> $tPASS_FILE

    return 0
}

_trun_ ()
{
    local cmd="$1"
    local chk="$2"
    local cur_date=$(tdate)

    local stdout=$(eval "$cmd" 2>$tSTDERR_FILE; echo $? >$tRETURN_FILE 2>/dev/null)
#timeout -- how to set timeout?
    local exit_status=$(< $tRETURN_FILE)
    local stderr=$(< $tSTDERR_FILE)
    local msg=CMD
#tnot
    if test x$chk = x1; then
        test $exit_status -eq 0 || msg=PASS
        test $exit_status -eq 0 && msg=FAIL
#should let the tester know this is the negative testing
#if cmd return 0 we will return 1 and vice versa
        cmd="[NOT] $cmd"
    fi
#tok
    if test x$chk = x0; then
        test $exit_status -eq 0 && msg=PASS
        test $exit_status -eq 0 || msg=FAIL
    fi

    tSTDOUT=$stdout
    tSTDERR=$stderr

    test $tIGNORE_STDOUT -eq 1 && stdout='redirect the stdout to /dev/null' 
    test $tIGNORE_STDERR -eq 1 && stderr='redirect the stderr to /dev/null' 

    echo "[$msg][$cur_date][$HOSTNAME]$cmd" 
    echo "STDOUT:"
    test "x$stdout" = x || echo "$stdout"
    echo "STDERR:$stderr"
    echo "RETURN:$exit_status"
    echo

    return $exit_status
}

#
# setup the testing environment
#
_tsetup_ ()
{

    LXT_TMP_DIR="/mnt/testarea/lxt";

    test -z "$HOSTNAME" && HOSTNAME=$(hostname)
    test -d "$LXT_TMP_DIR" || mkdir -p "$LXT_TMP_DIR" >& /dev/null || exit 1

    tSTDERR_FILE="$LXT_TMP_DIR/stderr.$$"
    test -e "$tSTDERR_FILE" || > "$tSTDERR_FILE" || exit 1
    tRETURN_FILE="$LXT_TMP_DIR/return.$$"
    test -e "$tRETURN_FILE" || > "$tRETURN_FILE" || exit 1
    tPASS_FILE="$LXT_TMP_DIR/tc.pass.$$"
    test -e "$tPASS_FILE" || > "$tPASS_FILE" || exit 1
    tFAIL_FILE="$LXT_TMP_DIR/tc.fail.$$"
    test -e "$tFAIL_FILE" || > "$tFAIL_FILE" || exit 1
}

#
# main
#

# global variables
tIGNORE_STDOUT=0
tIGNORE_STDERR=0
tSTDOUT=
tSTDERR=
#LXT_TMP_DIR
# only used in this file
tPASS_FILE=
tFAIL_FILE=

_tsetup_
