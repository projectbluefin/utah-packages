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

import sys, os
sys.path.append(os.path.abspath("dmpd_library.py"))

from dmpd_library import *

def thin_init(args):
    # Create thin pool with LVs
    print("INFO: Initializing test case")
    errors = []

    atomic_run("Creating loopdev",
               name=args["loop1"],
               size=args["loop1_size"],
               command=loopdev.create_loopdev,
               errors=errors)

    atomic_run("Creating VG",
               vg_name=args["group"],
               pv_name="/dev/" + args["loop1"],
               command=lvm.vg_create,
               errors=errors)

    atomic_run("Creating thin pool",
               vg_name=args["group"],
               lv_name=args["pool"],
               options=["-T", "-L 1500"],
               command=lvm.lv_create,
               errors=errors)

    # create few LVs to increase transaction ID and be able to do thin_delta
    for i in range(args["number of vols"]):
        atomic_run("Creating thin LV No. %s" % i,
                   vg_name=args["group"] + "/" + args["pool"],
                   lv_name=args["vol"] + str(i),
                   options=["-T", "-V 300"],
                   command=lvm.lv_create,
                   errors=errors)

        atomic_run("Creating filesystem on LV No. %s" % i,
                   vg_name=args["group"],
                   lv_name=args["vol"] + str(i),
                   command=create_filesystem,
                   errors=errors)

    atomic_run("Creating metadata snapshot",
               lv_name=args["pool"],
               vg_name=args["group"],
               command=metadata_snapshot,
               errors=errors)

    atomic_run("Creating swap LV",
               vg_name=args["group"],
               lv_name=args["swap"],
               options=["-L 300"],
               command=lvm.lv_create,
               errors=errors)

    atomic_run("Deactivating swap",
               lv_name=args["swap"],
               vg_name=args["group"],
               command=lvm.lv_deactivate,
               errors=errors)

    atomic_run("Deactivating pool",
               lv_name=args["pool"],
               vg_name=args["group"],
               command=lvm.lv_deactivate,
               errors=errors)

    for i in range(args["number of vols"]):
        atomic_run("Deactivating thin LV No. %s" % i,
                   lv_name=args["vol"] + str(i),
                   vg_name=args["group"],
                   command=lvm.lv_deactivate,
                   errors=errors)

    atomic_run("Swapping metadata",
               vg_name=args["group"],
               lv_name=args["swap"],
               options=["-y", "--thinpool " + args["group"] + "/" + args["pool"],
                        "--poolmetadata "],
               command=lvm.lv_convert,
               errors=errors)

    atomic_run("Activating swap",
               lv_name=args["swap"],
               vg_name=args["group"],
               command=lvm.lv_activate,
               errors=errors)

    if len(errors) == 0:
        TC.tpass("Initialization passed")
    else:
        TC.tfail("Initialization failed with following errors: \n\t'" +
                 "\n\t ".join([str(i) for i in errors]))
        return 1
    return 0


def thin_clean(args):
    print("INFO: Cleaning up")
    errors = []

    # restoring metadata device in case it is corrupted
    atomic_run("Repairing metadata device",
               source_file="/tmp/metadata",
               target_vg=args["group"],
               target_lv=args["swap"],
               quiet=True,
               command=dmpd.thin_restore,
               errors=errors)

    # thinpool got activated after checking its metadata to get bad checksum
    atomic_run("Deactivating pool",
               lv_name=args["pool"],
               vg_name=args["group"],
               command=lvm.lv_deactivate,
               errors=errors)

    atomic_run("Deactivating swap",
               lv_name=args["swap"],
               vg_name=args["group"],
               command=lvm.lv_deactivate,
               errors=errors)

    atomic_run("Swapping back metadata",
               vg_name=args["group"],
               lv_name=args["swap"],
               options=["-y", "--thinpool " + args["group"] + "/" + args["pool"],
                        "--poolmetadata "],
               command=lvm.lv_convert,
               errors=errors)

    atomic_run("Removing swap",
               lv_name=args["swap"],
               vg_name=args["group"],
               command=lvm.lv_remove,
               errors=errors)

    atomic_run("Removing thinpool",
               lv_name=args["pool"],
               vg_name=args["group"],
               command=lvm.lv_remove,
               errors=errors)

    atomic_run("Removing VG",
               vg_name=args["group"],
               force=True,
               command=lvm.vg_remove,
               errors=errors)

    atomic_run("Deleting loopdev",
               name=args["loop1"],
               command=loopdev.delete_loopdev,
               errors=errors)

    atomic_run("Deleting metadata file",
               cmd="rm -f /tmp/metadata",
               command=run,
               errors=errors)

    atomic_run("Deleting repair metadata file",
               cmd="rm -f /tmp/metadata_repair",
               command=run,
               errors=errors)

    atomic_run("Deleting snapshot metadata file",
               cmd="rm -f /tmp/metadata_snap",
               command=run,
               errors=errors)

    if len(errors) == 0:
        TC.tpass("Cleanup passed")
    else:
        TC.tfail("Cleanup failed with following errors: \n\t'" +
                 "\n\t ".join([str(i) for i in errors]))
        print(errors)
        return 1
    return 0

