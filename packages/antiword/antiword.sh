#!/bin/sh

# a shell wrapper to make 'antiword' usage reasonable on UTF-8 systems.
#
# Michal Jaegermann, michal@harddata.com, 2004/Nov/03
#    - simplify and we may be printing on a Postcript printer
#    - so do not use -i0, 2006/May/08

echo "$@" | egrep -q -- '-p|-a' && lang="env LANG=${LANG%%.*}"
$lang antiword.bin "$@"
exit
