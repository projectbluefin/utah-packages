#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Nicolas Chauvet <kwizart@gmail.com>
# Copyright (C) 2026 Simone Caronni <negativ17@gmail.com>
# Licensed under the GNU General Public License Version or later

import sys
import xml.etree.ElementTree as ElementTree

if len(sys.argv) != 3:
    sys.exit("usage: %s src/i965_pciids.h com.intel.vaapi_driver.metainfo.xml" % sys.argv[0])

# open file
f = open(sys.argv[1])
pids = []
for line in f.readlines():

    # remove Windows and Linux line endings
    line = line.replace('\r', '')
    line = line.replace('\n', '')

    # Only look at line with CHIPSET
    if len(line) > 0 and not line.startswith('CHIPSET'):
        continue

    # empty line
    if len(line) == 0:
        continue

    # get name
    pid = int(line[10:14], 16)
    if not pid in pids:
        pids.append(pid)

# output
appstream_xml = ElementTree.parse(sys.argv[2])
root = appstream_xml.getroot()
provides = ElementTree.SubElement(root, "provides")

for pid in pids:
    vid = 0x8086
    modalias = ElementTree.SubElement(provides, "modalias")
    modalias.text = "pci:v%08Xd%08Xsv*sd*bc*sc*i*" % (vid, pid)

ElementTree.indent(root, space="  ", level=0)
# appstream-util validate requires the xml header
appstream_xml.write(sys.argv[2], encoding="utf-8", xml_declaration=True)