def thin_test(args):
    print("\n#######################################\n")
    print(
        "INFO: Testing thin tools runtime provided by device_mapper_persistent_data")

    errors = []

    atomic_run("Checking metadata",
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.thin_check,
               errors=errors)

    atomic_run("Checking metadata with few paramethers",
               source_vg=args["group"],
               source_lv=args["swap"],
               super_block_only=True,
               skip_mappings=True,
               ignore_non_fatal_errors=True,
               command=dmpd.thin_check,
               errors=errors)

    atomic_run("Listing information about thin LVs",
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.thin_ls,
               errors=errors)

    atomic_run("Listing information about thin LVs without headers",
               source_vg=args["group"],
               source_lv=args["swap"],
               no_headers=True,
               command=dmpd.thin_ls,
               errors=errors)

    # Not yet in Fedora 26, shoud be in F27
    #atomic_run("Dumping metadata to standard output without mappings",
    #           formatting="human_readable",
    #           source_vg=args["group"],
    #           source_lv=args["swap"],
    #           skip_mappings=True,
    #           command=dmpd.thin_dump,
    #           errors=errors)

    atomic_run("Dumping metadata to standard output",
               formatting="human_readable",
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.thin_dump,
               errors=errors)

    atomic_run("Dumping metadata to standard output from snapshot",
               formatting="human_readable",
               source_vg=args["group"],
               source_lv=args["swap"],
               snapshot=True,
               command=dmpd.thin_dump,
               errors=errors)

    # Not yet in Fedora 26, shoud be in F27
    #atomic_run("Dumping metadata with dev-id",
    #           formatting="human_readable",
    #           source_vg=args["group"],
    #           source_lv=args["swap"],
    #           dev_id=args["number of vols"] - 1,
    #           command=dmpd.thin_dump,
    #           errors=errors)

    atomic_run("Calculating metadata size for pool of 64k blocks and 100M size",
               cmd="thin_metadata_size -b64k -s100m -m1 -um",
               command=run,
               errors=errors)

    atomic_run("Calculating metadata size for pool of 64k blocks and 100M size",
               cmd="thin_metadata_size -b64k -s100m -m1 -um -n",
               command=run,
               errors=errors)

    atomic_run("Calculating metadata size for pool of 64k blocks and 100M size",
               cmd="thin_metadata_size -b64k -s100m -m1 -um -nlong",
               command=run,
               errors=errors)

    atomic_run("Calculating metadata size for pool of 64k blocks and 100M size",
               cmd="thin_metadata_size -b64k -s100m -m1 -um -nshort",
               command=run,
               errors=errors)

    atomic_run("Outputting reverse map of metadata device with negative number in region",
               False,
               source_vg=args["group"],
               source_lv=args["swap"],
               region="0..-1",
               command=dmpd.thin_rmap,
               errors=errors)

    # this fails now and it should not
    # atomic_run("Discarding free space of pool",
    #           target_vg=args["group"],
    #           target_lv=args["swap"],
    #           command=dmpd.thin_trim,
    #           errors=errors)

    atomic_run("Dumping metadata to file",
               formatting="xml",
               source_vg=args["group"],
               source_lv=args["swap"],
               repair=True,
               output="/tmp/metadata",
               command=dmpd.thin_dump,
               errors=errors)

    atomic_run("Dumping metadata to file from snapshot",
               formatting="xml",
               source_vg=args["group"],
               source_lv=args["swap"],
               snapshot=True,
               output="/tmp/metadata_snap",
               command=dmpd.thin_dump,
               errors=errors)

    atomic_run("Getting differences between thin LVs",
               source_vg=args["group"],
               source_lv=args["swap"],
               thin1=1,
               thin2=args["number of vols"] - 1,
               snapshot=True,
               command=dmpd.thin_delta,
               errors=errors)

    atomic_run("Getting differences between thin LVs with --verbose",
               source_vg=args["group"],
               source_lv=args["swap"],
               thin1=1,
               thin2=args["number of vols"] - 1,
               verbosity=True,
               snapshot=True,
               command=dmpd.thin_delta,
               errors=errors)

    atomic_run("Getting differences between the same LV",
               source_vg=args["group"],
               source_lv=args["swap"],
               thin1=1,
               thin2=1,
               snapshot=True,
               command=dmpd.thin_delta,
               errors=errors)

    atomic_run("Getting differences between the same LV with --verbose",
               source_vg=args["group"],
               source_lv=args["swap"],
               thin1=1,
               thin2=1,
               verbosity=True,
               snapshot=True,
               command=dmpd.thin_delta,
               errors=errors)

    atomic_run("Listing metadata output from snapshot",
               source_vg=args["group"],
               source_lv=args["swap"],
               snapshot=True,
               command=dmpd.thin_ls,
               errors=errors)

    # Need to run everything on snapshot before this as thin_restore removes the metadata snapshot
    # This should work but is not working due to a bug
    #atomic_run("Restoring metadata",
    #           source_file="/tmp/metadata_snap",
    #           target_vg=args["group"],
    #           target_lv=args["swap"],
    #           command=dmpd.thin_restore,
    #           errors=errors)

    atomic_run("Restoring metadata",
               source_file="/tmp/metadata",
               target_vg=args["group"],
               target_lv=args["swap"],
               command=dmpd.thin_restore,
               errors=errors)

    #   Repairing from non-binary file leads to segmentation fault
    #atomic_run("Repairing metadata from file",
    #            source_file="/tmp/metadata",
    #            target_vg=args["group"],
    #            target_lv=args["swap"],
    #            command=dmpd.thin_repair,
    #            errors=errors)

    atomic_run("Repairing metadata to file",
               target_file="/tmp/metadata_repair",
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.thin_repair,
               errors=errors)

    atomic_run("Repairing metadata from file",
               source_file="/tmp/metadata_repair",
               target_vg=args["group"],
               target_lv=args["swap"],
               command=dmpd.thin_repair,
               errors=errors)

    atomic_run("Checking metadata",
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.thin_check,
               errors=errors)

    print("\n#######################################\n")

    if len(errors) == 0:
        TC.tpass("Testing thin tools of device_mapper_persistent_data passed")
    else:
        TC.tfail("Testing thin tools of device_mapper_persistent_data failed with following errors: \n\t'" +
                 "\n\t ".join([str(i) for i in errors]))
        return 1
    return 0


