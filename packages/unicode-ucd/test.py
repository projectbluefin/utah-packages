#!/usr/bin/env python3

import sys

script_name = sys.argv[0]

try:
    filepath = sys.argv[1]
except IndexError:
    print(f"Usage: {script_name} <filepath>", file=sys.stderr)
    sys.exit(1)

codepoints = 0

with open(filepath, mode='rt', encoding='ascii') as unicode_data:
    for line in unicode_data.readlines():
        codepoint_string, name, category = line.split(';')[:3]
        codepoint = int(codepoint_string, 16)
        char = chr(codepoint)
        codepoints = codepoints + 1

print(codepoints)
# Unicode 18
assert(codepoints == 41341)
