#!/usr/bin/python

# Copyright (c) 2017 Red Hat, Inc. All rights reserved. This copyrighted material
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
# Author: Jakub Krysl <jkrysl@redhat.com>

"""dmpd_library.py: Complete library providing functionality for device-mapper-persistent-data upstream test."""

from __future__ import print_function

import platform
from os.path import expanduser
import re #regex
import sys, os
import subprocess
import time
import fileinput
# TODO: Is this really necessary? Unlikely we will run into python2 in rawhide
# again...


def _print(string):
    module_name = __name__
    string = re.sub("DEBUG:", "DEBUG:("+ module_name + ") ", string)
    string = re.sub("FAIL:", "FAIL:("+ module_name + ") ", string)
    string = re.sub("FATAL:", "FATAL:("+ module_name + ") ", string)
    string = re.sub("WARN:", "WARN:("+ module_name + ") ", string)
    print(string)
    return


def run(cmd, return_output=False, verbose=True, force_flush=False):
    """Run a command line specified as cmd.
    The arguments are:
    \tcmd (str):    Command to be executed
    \tverbose:      if we should show command output or not
    \tforce_flush:  if we want to show command output while command is being executed. eg. hba_test run
    \treturn_output (Boolean): Set to True if want output result to be returned as tuple. Default is False
    Returns:
    \tint: Return code of the command executed
    \tstr: As tuple of return code if return_output is set to True
    """
    #by default print command output
    if (verbose == True):
        #Append time information to command
        date = "date \"+%Y-%m-%d %H:%M:%S\""
        p = subprocess.Popen(date, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = p.communicate()
        stdout = stdout.decode('ascii', 'ignore').rstrip("\n")
        _print("INFO: [%s] Running: '%s'..." % (stdout, cmd))

    #enabling shell=True, because was the only way I found to run command with '|'
    if not force_flush:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = p.communicate()
        sys.stdout.flush()
        sys.stderr.flush()
    else:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        stdout = ""
        stderr = ""
        while p.poll() is None:
            new_data = p.stdout.readline()
            stdout += new_data
            if verbose:
                sys.stdout.write(new_data)
            sys.stdout.flush()

    retcode = p.returncode

    output = stdout.decode('ascii', 'ignore') + stderr.decode('ascii', 'ignore')

    #remove new line from last line
    output = output.rstrip()

    #by default print command output
    #if force_flush we already printed it
    if verbose == True and not force_flush:
        print(output)

    if return_output == False:
        return retcode
    else:
        return retcode, output


def atomic_run(message, success=True, return_output=False, **kwargs):
    errors = kwargs.pop("errors")
    command = kwargs.pop("command")
    params = []
    for a in kwargs:
        params.append(str(a) + " = " + str(kwargs[a]))
    params = ", ".join([str(i) for i in params])
    _print("\nINFO: " + message + " with params %s" % params)
    if return_output:
        kwargs["return_output"] = True
        ret, output = command(**kwargs)
    else:
        ret = command(**kwargs)
    expected_break = {True: False, False: True}
    print("(Returned, Expected)")
    if command == run:
        expected_break = {True: 1, False: 0}
        if ret in expected_break:
            print(not expected_break[ret], success)
        else:
            print(ret, success)
    else:
        print(ret, success)
    if ret == expected_break[success]:
        error = "FAIL: " + message + " with params %s failed" % params
        _print(error)
        errors.append(error)
    sleep(0.2)
    if return_output:
        return output
    else:
        return ret


def sleep(duration):
    """
    It basically call sys.sleep, but as stdout and stderr can be buffered
    We flush them before sleep
    """
    sys.stdout.flush()
    sys.stderr.flush()
    time.sleep(duration)
    return


def mkdir(new_dir):
    if os.path.isdir(new_dir):
        _print("INFO: %s already exist" % new_dir)
        return True
    cmd = "mkdir -p %s" % new_dir
    retcode, output = run(cmd, return_output=True, verbose=False)
    if retcode != 0:
        _print("WARN: could create directory %s" % new_dir)
        print(output)
        return False
    return True


def dist_release():
    """
    Find out the release number of Linux distribution.
    """
    dist = platform.release()
    if not dist:
        _print("WARN: dist_release() - Could not determine dist release")
        return None
    return dist


def dist_ver():
    """
    Check the Linux distribution version.
    """
    release = dist_release()
    if not release:
        return None
    m = re.match("(\d+).\d+", release)
    if m:
        return int(m.group(1))

    # See if it is only digits, in that case return it
    m = re.match("(\d+)", release)
    if m:
        return int(m.group(1))

    _print("WARN: dist_ver() - Invalid release output %s" % release)
    return None


def show_sys_info():
    print("### Kernel Info: ###")
    ret, kernel = run ("uname -a", return_output=True, verbose=False)
    ret, taint_val = run("cat /proc/sys/kernel/tainted", return_output=True, verbose=False)
    print("Kernel version: %s" % kernel)
    print("Kernel tainted: %s" % taint_val)
    print("### IP settings: ###")
    run("ip a")

    if run("rpm -q device-mapper-multipath") == 0:
        #Abort test execution if multipath is not working well
        if run("multipath -l 2>/dev/null") != 0:
            print("WARN: Multipath is not configured correctly")
            return
        #Flush all unused multipath devices before starting the test
        run("multipath -F")
        run("multipath -r")


def get_free_space(path):
    """
    Get free space of a path.
    Path could be:
    \t/dev/sda
    \t/root
    \t./
    """
    if not path:
        return None

    cmd = "df -B 1 %s" % (path)
    retcode, output = run(cmd, return_output=True, verbose=False)
    if retcode != 0:
        _print("WARN: get_free_space() - could not run %s" % (cmd))
        print(output)
        return None
    fs_list = output.split("\n")
    # delete the header info
    del fs_list[0]

    if len(fs_list) > 1:
        #Could be the information was too long and splited in lines
        tmp_info = "".join(fs_list)
        fs_list[0] = tmp_info

    #expected order
    #Filesystem    1B-blocks       Used   Available Use% Mounted on
    free_space_regex = re.compile("\S+\s+\d+\s+\d+\s+(\d+)")
    m = free_space_regex.search(fs_list[0])
    if m:
        return int(m.group(1))
    return None


def size_human_2_size_bytes(size_human):
    """
    Usage
        size_human_2_size_bytes(size_human)
    Purpose
        Convert human readable stander size to B
    Parameter
        size_human     # like '1KiB'
    Returns
        size_bytes     # like 1024
    """
    if not size_human:
        return None

    # make sure size_human is a string, could be only numbers, for example
    size_human = str(size_human)
    if not re.search("\d", size_human):
        # Need at least 1 digit
        return None

    size_human_regex = re.compile("([\-0-9\.]+)(Ki|Mi|Gi|Ti|Ei|Zi){0,1}B$")
    m = size_human_regex.match(size_human)
    if not m:
        if re.match("^\d+$", size_human):
            # Assume size is already in bytes
            return size_human
        _print("WARN: '%s' is an invalid human size format" % size_human)
        return None

    number = None
    fraction = 0
    # check if number is fractional
    f = re.match("(\d+)\.(\d+)", m.group(1))
    if f:
        number = int(f.group(1))
        fraction = int(f.group(2))
    else:
        number = int(m.group(1))

    unit = m.group(2)
    if not unit:
        unit = 'B'

    for valid_unit in ['B', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if unit == valid_unit:
            if unit == 'B':
                # cut any fraction if was given, as it is not valid
                return str(number)
            return int(number + fraction)
        number *= 1024
        fraction *= 1024
        fraction /= 10
    return int(number + fraction)


def size_bytes_2_size_human(num):
    if not num:
        return None

    #Even if we receive string we convert so we can process it
    num = int(num)
    for unit in ['B','KiB','MiB','GiB','TiB','PiB','EiB','ZiB']:
        if abs(num) < 1024.0:
            size_human = "%3.1f%s" % (num, unit)
            #round it down removing decimal numbers
            size_human = re.sub("\.\d+", "", size_human)
            return size_human
        num /= 1024.0
    #Very big number!!
    size_human = "%.1f%s" % (num, 'Yi')
    #round it down removing decimal numbers
    size_human = re.sub("\.\d+", "", size_human)
    return size_human


def install_package(pack):
    """
    Install a package "pack" via `yum install -y `
    """
    #Check if package is already installed
    ret, ver = run("rpm -q %s" % pack, verbose=False, return_output=True)
    if ret == 0:
        _print("INFO: %s is already installed (%s)" % (pack, ver))
        return True

    if run("yum install -y %s" % pack) != 0:
        msg = "FAIL: Could not install %s" % pack
        _print(msg)
        return False

    _print("INFO: %s was successfully installed" % pack)
    return True


def create_filesystem(vg_name, lv_name, filesystem="xfs"):
    if filesystem not in ["xfs", "ext4", "btrfs"]:
        _print("WARN: Unknown filesystem.")
        return False
    if run("mkfs.%s /dev/%s/%s" % (filesystem, vg_name, lv_name), verbose=True) != 0:
        _print("WARN: Could not create filesystem %s on %s/%s" % (filesystem, vg_name, lv_name))
        return False
    return True


def metadata_snapshot(vg_name, lv_name):
    if run("dmsetup suspend /dev/mapper/%s-%s-tpool" % (vg_name, lv_name), verbose=True) != 0:
        _print("WARN: Device mapper could not suspend /dev/mapper/%s-%s-tpool" % (vg_name, lv_name))
        return False
    if run("dmsetup message /dev/mapper/%s-%s-tpool 0 reserve_metadata_snap" % (vg_name, lv_name), verbose=True) != 0:
        _print("WARN: Device mapper could not create metadata snaphot on /dev/mapper/%s-%s-tpool" % (vg_name, lv_name))
        return False
    if run("dmsetup resume /dev/mapper/%s-%s-tpool" % (vg_name, lv_name), verbose=True) != 0:
        _print("WARN: Device mapper could not resume /dev/mapper/%s-%s-tpool" % (vg_name, lv_name))
        return False
    return True


class LogChecker:
    def __init__(self):
        segfault_msg = " segfault "
        calltrace_msg = "Call Trace:"
        self.error_mgs = [segfault_msg, calltrace_msg]

    def check_all(self):
        """Check for error on the system
        Returns:
        \tBoolean:
        \t\tTrue is no error was found
        \t\tFalse if some error was found
        """
        _print("INFO: Checking for error on the system")
        error = 0

        if not self.kernel_check():
            error += 1
        if not self.abrt_check():
            error += 1
        if not self.messages_dump_check():
            error += 1
        if not self.dmesg_check():
            error += 1
        if not self.console_log_check():
            error += 1
        if not self.kdump_check():
            error += 1

        if error:
            log_messages = "/var/log/messages"
            if os.path.isfile(log_messages):
                print("submit %s, named messages.log" % log_messages)
                run("cp %s messages.log" % log_messages)
                run("rhts-submit-log -l messages.log")

            _print("INFO: Umounting NFS to avoid sosreport being hang there")
            run("umount /var/crash")



            ret_code = run("which sosreport", verbose=False)
            if ret_code != 0:
                _print("WARN: sosreport is not installed")
                _print("INFO: Mounting NFS again")
                run("mount /var/crash")
                return False

            print("Generating sosreport log")
            disable_plugin = ""
            if run("sosreport --list-plugins | grep emc") == 0:
                disable_plugin = "-n emc"
            ret_code, sosreport_log = run("sosreport --batch %s" % disable_plugin, return_output=True)
            if ret_code != 0:
                _print("WARN: sosreport command failed")
                _print("INFO: Mounting NFS again")
                run("mount /var/crash")
                return False

            sos_lines = sosreport_log.split("\n")
            sos_file = None
            for line in sos_lines:
                #In RHEL7 sosreport is saving under /var/tmp while RHEL6 uses /tmp...
                m = re.match(r"\s+((\/var)?\/tmp\/sosreport\S+)", line)
                if m:
                    sos_file = m.group(1)
            if not sos_file:
                _print("WARN: could not save sosreport log")
                _print("INFO: Mounting NFS again")
                run("mount /var/crash")
                return False

            run("rhts-submit-log -l %s" % sos_file)
            _print("INFO: Mounting NFS again")
            run("mount /var/crash")

            return False
        return True

    @staticmethod
    def abrt_check():
        """Check if abrtd found any issue
        Returns:
        \tBoolean:
        \t\tTrue no error was found
        \t\tFalse some error was found
        """
        _print("INFO: Checking abrt for error")

        if run("rpm -q abrt", verbose=False) != 0:
            _print("WARN: abrt tool does not seem to be installed")
            _print("WARN: skipping abrt check")
            return True

        if run("pidof abrtd", verbose=False) != 0:
            _print("WARN: abrtd is not running")
            return False

        ret, log = run("abrt-cli list", return_output=True)
        if ret != 0:
            _print("WARN: abrt-cli command failed")
            return False

        # We try to match for "Directory" to check if
        # abrt-cli list is actually listing any issue
        error = False
        if log:
            lines = log.split("\n")
            for line in lines:
                m = re.match(r"Directory:\s+(\S+)", line)
                if m:
                    directory = m.group(1)
                    filename = directory
                    filename = filename.replace(":", "-")
                    filename += ".tar.gz"
                    run("tar cfzP %s %s" % (filename, directory))
                    run("rhts-submit-log -l %s" % filename)
                    # if log is saved on beaker, it can be deleted from server
                    # it avoids next test from detecting this failure
                    run("abrt-cli rm %s" % directory)
                    error = True

        if error:
            _print("WARN: Found abrt error")
            return False

        _print("PASS: no Abrt entry has been found.")
        return True

    @staticmethod
    def kernel_check():
        """
        Check if kernel got tainted.
        It checks /proc/sys/kernel/tainted which returns a bitmask.
        The values are defined in the kernel source file include/linux/kernel.h,
        and explained in kernel/panic.c
        cd /usr/src/kernels/`uname -r`/
        Sources are provided by kernel-devel
        Returns:
        \tBoolean:
        \t\tTrue if did not find any issue
        \t\tFalse if found some issue
        """
        _print("INFO: Checking for tainted kernel")

        previous_tainted_file = "/tmp/previous-tainted"

        ret, tainted = run("cat /proc/sys/kernel/tainted", return_output=True)

        tainted_val = int(tainted)
        if tainted_val == 0:
            run("echo %d > %s" % (tainted_val, previous_tainted_file), verbose=False)
            _print("PASS: Kernel is not tainted.")
            return True

        _print("WARN: Kernel is tainted!")

        if not os.path.isfile(previous_tainted_file):
            run("echo 0 > %s" % previous_tainted_file, verbose=False)
        ret, prev_taint = run("cat %s" % previous_tainted_file, return_output=True)
        prev_taint_val = int(prev_taint)
        if prev_taint_val == tainted_val:
            _print("INFO: Kernel tainted has already been handled")
            return True

        run("echo %d > %s" % (tainted_val, previous_tainted_file), verbose=False)

        # check all bits that are set
        bit = 0
        while tainted_val != 0:
            if tainted_val & 1:
                _print("\tTAINT bit %d is set\n" % bit)
            bit += 1
            # shift tainted value
            tainted_val /= 2
        # List all tainted bits that are defined
        print("List bit definition for tainted kernel")
        run("cat /usr/src/kernels/`uname -r`/include/linux/kernel.h | grep TAINT_")

        found_issue = False
        # try to find the module which tainted the kernel, tainted module have a mark between '('')'
        ret, output = run("cat /proc/modules | grep -e '(.*)' |  cut -d' ' -f1", return_output=True)
        tainted_mods = output.split("\n")
        # For example during iscsi async_events scst tool loads an unsigned module
        # just ignores it, so we will ignore this tainted if there is no tainted
        # modules loaded
        if not tainted_mods:
            _print("INFO: ignoring tainted as the module is not loaded anymore")
        else:
            ignore_modules = ["ocrdma", "nvme_fc", "nvmet_fc"]
            for tainted_mod in tainted_mods:
                if tainted_mod:
                    _print("INFO: The following module got tainted: %s" % tainted_mod)
                    run("modinfo %s" % tainted_mod)
                    # we are ignoring ocrdma module
                    if tainted_mod in ignore_modules:
                        _print("INFO: ignoring tainted on %s" % tainted_mod)
                        run("echo %d > %s" % (tainted_val, previous_tainted_file), verbose=False)
                        continue
                    found_issue = True

        run("echo %s > %s" % (tainted, previous_tainted_file), verbose=False)
        if found_issue:
            return False

        return True

    @staticmethod
    def _date2num(date):
        date_map = {"Jan": "1",
                    "Feb": "2",
                    "Mar": "3",
                    "Apr": "4",
                    "May": "5",
                    "Jun": "6",
                    "Jul": "7",
                    "Aug": "8",
                    "Sep": "9",
                    "Oct": "10",
                    "Nov": "11",
                    "Dec": "12"}

        date_regex = r"(\S\S\S)\s(\d+)\s(\d\d:\d\d:\d\d)"
        m = re.match(date_regex, date)
        month = date_map[m.group(1)]
        day = str(m.group(2))
        # if day is a single digit, add '0' to begin
        if len(day) == 1:
            day = "0" + day

        hour = m.group(3)
        hour = hour.replace(":", "")

        value = month + day + hour

        return value

    @staticmethod
    def clear_dmesg():
        cmd = "dmesg --clear"
        if dist_ver() < 7:
            cmd = "dmesg -c"
        run(cmd, verbose=False)
        return True

    def messages_dump_check(self):
        previous_time_file = "/tmp/previous-dump-check"

        log_msg_file = "/var/log/messages"
        if not os.path.isfile(log_msg_file):
            _print("WARN: Could not open %s" % log_msg_file)
            return True

        log_file = open(log_msg_file, encoding="utf-8", errors="ignore")
        log = log_file.read()

        begin_tag = "\\[ cut here \\]"
        end_tag = "\\[ end trace "

        if not os.path.isfile(previous_time_file):
            first_time = "Jan 01 00:00:00"
            time = self._date2num(first_time)
            run("echo %s > %s" % (time, previous_time_file))

        # Read the last time test ran
        ret, last_run = run("cat %s" % previous_time_file, return_output=True)
        _print("INFO: Checking for stack dump messages after: %s" % last_run)

        # Going to search the file for text that matches begin_tag until end_tag
        dump_regex = begin_tag + "(.*?)" + end_tag
        m = re.findall(dump_regex, log, re.MULTILINE)
        if m:
            _print("INFO: Checking if it is newer than: %s" % last_run)
            print(m.group(1))
            # TODO

        _print("PASS: No recent dump messages has been found.")
        return True

    def dmesg_check(self):
        """
        Check for error messages on dmesg ("Call Trace and segfault")
        """
        _print("INFO: Checking for errors on dmesg.")
        error = 0
        for msg in self.error_mgs:
            ret, output = run("dmesg | grep -i '%s'" % msg, return_output=True)
            if output:
                _print("WARN: found %s on dmesg" % msg)
                run("echo '\nINFO found %s  Saving it\n'>> dmesg.log" % msg)
                run("dmesg >> dmesg.log")
                run("rhts-submit-log -l dmesg.log")
                error = + 1
        self.clear_dmesg()
        if error:
            return False

        _print("PASS: No errors on dmesg have been found.")
        return True

    def console_log_check(self):
        """
        Checks for error messages on console log ("Call Trace and segfault")
        """
        error = 0
        console_log_file = "/root/console.log"
        prev_console_log_file = "/root/console.log.prev"
        new_console_log_file = "/root/console.log.new"

        if not os.environ.get('LAB_CONTROLLER'):
            _print("WARN: Could not find lab controller")
            return True

        if not os.environ.get('RECIPEID'):
            _print("WARN: Could not find recipe ID")
            return True

        lab_controller = os.environ['LAB_CONTROLLER']
        recipe_id = os.environ['RECIPEID']

        # get current console log
        url = "http://%s:8000/recipes/%s/logs/console.log" % (lab_controller, recipe_id)

        if (run("wget -q %s -O %s" % (url, new_console_log_file)) != 0):
            _print("INFO: Could not get console log")
            # return sucess if could not get console.log
            return True

        # if there was previous console log, we just check the new part
        run("diff -N -n --unidirectional-new-file %s %s > %s" % (
        prev_console_log_file, new_console_log_file, console_log_file))

        # backup the current full console.log
        # next time we run the test we will compare just
        # what has been appended to console.log
        run("mv -f %s %s" % (new_console_log_file, prev_console_log_file))

        _print("INFO: Checking for errors on %s" % console_log_file)
        for msg in self.error_mgs:
            ret, output = run("cat %s | grep -i '%s'" % (console_log_file, msg), return_output=True)
            if output:
                _print("INFO found %s on %s" % (msg, console_log_file))
                run("rhts-submit-log -l %s" % console_log_file)
                error = + 1

        if error:
            return False

        _print("PASS: No errors on %s have been found." % console_log_file)
        return True

    @staticmethod
    def kdump_check():
        """
        Check for kdump error messages.
        It assumes kdump is configured on /var/crash
        """
        error = 0

        previous_kdump_check_file = "/tmp/previous-kdump-check"
        kdump_dir = "/var/crash"
        ret, hostname = run("hostname", verbose=False, return_output=True)

        if not os.path.exists("%s/%s" % (kdump_dir, hostname)):
            _print("INFO: No kdump log found for this server")
            return True

        ret, output = run("ls -l %s/%s |  awk '{print$9}'" % (kdump_dir, hostname), return_output=True)
        kdumps = output.split("\n")
        kdump_dates = []
        for kdump in kdumps:
            if kdump == "":
                continue
            # parse on the date, remove the ip of the uploader
            m = re.match(".*?-(.*)", kdump)
            if not m:
                _print("WARN: unexpected format for kdump (%s)" % kdump)
                continue
            date = m.group(1)
            # Old dump were using "."
            date = date.replace(r"\.", "-")
            # replace last "-" with space to format date properly
            index = date.rfind("-")
            date = date[:index] + " " + date[index + 1:]
            _print("INFO: Found kdump from %s" % date)
            kdump_dates.append(date)

        # checks if a file to store last run exists, if not create it
        if not os.path.isfile("%s" % previous_kdump_check_file):
            # time in seconds
            ret, time = run(r"date +\"\%s\"", verbose=False, return_output=True)
            run("echo -n %s > %s" % (time, previous_kdump_check_file), verbose=False)
            _print("INFO: kdump check is executing for the first time.")
            _print("INFO: doesn't know from which date should check files.")
            _print("PASS: Returning success.")
            return True

        # Read the last time test ran
        ret, previous_check_time = run("cat %s" % previous_kdump_check_file, return_output=True)
        # just add new line to terminal because the file should not have already new line character
        print("")

        for date in kdump_dates:
            # Note %% is escape form to use % in a string
            ret, kdump_time = run("date --date=\"%s\" +%%s" % date, return_output=True)
            if ret != 0:
                _print("WARN: Could not convert date %s" % date)
                continue

            if not kdump_time:
                continue
            if (int(kdump_time) > int(previous_check_time)):
                _print("WARN: Found a kdump log from %s (more recent than %s)" % (date, previous_check_time))
                _print("WARN: Check %s/%s" % (kdump_dir, hostname))
                error += 1

        ret, time = run(r"date +\"\%s\"", verbose=False, return_output=True)
        run("echo -n %s > %s" % (time, previous_kdump_check_file), verbose=False)

        if error:
            return False

        _print("PASS: No errors on kdump have been found.")
        return True


class TestClass:
    #we currently support these exit code for a test case
    tc_sup_status = {"pass" : "PASS: ",
                    "fail" : "ERROR: ",
                    "skip" : "SKIP: "}
    tc_pass = []
    tc_fail = []
    tc_skip = []    #For some reason it did not execute
    tc_results = [] #Test results stored in a list

    test_dir = "%s/.stqe-test" % expanduser("~")
    test_log = "%s/test.log" % test_dir

    def __init__(self):
        print("################################## Test Init ###################################")
        self.log_checker = LogChecker()
        if not os.path.isdir(self.test_dir):
            mkdir(self.test_dir)
        # read entries on test.log, there will be entries if tend was not called
        # before starting a TC class again, usually if the test case reboots the server
        if not os.path.isfile(self.test_log):
            #running the test for the first time
            show_sys_info()
            #Track memory usage during test
            run("free -b > init_mem.txt", verbose=False)
            run("top -b -n 1 > init_top.txt", verbose=False)
        else:
            try:
                f = open(self.test_log)
                file_data = f.read()
                f.close()
            except:
                _print("WARN: TestClass() could not read %s" % self.test_log)
                return
            finally:
                f.close()
            log_entries = file_data.split("\n")
            #remove the file, once tlog is ran it will add the entries again...
            run("rm -f %s" % (self.test_log), verbose=False)
            if log_entries:
                _print("INFO: Loading test result from previous test run...")
                for entry in log_entries:
                    self.tlog(entry)
        print("################################################################################")
        return

    def tlog(self, string):
        """print message, if message begins with supported message status
        the test message will be added to specific test result array
        """
        print(string)
        if re.match(self.tc_sup_status["pass"], string):
            self.tc_pass.append(string)
            self.tc_results.append(string)
            run("echo '%s' >> %s" % (string, self.test_log), verbose=False)
        if re.match(self.tc_sup_status["fail"], string):
            self.tc_fail.append(string)
            self.tc_results.append(string)
            run("echo '%s' >> %s" % (string, self.test_log), verbose=False)
        if re.match(self.tc_sup_status["skip"], string):
            self.tc_skip.append(string)
            self.tc_results.append(string)
            run("echo '%s' >> %s" % (string, self.test_log), verbose=False)
        return None

    @staticmethod
    def trun(cmd, return_output=False):
        """Run the cmd and format the log. return the exitint status of cmd
        The arguments are:
        \tCommand to run
        \treturn_output: if should return command output as well (Boolean)
        Returns:
        \tint: Command exit code
        \tstr: command output (optional)
        """
        return run(cmd, return_output)

    def tok(self, cmd, return_output=False):
        """Run the cmd and expect it to pass.
        The arguments are:
        \tCommand to run
        \treturn_output: if should return command output as well (Boolean)
        Returns:
        \tBoolean: return_code
        \t\tTrue: If command excuted successfully
        \t\tFalse: Something went wrong
        \tstr: command output (optional)
        """
        cmd_code = None
        ouput = None
        ret_code = None
        if not return_output:
            cmd_code = run(cmd)
        else:
            cmd_code, output = run(cmd, return_output)

        if cmd_code == 0:
            self.tpass(cmd)
            ret_code = True
        else:
            self.tfail(cmd)
            ret_code = False

        if return_output:
            return ret_code, output
        else:
            return ret_code

    def tnok(self, cmd, return_output=False):
        """Run the cmd and expect it to fail.
        The arguments are:
        \tCommand to run
        \treturn_output: if should return command output as well (Boolean)
        Returns:
        \tBoolean: return_code
        \t\tFalse: If command excuted successfully
        \t\tTrue: Something went wrong
        \tstr: command output (optional)
        """
        cmd_code = None
        ouput = None
        ret_code = None
        if not return_output:
            cmd_code = run(cmd)
        else:
            cmd_code, output = run(cmd, return_output)

        if cmd_code != 0:
            self.tpass(cmd + " [exited with error, as expected]")
            ret_code = True
        else:
            self.tfail(cmd + " [expected to fail, but it did not]")
            ret_code = False

        if return_output:
            return ret_code, output
        else:
            return ret_code

    def tpass(self, string):
        """Will add PASS + string to test log summary
        """
        self.tlog(self.tc_sup_status["pass"] + string)
        return None

    def tfail(self, string):
        """Will add ERROR + string to test log summary
        """
        self.tlog(self.tc_sup_status["fail"] + string)
        return None

    def tskip(self, string):
        """Will add SKIP + string to test log summary
        """
        self.tlog(self.tc_sup_status["skip"] + string)
        return None

    def tend(self):
        """It checks for error in the system and print test summary
        Returns:
        \tBoolean
        \t\tTrue if all test passed and no error was found on server
        \t\tFalse if some test failed or found error on server
        """
        if self.log_checker.check_all():
            self.tpass("Search for error on the server")
        else:
            self.tfail("Search for error on the server")

        print("################################ Test Summary ##################################")
        #Will print test results in order and not by test result order
        for tc in self.tc_results:
            print(tc)

        n_tc_pass = len(self.tc_pass)
        n_tc_fail = len(self.tc_fail)
        n_tc_skip = len(self.tc_skip)
        print("#############################")
        print("Total tests that passed: " + str(n_tc_pass))
        print("Total tests that failed: " + str(n_tc_fail))
        print("Total tests that skipped: " + str(n_tc_skip))
        print("################################################################################")
        sys.stdout.flush()
        #Added this sleep otherwise some of the prints were not being shown....
        sleep(1)
        run("rm -f %s" % (self.test_log), verbose=False)
        run("rmdir %s" % (self.test_dir), verbose=False)

        #If at least one test failed, return error
        if n_tc_fail > 0:
            return False

        return True


class LoopDev:
    def __init__(self):
        self.image_path = "/tmp"

    @staticmethod
    def _get_loop_path(name):
        loop_path = name
        if "/dev/" not in name:
            loop_path = "/dev/" + name

        return loop_path

    @staticmethod
    def _get_image_file(name, image_path):
        image_file = "%s/%s.img" % (image_path, name)
        return image_file

    @staticmethod
    def _standardize_name(name):
        """
        Make sure use same standard for name, for example remove /dev/ from it if exists
        """
        if not name:
            _print("WARN: _standardize_name() - requires name as parameter")
            return None
        return name.replace("/dev/", "")

    def create_loopdev(self, name=None, size=1024):
        """
        Create a loop device
        Parameters:
        \tname:     eg. loop0 (optional)
        \tsize:     Size in MB (default: 1024MB)
        """

        ret_fail = False
        if not name:
            cmd = "losetup -f"
            retcode, output = run(cmd, return_output=True, verbose=False)
            if retcode != 0:
                _print("WARN: Could not find free loop device")
                print(output)
                return None
            name = output
            ret_fail = None
        name = self._standardize_name(name)

        fname = self._get_image_file(name, self.image_path)
        _print("INFO: Creating loop device %s with size %d" % (fname, size))

        _print("INFO: Checking if %s exists" % fname)
        if not os.path.isfile(fname):
            # make sure we have enough space to create the file
            free_space_bytes = get_free_space(self.image_path)
            # Convert the size given in megabytes to bytes
            size_bytes = int(size_human_2_size_bytes("%sMiB" % size))
            if free_space_bytes <= size_bytes:
                _print("WARN: Not enough space to create loop device with size %s"
                       % size_bytes_2_size_human(size_bytes))
                _print("available space: %s" % size_bytes_2_size_human(free_space_bytes))
                return ret_fail
            _print("INFO: Creating file %s" % fname)
            # cmd = "dd if=/dev/zero of=%s seek=%d bs=1M count=0" % (fname, size)
            cmd = "fallocate -l %sM %s" % (size, fname)
            try:
                # We are just creating the file, not writting zeros to it
                retcode = run(cmd)
                if retcode != 0:
                    _print("command failed with code %s" % retcode)
                    _print("WARN: Could not create loop device image file")
                    return ret_fail
            except OSError as e:
                print("command failed: ", e, file=sys.err)
                return ret_fail

        loop_path = self._get_loop_path(name)
        # detach loop device if it exists
        self.detach_loopdev(loop_path)

        # Going to associate the file to the loopdevice
        cmd = "losetup %s %s" % (loop_path, fname)
        retcode = run(cmd)
        if retcode != 0:
            _print("WARN: Could not create loop device")
            return ret_fail

        if ret_fail is None:
            return loop_path
        return True

    def delete_loopdev(self, name):
        """
        Delete a loop device
        Parameters:
        \tname:     eg. loop0 or /dev/loop0
        """
        if not name:
            _print("WARN: delete_loopdev() - requires name parameter")
            return False

        _print("INFO: Deleting loop device %s" % name)
        name = self._standardize_name(name)

        loop_path = self._get_loop_path(name)

        # detach loop device if it exists
        if not self.detach_loopdev(name):
            _print("WARN: could not detach %s" % loop_path)
            return False

        fname = self._get_image_file(name, self.image_path)
        if os.path.isfile(fname):
            cmd = "rm -f %s" % fname
            retcode = run(cmd)
            if retcode != 0:
                _print("WARN: Could not delete loop device %s" % name)
                return False

                # check if loopdev file is deleted as it sometimes remains
        if os.path.isfile(fname):
            _print("WARN: Deleted loop device file %s but it is still there" % fname)
            return False

        return True

    @staticmethod
    def get_loopdev():
        # example of output on rhel-6.7
        # /dev/loop0: [fd00]:396428 (/tmp/loop0.img)
        retcode, output = run("losetup -a | awk '{print$1}'", return_output=True, verbose=False)
        # retcode, output = run("losetup -l | tail -n +2", return_output=True, verbose=False)
        if (retcode != 0):
            _print("WARN: get_loopdev failed to execute")
            print(output)
            return None

        devs = None
        if output:
            devs = output.split("\n")
            # remove the ":" character from all devices
            devs = [d.replace(':', "") for d in devs]

        return devs

    def detach_loopdev(self, name=None):
        cmd = "losetup -D"
        if name:
            devs = self.get_loopdev()
            if not devs:
                # No device was found
                return False

            name = self._standardize_name(name)

            # Just try to detach if device is connected, otherwise ignore
            # print("INFO: Checking if ", loop_path, " exists, to be detached")
            dev_path = self._get_loop_path(name)
            if dev_path in devs:
                cmd = "losetup -d %s" % dev_path
            else:
                # if loop device does not exist just ignore it
                return True

        # run losetup -D or -d <device>
        retcode = run(cmd)
        if retcode != 0:
            _print("WARN: Could not detach loop device")
            return False

        return True


class LVM:
    ###########################################
    # VG section
    ###########################################
    @staticmethod
    def vg_query(verbose=False):
        """Query Volume Groups and return a dictonary with VG information for each VG.
        The arguments are:
        \tNone
        Returns:
        \tdict: Return a dictionary with VG info for each VG
        """
        cmd = "vgs --noheadings --separator \",\""
        retcode, output = run(cmd, return_output=True, verbose=verbose)
        if (retcode != 0):
            _print("INFO: there is no VGs")
            return None
        vgs = output.split("\n")

        # format of VG info: name #PV #LV #SN Attr VSize VFree
        vg_info_regex = "\s+(\S+),(\S+),(\S+),(.*),(.*),(.*),(.*)$"

        vg_dict = {}
        for vg in vgs:
            m = re.match(vg_info_regex, vg)
            if not m:
                continue
            vg_info_dict = {"num_pvs": m.group(2),
                            "num_lvs": m.group(3),
                            "num_sn": m.group(4),  # not sure what it is
                            "attr": m.group(5),
                            "vsize": m.group(6),
                            "vfree": m.group(7)}
            vg_dict[m.group(1)] = vg_info_dict

        return vg_dict

    @staticmethod
    def vg_create(vg_name, pv_name, force=False, verbose=True):
        """Create a Volume Group.
        The arguments are:
        \tPV name
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """
        if not vg_name or not pv_name:
            _print("WARN: vg_create requires vg_name and pv_name")
            return False

        options = ""
        if force:
            options += "--force"
        cmd = "vgcreate %s %s %s" % (options, vg_name, pv_name)
        retcode = run(cmd, verbose=verbose)
        if (retcode != 0):
            # _print("WARN: Could not create %s" % vg_name)
            return False
        return True

    def vg_remove(self, vg_name, force=False, verbose=True):
        """Delete a Volume Group.
        The arguments are:
        \tVG name
        \tforce (boolean)
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """
        if not vg_name:
            _print("WARN: vg_remove requires vg_name")
            return False

        vg_dict = self.vg_query()
        if vg_name not in vg_dict.keys():
            _print("INFO: vg_remove - %s does not exist. Skipping..." % vg_name)
            return True

        options = ""
        if force:
            options += "--force"
        cmd = "vgremove %s %s" % (options, vg_name)
        retcode = run(cmd, verbose=verbose)
        if (retcode != 0):
            return False
        return True

    ###########################################
    # LV section
    ###########################################
    @staticmethod
    def lv_query(options=None, verbose=False):
        """Query Logical Volumes and return a dictonary with LV information for each LV.
        The arguments are:
        \toptions:  If not want to use default lvs output. Use -o for no default fields
        Returns:
        \tdict: Return a list with LV info for each LV
        """
        # Use \",\" as separator, as some output might contain ','
        # For example, lvs -o modules on thin device returns "thin,thin-pool"
        cmd = "lvs -a --noheadings --separator \\\",\\\""

        # format of LV info: Name VG Attr LSize Pool Origin Data%  Meta%  Move Log Cpy%Sync Convert
        lv_info_regex = "\s+(\S+)\",\"(\S+)\",\"(\S+)\",\"(\S+)\",\"(.*)\",\"(.*)\",\"(.*)\",\"(.*)\",\"(.*)\",\"(.*)\",\"(.*)\",\"(.*)$"

        # default parameters returned by lvs -a
        param_names = ["name", "vg_name", "attr", "size", "pool", "origin", "data_per", "meta_per", "move", "log",
                       "copy_per", "convert"]

        if options:
            param_names = ["name", "vg_name"]
            # need to change default regex
            lv_info_regex = "\s+(\S+)\",\"(\S+)"
            parameters = options.split(",")
            for param in parameters:
                lv_info_regex += "\",\"(.*)"
                param_names.append(param)
            lv_info_regex += "$"
            cmd += " -o lv_name,vg_name,%s" % options

        retcode, output = run(cmd, return_output=True, verbose=verbose)
        if (retcode != 0):
            _print("INFO: there is no LVs")
            return None
        lvs = output.split("\n")

        lv_list = []
        for lv in lvs:
            m = re.match(lv_info_regex, lv)
            if not m:
                _print("WARN: (%s) does not match lvs output format" % lv)
                continue
            lv_info_dict = {}
            for index in range(len(param_names)):
                lv_info_dict[param_names[index]] = m.group(index + 1)
            lv_list.append(lv_info_dict)

        return lv_list

    def lv_info(self, lv_name, vg_name, options=None, verbose=False):
        """
        Show information of specific LV
        """
        if not lv_name or not vg_name:
            _print("WARN: lv_info() - requires lv_name and vg_name as parameters")
            return None

        lvs = self.lv_query(options=options, verbose=verbose)

        if not lvs:
            return None

        for lv in lvs:
            if (lv["name"] == lv_name and
                        lv["vg_name"] == vg_name):
                return lv
        return None

    @staticmethod
    def lv_create(vg_name, lv_name, options=(""), verbose=True):
        """Create a Logical Volume.
        The arguments are:
        \tVG name
        \tLV name
        \toptions
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """
        if not vg_name or not lv_name:
            _print("WARN: lv_create requires vg_name and lv_name")
            return False

        cmd = "lvcreate %s %s -n %s" % (" ".join(str(i) for i in options), vg_name, lv_name)
        retcode = run(cmd, verbose=verbose)
        if (retcode != 0):
            # _print("WARN: Could not create %s" % lv_name)
            return False
        return True

    @staticmethod
    def lv_activate(lv_name, vg_name, verbose=True):
        """Activate a Logical Volume
        The arguments are:
        \tLV name
        \tVG name
        Returns:
        \tBoolean:
        \t\tTrue in case of success
        \t\tFalse if something went wrong
        """
        if not lv_name or not vg_name:
            _print("WARN: lv_activate requires lv_name and vg_name")
            return False

        cmd = "lvchange -ay %s/%s" % (vg_name, lv_name)
        retcode = run(cmd, verbose=verbose)
        if (retcode != 0):
            _print("WARN: Could not activate LV %s" % lv_name)
            return False

        # Maybe we should query the LVs and make sure it is really activated
        return True

    @staticmethod
    def lv_deactivate(lv_name, vg_name, verbose=True):
        """Deactivate a Logical Volume
        The arguments are:
        \tLV name
        \tVG name
        Returns:
        \tBoolean:
        \t\tTrue in case of success
        \t\tFalse if something went wrong
        """
        if not lv_name or not vg_name:
            _print("WARN: lv_deactivate requires lv_name and vg_name")
            return False

        cmd = "lvchange -an %s/%s" % (vg_name, lv_name)
        retcode = run(cmd, verbose=verbose)
        if (retcode != 0):
            _print("WARN: Could not deactivate LV %s" % lv_name)
            return False

        # Maybe we should query the LVs and make sure it is really deactivated
        return True

    def lv_remove(self, lv_name, vg_name, verbose=True):
        """Remove an LV from a VG
        The arguments are:
        \tLV name
        \tVG name
        Returns:
        \tBoolean:
        \t\tTrue in case of success
        \t\tFalse if something went wrong
        """
        if not lv_name or not vg_name:
            _print("WARN: lv_remove requires lv_name and vg_name")
            return False

        lvs = self.lv_query()

        lv_names = lv_name.split()

        for lv_name in lv_names:
            if not self.lv_info(lv_name, vg_name):
                _print("INFO: lv_remove - LV %s does not exist. Skipping" % lv_name)
                continue

            cmd = "lvremove --force %s/%s" % (vg_name, lv_name)
            retcode = run(cmd, verbose=verbose)
            if (retcode != 0):
                _print("WARN: Could not remove LV %s" % lv_name)
                return False

            if self.lv_info(lv_name, vg_name):
                _print("INFO: lv_remove - LV %s still exists." % lv_name)
                return False

        return True

    @staticmethod
    def lv_convert(vg_name, lv_name, options, verbose=True):
        """Change Logical Volume layout.
        The arguments are:
        \tVG name
        \tLV name
        \toptions
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """
        if not options:
            _print("WARN: lv_convert requires at least some options specified.")
            return False

        if not lv_name or not vg_name:
            _print("WARN: lv_convert requires vg_name and lv_name")
            return False

        cmd = "lvconvert %s %s/%s" % (" ".join(options), vg_name, lv_name)
        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not convert %s" % lv_name)
            return False

        return True

    ###########################################
    # Config file
    ###########################################
    @staticmethod
    def get_config_file_path():
        return "/etc/lvm/lvm.conf"

    def update_config(self, key, value):
        config_file = self.get_config_file_path()
        search_regex = re.compile("(\s*)%s(\s*)=(\s*)\S*" % key)
        for line in fileinput.input(config_file, inplace=1):
            m = search_regex.match(line)
            if m:
                line = "%s%s = %s" % (m.group(1), key, value)
            # print saves the line to the file
            # need to remove new line character as print will add it
            line = line.rstrip('\n')
            print(line)


class DMPD:
    def __init__(self):
        self.lvm = LVM()

    def _get_devices(self):
        lv_list = self.lvm.lv_query()
        return lv_list

    @staticmethod
    def _get_active_devices():
        cmd = "ls /dev/mapper/"
        retcode, output = run(cmd, return_output=True, verbose=False)
        if retcode != 0:
            _print("WARN: Could not find active dm devices")
            return False
        devices = output.split()
        return devices

    @staticmethod
    def _get_device_path(vg_name, lv_name):
        device_path = vg_name + "-" + lv_name
        if "/dev/mapper/" not in device_path:
            device_path = "/dev/mapper/" + device_path
        return device_path

    def _check_device(self, vg_name, lv_name):
        devices = self._get_devices()
        device_list = [x["name"] for x in devices]
        if lv_name not in device_list:
            _print("WARN: %s is not a device" % lv_name)
            return False
        for x in devices:
            if x["name"] == lv_name and x["vg_name"] == vg_name:
                _print("INFO: Found device %s in group %s" % (lv_name, vg_name))
                return True
        return False

    def _activate_device(self, vg_name, lv_name):
        devices_active = self._get_active_devices()
        if vg_name + "-" + lv_name not in devices_active:
            ret = self.lvm.lv_activate(lv_name, vg_name)
            if not ret:
                _print("WARN: Could not activate device %s" % lv_name)
                return False
            _print("INFO: device %s was activated" % lv_name)
        _print("INFO: device %s is active" % lv_name)
        return True

    @staticmethod
    def _fallocate(_file, size, command_message):
        cmd = "fallocate -l %sM %s" % (size, _file)
        try:
            retcode = run(cmd)
            if retcode != 0:
                _print("WARN: Command failed with code %s." % retcode)
                _print("WARN: Could not create file to %s metadata to." % command_message)
                return False
        except OSError as e:
            print("command failed: ", e, file=sys.err)
            return False
        return True

    @staticmethod
    def get_help(cmd):
        commands = ["cache_check", "cache_dump", "cache_metadata_size", "cache_repair", "cache_restore", "era_check",
                    "era_dump", "era_invalidate", "era_restore", "thin_check", "thin_delta", "thin_dump", "thin_ls",
                    "thin_metadata_size", "thin_repair", "thin_restore", "thin_rmap", "thin_show_duplicates",
                    "thin_trim"]
        if cmd not in commands:
            _print("WARN: Unknown command %s" % cmd)
            return False

        command = "%s -h" % cmd
        retcode = run(command, verbose=True)
        if retcode != 0:
            _print("WARN: Could not get help for %s." % cmd)
            return False

        return True

    @staticmethod
    def get_version(cmd):
        commands = ["cache_check", "cache_dump", "cache_metadata_size", "cache_repair", "cache_restore", "era_check",
                    "era_dump", "era_invalidate", "era_restore", "thin_check", "thin_delta", "thin_dump", "thin_ls",
                    "thin_metadata_size", "thin_repair", "thin_restore", "thin_rmap", "thin_show_duplicates",
                    "thin_trim"]
        if cmd not in commands:
            _print("WARN: Unknown command %s" % cmd)
            return False

        command = "%s -V" % cmd
        retcode = run(command, verbose=True)
        if retcode != 0:
            _print("WARN: Could not get version of %s." % cmd)
            return False

        return True

    def _get_dev_id(self, dev_id, path=None, lv_name=None, vg_name=None):
        dev_ids = []

        if path is None:
            retcode, data = self.thin_dump(source_vg=vg_name, source_lv=lv_name, formatting="xml", return_output=True)
            if not retcode:
                _print("WARN: Could not dump metadata from %s/%s" % (vg_name, lv_name))
                return False
            data_lines = data.splitlines()
            for line in data_lines:
                blocks = line.split()
                for block in blocks:
                    if not block.startswith("dev_"):
                        continue
                    else:
                        dev_ids.append(int(block[8:-1]))

        else:
            with open(path, "r") as meta:
                for line in meta:
                    blocks = line.split()
                    for block in blocks:
                        if not block.startswith("dev_"):
                            continue
                        else:
                            dev_ids.append(int(block[8:-1]))

        if dev_id in dev_ids:
            return True

        return False

    @staticmethod
    def _metadata_size(source=None, lv_name=None, vg_name=None):
        if source is None:
            cmd = "lvs -a --units m"
            ret, data = run(cmd, return_output=True)
            if ret != 0:
                _print("WARN: Could not list LVs")
            data_line = data.splitlines()
            for line in data_line:
                cut = line.split()
                if not cut or lv_name != cut[0] and vg_name != cut[1]:
                    continue
                cut = cut[3]
                cut = cut.split("m")
                size = float(cut[0])
                cmd = "rm -f /tmp/meta_size"
                run(cmd)
                return int(size)
            _print("WARN: Could not find %s %s in lvs, setting size to 100m" % (lv_name, vg_name))
            return 100
        else:
            return int(os.stat(source).st_size) / 1000000

    ###########################################
    # cache section
    ###########################################

    def cache_check(self, source_file=None, source_vg=None, source_lv=None, quiet=False, super_block_only=False,
                    clear_needs_check_flag=False, skip_mappings=False, skip_hints=False, skip_discards=False,
                    verbose=True):
        """Check cache pool metadata from either file or device.
        The arguments are:
        \tsource_file
        \tsource_vg VG name
        \tsource_lv LV name
        \tquiet Mute STDOUT
        \tsuper_block_only
        \tclear_needs_check_flag
        \tskip_mappings
        \tskip_hints
        \tskip_discards
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        options = ""

        if not source_file and (not source_vg or not source_lv):
            _print("WARN: cache_check requires either source_file OR source_vg and source_lv.")
            return False

        if not source_file:
            ret = self._check_device(source_vg, source_lv)
            if not ret:
                return False
            ret = self._activate_device(source_vg, source_lv)
            if not ret:
                return False
            device = self._get_device_path(source_vg, source_lv)
        else:
            if not os.path.isfile(source_file):
                _print("WARN: Source file is not a file.")
                return False
            device = source_file

        if quiet:
            options += "--quiet "

        if super_block_only:
            options += "--super-block-only "

        if clear_needs_check_flag:
            options += "--clear-needs-check-flag "

        if skip_mappings:
            options += "--skip-mappings "

        if skip_hints:
            options += "--skip-hints "

        if skip_discards:
            options += "--skip-discards "

        cmd = "cache_check %s %s" % (device, options)
        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not check %s metadata" % device)
            return False

        return True

    def cache_dump(self, source_file=None, source_vg=None, source_lv=None, output=None, repair=False, verbose=True,
                   return_output=False):
        """Dumps cache metadata from device of source file to standard output or file.
        The arguments are:
        \tsource_file
        \tsource_vg VG name
        \tsource_lv LV name
        \toutput specify output xml file
        \treturn_output see 'Returns', not usable with output=True
        \trepair Repair the metadata while dumping it
        Returns:
        \tOnly Boolean if return_output False:
        \t\tTrue if success
        \t'tFalse in case of failure
        \tBoolean and data if return_output True
        """
        options = ""

        if return_output and output:
            _print("INFO: Cannot return to both STDOUT and file, returning only to file.")
            return_output = False

        if return_output:
            ret_fail = (False, None)
        else:
            ret_fail = False

        if not source_file and (not source_vg or not source_lv):
            _print("WARN: cache_dump requires either source_file OR source_vg and source_lv.")
            return ret_fail

        if not source_file:
            ret = self._check_device(source_vg, source_lv)
            if not ret:
                return ret_fail
            ret = self._activate_device(source_vg, source_lv)
            if not ret:
                return ret_fail
            device = self._get_device_path(source_vg, source_lv)
        else:
            if not os.path.isfile(source_file):
                _print("WARN: Source file is not a file.")
                return ret_fail
            device = source_file

        if output:
            if not os.path.isfile(output):
                size = self._metadata_size(source_file, source_lv, source_vg)
                ret = self._fallocate(output, size + 1, "dump")
                if not ret:
                    return ret_fail
            options += "-o %s " % output

        if repair:
            options += "--repair"

        cmd = "cache_dump %s %s" % (device, options)
        if return_output:
            retcode, data = run(cmd, return_output=True, verbose=verbose)
        else:
            retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not dump %s metadata." % device)
            return ret_fail

        if return_output:
            return True, data
        return True

    def cache_repair(self, source_file=None, source_vg=None, source_lv=None, target_file=None, target_vg=None,
                     target_lv=None, verbose=True):
        """Repairs cache metadata from source file/device to target file/device
        The arguments are:
        \tsource as either source_file OR source_vg and source_lv
        \ttarget as either target_file OR target_vg and target_lv
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        if not source_file and (not source_vg or not source_lv):
            _print("WARN: cache_repair requires either source_file OR source_vg and source_lv as source.")
            return False

        if not target_file and (not target_vg or not target_lv):
            _print("WARN: cache_repair requires either target_file OR target_vg and target_lv as target.")
            return False

        if not source_file:
            ret = self._check_device(source_vg, source_lv)
            if not ret:
                return False
            ret = self._activate_device(source_vg, source_lv)
            if not ret:
                return False
            source = self._get_device_path(source_vg, source_lv)
        else:
            if not os.path.isfile(source_file):
                _print("WARN: Source file is not a file.")
                return False
            source = source_file

        if not target_file:
            ret = self._check_device(target_vg, target_lv)
            if not ret:
                return False
            ret = self._activate_device(target_vg, target_lv)
            if not ret:
                return False
            target = self._get_device_path(target_vg, target_lv)
        else:
            if not os.path.isfile(target_file):
                size = self._metadata_size(source_file, source_lv, source_vg)
                ret = self._fallocate(target_file, size + 1, "repair")
                if not ret:
                    return False
            target = target_file

        cmd = "cache_repair -i %s -o %s" % (source, target)
        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not repair metadata from %s to %s" % (source, target))
            return False

        return True

    def cache_restore(self, source_file, target_vg=None, target_lv=None, target_file=None, quiet=False,
                      metadata_version=None, omit_clean_shutdown=False, override_metadata_version=None, verbose=True):
        """Restores cache metadata from source xml file to target device/file
        The arguments are:
        \tsource_file Source xml file
        \ttarget as either target_file OR target_vg and target_lv
        \tquiet Mute STDOUT
        \tmetadata_version Specify metadata version to restore
        \tomit_clean_shutdown Disable clean shutdown
        \toverride_metadata_version DEBUG option to override metadata version without checking
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        options = ""

        if source_file is None:
            _print("WARN: cache_restore requires source file.")
            return False

        if not target_file and (not target_vg or not target_lv):
            _print("WARN: cache_restore requires either target_file OR target_vg and target_lv as target.")
            return False

        if not os.path.isfile(source_file):
            _print("WARN: Source file is not a file.")
            return False

        if not target_file:
            ret = self._check_device(target_vg, target_lv)
            if not ret:
                return False
            ret = self._activate_device(target_vg, target_lv)
            if not ret:
                return False
            target = self._get_device_path(target_vg, target_lv)
        else:
            if not os.path.isfile(target_file):
                size = self._metadata_size(source_file)
                ret = self._fallocate(target_file, size + 1, "restore")
                if not ret:
                    return False
            target = target_file

        if quiet:
            options += "--quiet "

        if metadata_version:
            options += "--metadata-version %s " % metadata_version

        if omit_clean_shutdown:
            options += "--omit-clean-shutdown "

        if override_metadata_version:
            options += "--debug-override-metadata-version %s" % override_metadata_version

        cmd = "cache_restore -i %s -o %s %s" % (source_file, target, options)

        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not restore metadata from %s to %s" % (source_file, target))
            return False

        return True

    ###########################################
    # thinp section
    ###########################################

    def thin_check(self, source_file=None, source_vg=None, source_lv=None, quiet=False, super_block_only=False,
                   clear_needs_check_flag=False, skip_mappings=False, ignore_non_fatal_errors=False, verbose=True):
        """Check thin pool metadata from either file or device.
        The arguments are:
        \tsource_file
        \tsource_vg VG name
        \tsource_lv LV name
        \tquiet Mute STDOUT
        \tsuper_block_only
        \tclear_needs_check_flag
        \tskip_mappings
        \tignore_non_fatal_errors
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        options = ""

        if not source_file and (not source_vg or not source_lv):
            _print("WARN: thin_check requires either source_file OR source_vg and source_lv.")
            return False

        if not source_file:
            ret = self._check_device(source_vg, source_lv)
            if not ret:
                return False
            ret = self._activate_device(source_vg, source_lv)
            if not ret:
                return False
            device = self._get_device_path(source_vg, source_lv)
        else:
            if not os.path.isfile(source_file):
                _print("WARN: Source file is not a file.")
                return False
            device = source_file

        if quiet:
            options += "--quiet "

        if super_block_only:
            options += "--super-block-only "

        if clear_needs_check_flag:
            options += "--clear-needs-check-flag "

        if skip_mappings:
            options += "--skip-mappings "

        if ignore_non_fatal_errors:
            options += "--ignore-non-fatal-errors "

        cmd = "thin_check %s %s" % (device, options)
        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not check %s metadata" % device)
            return False

        return True

    def thin_ls(self, source_vg, source_lv, no_headers=False, fields=None, snapshot=False, verbose=True):
        """List information about thin LVs on thin pool.
        The arguments are:
        \tsource_vg VG name
        \tsource_lv LV name
        \tfields list of fields to output, default is all
        \tsnapshot If use metadata snapshot, able to run on live snapshotted pool
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        options = ""

        if not source_vg or not source_lv:
            _print("WARN: thin_ls requires source_vg and source_lv.")
            return False

        ret = self._check_device(source_vg, source_lv)
        if not ret:
            return False
        ret = self._activate_device(source_vg, source_lv)
        if not ret:
            return False
        device = self._get_device_path(source_vg, source_lv)

        if no_headers:
            options += "--no-headers "

        fields_possible = ["DEV", "MAPPED_BLOCKS", "EXCLUSIVE_BLOCKS", "SHARED_BLOCKS", "MAPPED_SECTORS",
                           "EXCLUSIVE_SECTORS", "SHARED_SECTORS", "MAPPED_BYTES", "EXCLUSIVE_BYTES", "SHARED_BYTES",
                           "MAPPED", "EXCLUSIVE", "TRANSACTION", "CREATE_TIME", "SHARED", "SNAP_TIME"]
        if fields is None:
            options += " --format \"%s\" " % ",".join([str(i) for i in fields_possible])
        else:
            for field in fields:
                if field not in fields_possible:
                    _print("WARN: Unknown field %s specified." % field)
                    _print("INFO: Possible fields are: %s" % ", ".join([str(i) for i in fields_possible]))
                    return False
            options += " --format \"%s\" " % ",".join([str(i) for i in fields])

        if snapshot:
            options += "--metadata-snap"

        cmd = "thin_ls %s %s" % (device, options)
        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not list %s metadata" % device)
            return False

        return True

    def thin_dump(self, source_file=None, source_vg=None, source_lv=None, output=None, repair=False, formatting=None,
                  snapshot=None, dev_id=None, skip_mappings=False, verbose=True, return_output=False):
        """Dumps thin metadata from device of source file to standard output or file.
        The arguments are:
        \tsource_file
        \tsource_vg VG name
        \tsource_lv LV name
        \toutput specify output xml file
        \treturn_output see 'Returns', not usable with output=True
        \trepair Repair the metadata while dumping it
        \tformatting Specify output format [xml, human_readable, custom='file']
        \tsnapshot (Boolean/Int) Use metadata snapshot. If Int provided, specifies block number
        \tdev_id ID of the device
        Returns:
        \tOnly Boolean if return_output False:
        \t\tTrue if success
        \t'tFalse in case of failure
        \tBoolean and data if return_output True
        """
        options = ""

        if return_output and output:
            _print("INFO: Cannot return to both STDOUT and file, returning only to file.")
            return_output = False

        if return_output:
            ret_fail = (False, None)
        else:
            ret_fail = False

        if not source_file and (not source_vg or not source_lv):
            _print("WARN: thin_dump requires either source_file OR source_vg and source_lv.")
            return ret_fail

        if not source_file:
            ret = self._check_device(source_vg, source_lv)
            if not ret:
                return ret_fail
            ret = self._activate_device(source_vg, source_lv)
            if not ret:
                return ret_fail
            device = self._get_device_path(source_vg, source_lv)
        else:
            if not os.path.isfile(source_file):
                _print("WARN: Source file is not a file.")
                return ret_fail
            device = source_file

        if output:
            if not os.path.isfile(output):
                size = self._metadata_size(source_file, source_lv, source_vg)
                ret = self._fallocate(output, size + 1, "dump")
                if not ret:
                    return ret_fail
            options += "-o %s " % output

        if repair:
            options += "--repair "

        if snapshot:
            if isinstance(snapshot, bool):
                options += "--metadata-snap "
            elif isinstance(snapshot, int):
                options += "--metadata-snap %s " % snapshot
            else:
                _print("WARN: Unknown snapshot value, use either Boolean or Int.")
                return ret_fail

        if formatting:
            if formatting in ["xml", "human_readable"]:
                options += "--format %s " % formatting
            elif formatting.startswith("custom="):
                if not os.path.isfile(formatting[8:-1]):
                    _print("WARN: Specified custom formatting file is not a file.")
                    return ret_fail
                options += "--format %s " % formatting
            else:
                _print("WARN: Unknown formatting specified, please use one of [xml, human_readable, custom='file'].")
                return ret_fail

        if dev_id:
            if isinstance(dev_id, int):
                if self._get_dev_id(dev_id, source_file, source_lv, source_vg):
                    options += "--dev-id %s " % dev_id
                else:
                    _print("WARN: Unknown dev_id value, device with ID %s does not exist." % dev_id)
                    return ret_fail
            else:
                _print("WARN: Unknown dev_id value, must be Int.")
                return ret_fail

        if skip_mappings:
            options += "--skip-mappings "

        cmd = "thin_dump %s %s" % (device, options)
        if return_output:
            retcode, data = run(cmd, return_output=True, verbose=verbose)
        else:
            retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not dump %s metadata." % device)
            return ret_fail

        if return_output:
            return True, data
        return True

    def thin_restore(self, source_file, target_vg=None, target_lv=None, target_file=None, quiet=False, verbose=True):
        """Restores thin metadata from source xml file to target device/file
        The arguments are:
        \tsource_file Source xml file
        \ttarget as either target_file OR target_vg and target_lv
        \tquiet Mute STDOUT
        \tmetadata_version Specify metadata version to restore
        \tomit_clean_shutdown Disable clean shutdown
        \toverride_metadata_version DEBUG option to override metadata version without checking
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        options = ""

        if source_file is None:
            _print("WARN: thin_restore requires source file.")
            return False

        if not target_file and (not target_vg or not target_lv):
            _print("WARN: thin_restore requires either target_file OR target_vg and target_lv as target.")
            return False

        if not os.path.isfile(source_file):
            _print("WARN: Source file is not a file.")
            return False

        if not target_file:
            ret = self._check_device(target_vg, target_lv)
            if not ret:
                return False
            ret = self._activate_device(target_vg, target_lv)
            if not ret:
                return False
            target = self._get_device_path(target_vg, target_lv)
        else:
            if not os.path.isfile(target_file):
                size = self._metadata_size(source_file)
                ret = self._fallocate(target_file, size + 1, "restore")
                if not ret:
                    return False
            target = target_file

        if quiet:
            options += "--quiet"

        cmd = "thin_restore -i %s -o %s %s" % (source_file, target, options)

        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not restore metadata from %s to %s" % (source_file, target))
            return False

        return True

    def thin_repair(self, source_file=None, source_vg=None, source_lv=None, target_file=None, target_vg=None,
                    target_lv=None, verbose=True):
        """Repairs thin metadata from source file/device to target file/device
        The arguments are:
        \tsource as either source_file OR source_vg and source_lv
        \ttarget as either target_file OR target_vg and target_lv
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        if not source_file and (not source_vg or not source_lv):
            _print("WARN: thin_repair requires either source_file OR source_vg and source_lv as source.")
            return False

        if not target_file and (not target_vg or not target_lv):
            _print("WARN: thin_repair requires either target_file OR target_vg and target_lv as target.")
            return False

        if not source_file:
            ret = self._check_device(source_vg, source_lv)
            if not ret:
                return False
            ret = self._activate_device(source_vg, source_lv)
            if not ret:
                return False
            source = self._get_device_path(source_vg, source_lv)
        else:
            if not os.path.isfile(source_file):
                _print("WARN: Source file is not a file.")
                return False
            source = source_file

        if not target_file:
            ret = self._check_device(target_vg, target_lv)
            if not ret:
                return False
            ret = self._activate_device(target_vg, target_lv)
            if not ret:
                return False
            target = self._get_device_path(target_vg, target_lv)
        else:
            if not os.path.isfile(target_file):
                size = self._metadata_size(source_file, source_lv, source_vg)
                ret = self._fallocate(target_file, size + 1, "repair")
                if not ret:
                    return False
            target = target_file

        cmd = "thin_repair -i %s -o %s" % (source, target)
        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not repair metadata from %s to %s" % (source, target))
            return False

        return True

    def thin_rmap(self, region, source_file=None, source_vg=None, source_lv=None, verbose=True):
        """Output reverse map of a thin provisioned region of blocks from metadata device.
        The arguments are:
        \tsource_vg VG name
        \tsource_lv LV name
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        if not source_file and (not source_vg or not source_lv):
            _print("WARN: thin_rmap requires either source_file OR source_vg and source_lv as source.")
            return False

        if not source_file:
            ret = self._check_device(source_vg, source_lv)
            if not ret:
                return False
            ret = self._activate_device(source_vg, source_lv)
            if not ret:
                return False
            device = self._get_device_path(source_vg, source_lv)
        else:
            if not os.path.isfile(source_file):
                _print("WARN: Source file is not a file.")
                return False
            device = source_file

        regions = region.split(".")
        try:
            int(regions[0])
            if regions[1] != '':
                raise ValueError
            int(regions[2])
            if regions[3] is not None:
                raise ValueError
        except ValueError:
            _print("WARN: Region must be in format 'INT..INT'")
            return False
        except IndexError:
            pass
        # region 1..-1 must be valid, using usigned 32bit ints
        if int(regions[0]) & 0xffffffff >= int(regions[2]) & 0xffffffff:
            _print("WARN: Beginning of the region must be before its end.")
            return False
        options = "--region %s" % region

        cmd = "thin_rmap %s %s" % (device, options)
        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not output reverse map from %s metadata device" % device)
            return False

        return True

    def thin_trim(self, target_vg, target_lv, force=True, verbose=True):
        """Issue discard requests for free pool space.
        The arguments are:
        \ttarget_vg VG name
        \ttarget_lv LV name
        \tforce suppress warning message and disable prompt, default True
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """
        options = ""

        if force:
            options += " --pool-inactive"

        if not target_vg or not target_lv:
            _print("WARN: thin_trim requires target_vg and target_lv.")
            return False

        ret = self._check_device(target_vg, target_lv)
        if not ret:
            return False

        ret = self._activate_device(target_vg, target_lv)
        if not ret:
            return False

        device = self._get_device_path(target_vg, target_lv)
        cmd = "thin_trim %s %s" % (device, options)
        retcode = run(cmd, verbose=verbose)
        if retcode != 0:
            _print("WARN: Could not discard free pool space on device %s." % device)
            return False

        return True

    def thin_delta(self, thin1, thin2, source_file=None, source_vg=None, source_lv=None, snapshot=False,
                   verbosity=False, verbose=True):
        """Print the differences in the mappings between two thin devices..
        The arguments are:
        \tsource_vg VG name
        \tsource_lv LV name
        \tthin1 numeric identificator of first thin volume
        \tthin2 numeric identificator of second thin volume
        \tsnapshot (Boolean/Int) Use metadata snapshot. If Int provided, specifies block number
        \tverbosity Provide extra information on the mappings
        Returns:
        \tBoolean:
        \t\tTrue if success
        \t'tFalse in case of failure
        """

        options = ""

        if not source_file and (not source_vg or not source_lv):
            _print("WARN: thin_delta requires either source_file OR source_vg and source_lv.")
            return False

        if not source_file:
            ret = self._check_device(source_vg, source_lv)
            if not ret:
                return False
            ret = self._activate_device(source_vg, source_lv)
            if not ret:
                return False
            device = self._get_device_path(source_vg, source_lv)
        else:
            if not os.path.isfile(source_file):
                _print("WARN: Source file is not a file.")
                return False
            device = source_file

        if snapshot:
            if isinstance(snapshot, bool):
                options += "--metadata-snap "
            elif isinstance(snapshot, int):
                options += "--metadata-snap %s " % snapshot
            else:
                _print("WARN: Unknown snapshot value, use either Boolean or Int.")
                return False

        if verbosity:
            options += "--verbose"

        if self._get_dev_id(thin1, source_file, source_lv, source_vg) and \
                self._get_dev_id(thin2, source_file, source_lv, source_vg):
            cmd = "thin_delta %s --thin1 %s --thin2 %s %s" % (options, thin1, thin2, device)
            retcode = run(cmd, verbose=verbose)
            if retcode != 0:
                _print("WARN: Could not get differences in mappings between two thin LVs.")
                return False
        else:
            _print("WARN: Specified ID does not exist.")
            return False
        return True
