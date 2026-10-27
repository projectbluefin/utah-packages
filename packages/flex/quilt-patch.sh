#!/bin/bash
# Patches are in the current directory.
export QUILT_PATCHES=$PWD
# Extract source file name from sources file,
# and assume it's the same name as the directory.
source=`awk -F '[() ]+'  '/^[A-Z0-9]+ /{print $2}; /^[0-9a-f]+ /{print $2}' sources`
srcdir=${source%.tar.gz}
if [ "$1" == "-f" ] && [ -d "$srcdir" ]; then
    echo Cleaning up $srcdir
    rm -rf $srcdir
fi
if [ -d "$srcdir" ]; then
    # Don't overwrite existing source directory.
    echo "ERROR: Source directory $srcdir already exists. Use -f to force cleanup step."
    exit 1
fi
tar xvf $source
echo "Entering $srcdir"
pushd $srcdir
# Apply all patches.
quilt push -a
popd
