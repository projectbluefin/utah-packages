#!/usr/bin/python

# Copyright (c) 2006 Red Hat, Inc. All rights reserved. This copyrighted material
# is made available to anyone wishing to use, modify, copy, or
# redistribute it subject to the terms and conditions of the GNU General
# Public License v.2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see http://www.gnu.org/licenses/.
#
# Author: Bruno Goncalves <bgoncalv@redhat.com>

import subprocess
import sys
import re

def run(cmd):
    print("INFO: Running '%s'..." % cmd)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = p.communicate()

    retcode = p.returncode
    output = stdout.decode('ascii', 'ignore') + stderr.decode('ascii', 'ignore')

    # remove new line from last line
    output = output.rstrip()
    print(output)
    return retcode, output

def start_test():

    #if uses any library linked to /usr this my affect the tools during boot
    print("INFO: Making sure tools provided by device-mapper-persistent-data "
           "are not linked to /usr")

    #Paths where we should have no libraries linked from
    lib_paths = ["/usr/"]

    package = "device-mapper-persistent-data"
    run("yum install -y %s" % package)
    #Get all tools that we need to check
    ret, output = run("rpm -ql %s | grep \"sbin/\"" % package)
    if ret != 0:
        print("FAIL: Could not get the tools shipped from %s" % package)
        return False
    tools = output.split("\n")

    error = False
    for tool in tools:
        if not tool:
            #skip any blank line
            continue
        tool_error = 0
        for lib_path in lib_paths:
            print("INFO: Checking if %s is not linked to libraries at %s" % (tool, lib_path))
            ret, linked_lib = run("ldd %s" % tool)
            if ret != 0:
                print("FAIL: Could not list dynamically libraries for %s" % (tool))
                tool_error += 1
            else:
                #The command executed sucessfuly
                #check if any library linked is from lib_path
                links = linked_lib.split("\n")
                for link in links:
                    if re.match(".*%s.*" % lib_path, link):
                        print("FAIL: %s is linked to %s" % (tool, link))
                        tool_error += 1

            if tool_error == 0:
                print("%s is not linked to %s" % (tool, lib_path))
            else:
                #found some error in at least 1 tool
                error = True

    if error:
        return False

    return True


def main():

    if not start_test():
        print("FAIL: test failed")
        sys.exit(1)

    print("PASS: Test pass")
    sys.exit(0)

main()

