#!/bin/sh

DIRNAME=mtdev-$( date +%Y%m%d )

rm -rf $DIRNAME
git clone http://bitmath.org/git/mtdev.git $DIRNAME
cd $DIRNAME
if [ -z "$1" ]; then
    git log | head -1
else
    git checkout $1
fi
git log | head -1 | awk '{ print $2 }' > ../commitid
git repack -a -d
cd ..
tar jcf $DIRNAME.tar.bz2 $DIRNAME
rm -rf $DIRNAME