def thin_errors_test(args):
    print("\n#######################################\n")
    print(
        "INFO: Testing thin tools errors provided by device_mapper_persistent_data")

    errors = []

    # "thin_show_duplicates" does not work yet
    functions = ["thin_check", "thin_delta", "thin_dump", "thin_ls", "thin_metadata_size", "thin_repair",
                 "thin_restore", "thin_rmap", "thin_trim"]

    # Sanity to check for missing input
    for func in functions:
        atomic_run("Validating missing input",
                   False,
                   cmd=func,
                   command=run,
                   errors=errors)

    # Sanity to check with wrong input
    for func in functions:
        atomic_run("Validating wrong input",
                   False,
                   cmd=func + " wrong",
                   command=run,
                   errors=errors)

    # Sanity to check with wrong option
    for func in functions:
        atomic_run("Validating wrong option",
                   False,
                   cmd=func + " -wrong",
                   command=run,
                   errors=errors)

    # Sanity to check present functions with -h
    for func in functions:
        atomic_run("Checking help of command",
                   cmd=func,
                   command=dmpd.get_help,
                   errors=errors)

    # Sanity to check present functions with -V
    for func in functions:
        # thin_metadata_size has wrong return value
        if func == "thin_metadata_size":
            continue
        atomic_run("Checking version of command",
                   cmd=func,
                   command=dmpd.get_version,
                   errors=errors)

    atomic_run("Checking original pool metadata, should fail",
               False,
               source_vg=args["group"],
               source_lv=args["pool"],
               command=dmpd.thin_check,
               errors=errors)

    atomic_run("Listing information about thin LVs",
               False,
               cmd="thin_ls /dev/mapper/%s-%s --format \"WRONG\"" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Checking thin_metadata_size inputs",
               False,
               cmd="thin_metadata_size -b 64",
               command=run,
               errors=errors)

    atomic_run("Checking thin_metadata_size inputs",
               False,
               cmd="thin_metadata_size -b 64 -s 128",
               command=run,
               errors=errors)

    atomic_run("Checking thin_metadata_size inputs",
               False,
               cmd="thin_metadata_size -b 25 -s 128 -m 10",
               command=run,
               errors=errors)

    atomic_run("Checking thin_metadata_size inputs",
               False,
               cmd="thin_metadata_size -b 128 -s 64 -m 10",
               command=run,
               errors=errors)

    atomic_run("Checking thin_metadata_size inputs",
               False,
               cmd="thin_metadata_size -u h",
               command=run,
               errors=errors)

    atomic_run("Checking thin_metadata_size inputs",
               False,
               cmd="thin_metadata_size -n -n",
               command=run,
               errors=errors)

    atomic_run("Checking thin_metadata_size inputs",
               False,
               cmd="thin_metadata_size -nlongshort",
               command=run,
               errors=errors)

    atomic_run("Checking thin_metadata_size inputs",
               False,
               cmd="thin_metadata_size -b 128 -b 64",
               command=run,
               errors=errors)

    atomic_run("Repairing metadata without output",
               False,
               cmd="thin_repair -i /tmp/metadata_repair",
               command=run,
               errors=errors)

    atomic_run("Dumping metadata with wrong custom format",
               False,
               cmd="thin_dump /dev/mapper/%s-%s --format custom=wrong" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Dumping metadata with unknown format",
               False,
               cmd="thin_dump /dev/mapper/%s-%s --format wrong" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Dumping metadata with wrong dev-id",
               False,
               cmd="thin_dump /dev/mapper/%s-%s --dev-id wrong" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Repairing metadata to produce 'output file does not exist' error",
               False,
               cmd="thin_repair -i /dev/mapper/%s-%s -o /tmp/wrong.wrong" %
                   (args['group'], args['swap']),
               command=run,
               errors=errors)

    atomic_run("Repairing metadata to produce 'output file too small' error",
               False,
               cmd="thin_repair -i /tmp/metadata -o /tmp/metadata",
               command=run,
               errors=errors)

    # This does not fail now due to a bug
    #atomic_run("Outputting reverse map of metadata device, should fail without region",
    #           cmd="thin_rmap /dev/mapper/%s-%s" % (args["group"], args["swap"]),
    #           command=run,
    #           errors=errors)

    atomic_run("Outputting reverse map of metadata device with wrong region",
               False,
               cmd="thin_rmap /dev/mapper/%s-%s --region 0..0" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Outputting reverse map of metadata device with wrong region",
               False,
               cmd="thin_rmap /dev/mapper/%s-%s --region 0...1" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Outputting reverse map of metadata device with wrong region",
               False,
               cmd="thin_rmap /dev/mapper/%s-%s --region 00" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Outputting reverse map of metadata device with wrong device",
               False,
               cmd="thin_rmap --region 0..-1 /tmp/wrong.wrong",
               command=run,
               errors=errors)

    #   Reverse mapping from bad file leads to segmentation fault
    #atomic_run("Outputting reverse map of metadata device with wrong device",
    #            False,
    #            cmd="thin_rmap --region 0..-1 /tmp/metadata",
    #            command=run,
    #            errors=errors)

    atomic_run("Getting differences with thin1 ID out of range",
               False,
               source_vg=args["group"],
               source_lv=args["swap"],
               thin1=-1,
               thin2=args["number of vols"] - 1,
               command=dmpd.thin_delta,
               errors=errors)

    atomic_run("Getting differences with thin2 ID out of range",
               False,
               source_vg=args["group"],
               source_lv=args["swap"],
               thin1=1,
               thin2=args["number of vols"] + 1,
               command=dmpd.thin_delta,
               errors=errors)

    atomic_run("Restoring metadata without output",
               False,
               cmd="thin_restore -i /tmp/metadata",
               command=run,
               errors=errors)

    atomic_run("Restoring metadata with wrong options",
               False,
               cmd="thin_restore -i /tmp/metadata -o /dev/mapper/%s-%s --wrong test" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Restoring metadata with wrong source",
               False,
               cmd="thin_restore -i /tmp/wrong.wrong -o /dev/mapper/%s-%s" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Getting differences without thin2",
               False,
               cmd="thin_delta --thin1 1 /dev/mapper/%s-%s" %
                   (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Corrupting metadata on device",
               cmd="echo 'nothing' >> /dev/mapper/%s-%s" %
                   (args['group'], args['swap']),
               command=run,
               errors=errors)

    atomic_run("Trying to fail while repairing metadata",
               False,
               source_vg=args['group'],
               source_lv=args['swap'],
               target_file="/tmp/metadata_repair",
               command=dmpd.thin_repair,
               errors=errors)

    atomic_run("Trying to fail listing volumes",
               False,
               source_vg=args['group'],
               source_lv=args['swap'],
               command=dmpd.thin_ls,
               errors=errors)

    atomic_run("Trying to fail while checking metadata",
               False,
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.thin_check,
               errors=errors)

    atomic_run("Trying to fail while dumping metadata from snapshot",
               False,
               formatting="human_readable",
               source_vg=args["group"],
               source_lv=args["swap"],
               snapshot=True,
               command=dmpd.thin_dump,
               errors=errors)

    # restoring metadata device after corrupting it
    atomic_run("Repairing metadata device",
               source_file="/tmp/metadata",
               target_vg=args["group"],
               target_lv=args["swap"],
               quiet=True,
               command=dmpd.thin_restore,
               errors=errors)

    print("\n#######################################\n")

    if len(errors) == 0:
        TC.tpass("Testing thin tools errors of device_mapper_persistent_data passed")
    else:
        TC.tfail("Testing thin tools errors of device_mapper_persistent_data failed with following errors: \n\t'" +
                 "\n\t ".join([str(i) for i in errors]))
        return 1
    return 0


def cache_init(args):
    print("INFO: Initializing test case")
    errors = []

    atomic_run("Creating loopdev 1 - 'fast' device",
               name=args["loop1"],
               size=args["loop1_size"],
               command=loopdev.create_loopdev,
               errors=errors)

    atomic_run("Creating loopdev 2 - 'slow' device",
               name=args["loop2"],
               size=args["loop2_size"],
               command=loopdev.create_loopdev,
               errors=errors)

    atomic_run("Creating VG",
               vg_name=args["group"],
               pv_name="/dev/" + args["loop1"] +
                       " /dev/" + args["loop2"],
               command=lvm.vg_create,
               errors=errors)

    atomic_run("Creating cache metadata volume",
               vg_name=args["group"] + " /dev/" + args["loop1"],
               lv_name=args["meta"],
               options=["-L 12"],
               command=lvm.lv_create,
               errors=errors)

    atomic_run("Creating origin volume",
               vg_name=args["group"] + " /dev/" + args["loop2"],
               lv_name=args["origin"],
               options=["-L 2G"],
               command=lvm.lv_create,
               errors=errors)

    atomic_run("Creating cache data volume",
               vg_name=args["group"] + " /dev/" + args["loop1"],
               lv_name=args["data"],
               options=["-L 1G"],
               command=lvm.lv_create,
               errors=errors)

    atomic_run("Creating cache pool",
               vg_name=args["group"],
               lv_name=args["data"],
               options=["-y --type cache-pool", "--cachemode writeback", "--poolmetadata %s/%s" %
                       (args["group"], args["meta"])],
               command=lvm.lv_convert,
               errors=errors)

    atomic_run("Creating cache logical volume",
               vg_name=args["group"],
               lv_name=args["origin"],
               options=["-y", "--type cache", "--cachepool %s/%s" %
                       (args["group"], args["data"])],
               command=lvm.lv_convert,
               errors=errors)

    atomic_run("Creating filesystem on cache logical volume",
               vg_name=args["group"],
               lv_name=args["origin"],
               command=create_filesystem,
               errors=errors)

    atomic_run("Splitting cache logical volume",
               vg_name=args["group"],
               lv_name=args["origin"],
               options=["-y", "--splitcache"],
               command=lvm.lv_convert,
               errors=errors)

    atomic_run("Creating swap LV",
               vg_name=args["group"],
               lv_name=args["swap"],
               options=["-L 100"],
               command=lvm.lv_create,
               errors=errors)

    atomic_run("Swapping metadata",
               vg_name=args["group"],
               lv_name=args["swap"],
               options=["-y", "--cachepool " + args["group"] + "/" + args["data"],
                        "--poolmetadata "],
               command=lvm.lv_convert,
               errors=errors)

    atomic_run("Activating swap",
               lv_name=args["swap"],
               vg_name=args["group"],
               command=lvm.lv_activate,
               errors=errors)

    if len(errors) == 0:
        TC.tpass("Initialization passed")
    else:
        TC.tfail("Initialization failed with following errors: \n\t'" +
                 "\n\t ".join([str(i) for i in errors]))
        return 1
    return 0


def cache_clean(args):
    print("INFO: Cleaning up")
    errors = []

    atomic_run("Removing VG",
               vg_name=args["group"],
               force=True,
               command=lvm.vg_remove,
               errors=errors)

    atomic_run("Deleting loopdev loop1",
               name=args["loop1"],
               command=loopdev.delete_loopdev,
               errors=errors)

    atomic_run("Deleting loopdev loop2",
               name=args["loop2"],
               command=loopdev.delete_loopdev,
               errors=errors)

    atomic_run("Deleting metadata file",
               cmd="rm -f /tmp/metadata",
               command=run,
               errors=errors)

    atomic_run("Deleting repair metadata file",
               cmd="rm -f /tmp/metadata_repair",
               command=run,
               errors=errors)

    if len(errors) == 0:
        TC.tpass("Cleanup passed")
    else:
        TC.tfail("Cleanup failed with following errors: \n\t'" +
                 "\n\t ".join([str(i) for i in errors]))
        print(errors)
        return 1
    return 0


def cache_test(args):
    print("\n#######################################\n")
    print("INFO: Testing cache tools runtime provided by device_mapper_persistent_data")

    errors = []

    atomic_run("Checking metadata",
               source_lv=args["swap"],
               source_vg=args["group"],
               command=dmpd.cache_check,
               errors=errors)

    atomic_run("Checking metadata with clear-need-check-flag",
               source_lv=args["swap"],
               source_vg=args["group"],
               clear_needs_check_flag=True,
               command=dmpd.cache_check,
               errors=errors)

    atomic_run("Checking metadata with super-block-only",
               source_lv=args["swap"],
               source_vg=args["group"],
               super_block_only=True,
               command=dmpd.cache_check,
               errors=errors)

    atomic_run("Checking metadata with few paramethers",
               source_vg=args["group"],
               source_lv=args["swap"],
               skip_discards=True,
               skip_mappings=True,
               skip_hints=True,
               command=dmpd.cache_check,
               errors=errors)

    atomic_run("Dumping metadata to standard output",
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.cache_dump,
               errors=errors)

    atomic_run("Calculating metadata size for cache of 64 blocks and 128 size",
               cmd="cache_metadata_size --block-size 64 --device-size 128",
               command=run,
               errors=errors)

    atomic_run("Calculating metadata size for cache of 128 nr blocks",
               cmd="cache_metadata_size --nr-blocks 128 --max-hint-width 4",
               command=run,
               errors=errors)

    atomic_run("Dumping metadata to file",
               source_vg=args["group"],
               source_lv=args["swap"],
               repair=True,
               output="/tmp/metadata",
               command=dmpd.cache_dump,
               errors=errors)

    # Not yet in Fedora 26, shoud be in F27
    #atomic_run("Checking metadata file",
    #           source_file="/tmp/metadata",
    #           command=dmpd.cache_check,
    #           errors=errors)
    #
    #atomic_run("Restoring metadata with options",
    #           source_file="/tmp/metadata",
    #           target_vg=args["group"],
    #           target_lv=args["swap"],
    #           quiet=True,
    #           override_metadata_version=1,
    #           metadata_version=1,
    #           command=dmpd.cache_restore,
    #           errors=errors)

    atomic_run("Restoring metadata from file",
               source_file="/tmp/metadata",
               target_vg=args["group"],
               target_lv=args["swap"],
               command=dmpd.cache_restore,
               errors=errors)

    atomic_run("Repairing metadata to file",
               target_file="/tmp/metadata_repair",
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.cache_repair,
               errors=errors)

    atomic_run("Repairing metadata from file",
               source_file="/tmp/metadata_repair",
               target_vg=args["group"],
               target_lv=args["swap"],
               command=dmpd.cache_repair,
               errors=errors)

    atomic_run("Simulating TTY for cache_restore",
               cmd="script --return -c 'cache_restore -i /tmp/metadata -o /dev/mapper/%s-%s' /dev/null" %
                   (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Checking metadata",
               source_vg=args["group"],
               source_lv=args["swap"],
               quiet=True,
               command=dmpd.cache_check,
               errors=errors)

    print("\n#######################################\n")

    if len(errors) == 0:
        TC.tpass("Testing cache tools of device_mapper_persistent_data passed")
    else:
        TC.tfail("Testing cache tools of device_mapper_persistent_data failed with following errors: \n\t'" +
                 "\n\t ".join([str(i) for i in errors]))
        return 1
    return 0


def cache_errors_test(args):
    print("\n#######################################\n")
    print("INFO: Testing cache tools errors provided by device_mapper_persistent_data")

    errors = []

    functions = ["cache_check", "cache_dump", "cache_metadata_size", "cache_repair", "cache_restore"]

    # Sanity to check for missing input
    for func in functions:
        atomic_run("Validating missing input",
                   False,
                   cmd=func,
                   command=run,
                   errors=errors)

    # Sanity to check with wrong input
    for func in functions:
        atomic_run("Validating wrong input",
                   False,
                   cmd=func + " wrong",
                   command=run,
                   errors=errors)

    # Sanity to check with wrong option
    for func in functions:
        atomic_run("Validating wrong option",
                   False,
                   cmd=func + " -wrong",
                   command=run,
                   errors=errors)

    # Sanity to check with wrong -- option
    for func in functions:
        atomic_run("Validating wrong -- option",
                   False,
                   cmd=func + " --wrong",
                   command=run,
                   errors=errors)

    # Sanity to check present functions with -h
    for func in functions:
        atomic_run("Checking help of command",
                   cmd="%s" % func,
                   command=dmpd.get_help,
                   errors=errors)

    # Sanity to check present functions with -V
    for func in functions:
        atomic_run("Checking version of command",
                   cmd="%s" % func,
                   command=dmpd.get_version,
                   errors=errors)

    atomic_run("Checking metadata of non-metadata file",
               False,
               cmd="cache_check README",
               command=run,
               errors=errors)

    atomic_run("Checking metadata of non-existent file",
               False,
               cmd="cache_check WRONG",
               command=run,
               errors=errors)

    atomic_run("Checking metadata of non-regular file",
               False,
               cmd="cache_check /dev/mapper/control",
               command=run,
               errors=errors)

    atomic_run("Calculating metadata size for cache of 64 blocks",
               False,
               cmd="cache_metadata_size --block-size 64",
               command=run,
               errors=errors)

    atomic_run("Calculating metadata size for cache of 128 size",
               False,
               cmd="cache_metadata_size --device-size 128",
               command=run,
               errors=errors)

    atomic_run("Calculating metadata size for cache of 64 blocks and 128 size and 128 nr blocks",
               False,
               cmd="cache_metadata_size --block-size 64 --device-size 128 --nr-blocks 128",
               command=run,
               errors=errors)

    atomic_run("Repairing metadata without output",
               False,
               cmd="cache_repair -i /tmp/metadata_repair",
               command=run,
               errors=errors)

    atomic_run("Restoring metadata with wrong options",
               False,
               cmd="cache_restore -i /tmp/metadata -o /dev/mapper/%s-%s --wrong test" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Restoring metadata with wrong metadata version",
               False,
               source_file="/tmp/metadata",
               target_vg=args["group"],
               target_lv=args["swap"],
               metadata_version=12445,
               command=dmpd.cache_restore,
               errors=errors)

    atomic_run("Restoring metadata with wrong source",
               False,
               cmd="cache_restore -i /tmp/wrong.wrong -o /dev/mapper/%s-%s" % (args["group"], args["swap"]),
               command=run,
               errors=errors)

    atomic_run("Restoring metadata with bit source",
               False,
               source_file="/tmp/metadata_repair",
               target_vg=args["group"],
               target_lv=args["swap"],
               command=dmpd.cache_restore,
               errors=errors)

    atomic_run("Restoring metadata without output",
               False,
               cmd="cache_restore -i /tmp/metadata",
               command=run,
               errors=errors)

    # I am not able to run cache_restore with --omit-clean-shutdown successfully
    #atomic_run("Restoring metadata with options",
    #           source_file="/tmp/metadata",
    #           target_vg=args["group"],
    #           target_lv=args["swap"],
    #           omit_clean_shutdown=True,
    #           command=dmpd.cache_restore,
    #           errors=errors)

    # This fails in Fedora 26, should work in F27
    #atomic_run("Checking metadata",
    #           source_vg=args["group"],
    #           source_lv=args["swap"],
    #           command=dmpd.cache_check,
    #           errors=errors)

    #FIXME: Find other way to corrupt metadata, this exploits a bug
    """
    atomic_run("Corrupting mappings on metadata device",
               False,
               source_file="Makefile",
               target_vg=args["group"],
               target_lv=args["swap"],
               command=dmpd.cache_restore,
               errors=errors)

    atomic_run("Checking corrupted mappings",
               False,
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.cache_check,
               errors=errors)

    atomic_run("Trying to fail while dumping metadata",
               False,
               source_vg=args['group'],
               source_lv=args['swap'],
               output="/tmp/metadata",
               command=dmpd.cache_dump,
               errors=errors)

    atomic_run("Repairing metadata",
               source_vg=args['group'],
               source_lv=args['swap'],
               target_file="/tmp/metadata_repair",
               command=dmpd.cache_repair,
               errors=errors)"""

    atomic_run("Corrupting metadata on device",
               cmd="echo 'nothing' >> /dev/mapper/%s-%s" % (args['group'], args['swap']),
               command=run,
               errors=errors)

    atomic_run("Trying to fail while repairing metadata",
               False,
               source_vg=args['group'],
               source_lv=args['swap'],
               target_file="/tmp/metadata_repair",
               command=dmpd.cache_repair,
               errors=errors)

    atomic_run("Trying to fail while dumping metadata",
               False,
               source_vg=args['group'],
               source_lv=args['swap'],
               output="/tmp/metadata",
               command=dmpd.cache_dump,
               errors=errors)

    atomic_run("Checking corrupted metadata",
               False,
               source_vg=args["group"],
               source_lv=args["swap"],
               command=dmpd.cache_check,
               errors=errors)


    print("\n#######################################\n")

    if len(errors) == 0:
        TC.tpass("Testing cache tools errors of device_mapper_persistent_data passed")
    else:
        TC.tfail("Testing cache tools errors of device_mapper_persistent_data failed with following errors: \n\t'" +
                 "\n\t ".join([str(i) for i in errors]))
        return 1
    return 0


def main():
    # Initialize Test Case
    global TC
    TC = TestClass()

    # Initialize library classes
    global loopdev
    global lvm
    global dmpd
    loopdev = LoopDev()
    lvm = LVM()
    dmpd = DMPD()

    args = {"loop1": "loop1",
            "loop1_size": 2048,
            "loop2": "loop2",
            "loop2_size": 4128,
            "group": "vgtest",
            "origin": "origin",
            "data": "cache_data",
            "meta": "cache_meta",
            "pool": "pool",
            "vol": "thinvol",
            "number of vols": 10,
            "swap": "swapvol"}

    # Initialization
    install_package("lvm2")
    install_package("device-mapper-persistent-data")

    # Tests for thin tools provided by device-mapper-persistent-data
    thin_init(args)
    thin_test(args)
    thin_errors_test(args)
    thin_clean(args)

    # Tests for cache tools provided by device-mapper-persistent-data
    cache_init(args)
    cache_test(args)
    cache_errors_test(args)
    cache_clean(args)

    if not TC.tend():
        print("FAIL: test failed")
        sys.exit(1)

    print("PASS: Test pass")
    sys.exit(0)


if __name__ == "__main__":
    main()
