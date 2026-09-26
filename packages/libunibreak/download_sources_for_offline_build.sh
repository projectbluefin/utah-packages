#!/bin/bash
#
# Upstream downloads a handful of Unicode files for the build
# and for testing.
#
# Run this script to get them for offline use and add them to
# the side cache.

ARCHIVE="libunibreak-test-data.tar.gz"

# Get current archive from side cache and unpack.
fedpkg sources
tar xzf ${ARCHIVE}

# Ensure timestamp of src/ doesn't differ across runs
touch -r src .timestamp

pushd src

# These are needed for regenerating src/*data.c
wget -Nc https://www.unicode.org/Public/UNIDATA/LineBreak.txt
wget -Nc https://www.unicode.org/Public/UNIDATA/auxiliary/WordBreakProperty.txt
wget -Nc https://www.unicode.org/Public/UNIDATA/auxiliary/GraphemeBreakProperty.txt
wget -Nc https://www.unicode.org/Public/UNIDATA/DerivedCoreProperties.txt
wget -Nc https://www.unicode.org/Public/UNIDATA/DerivedGeneralCategory.txt
wget -Nc https://www.unicode.org/Public/UNIDATA/EastAsianWidth.txt
wget -Nc https://www.unicode.org/Public/UNIDATA/emoji/emoji-data.txt


# These are needed for the tests.
# Upstream provides them, but also provides means of updating them, by means
# of fresh downloads from the Unicode website.
# However, we'd like to use upstream's version in order to ensure tests are
# working as intended. Uncomment, if needed.
#wget -Nc https://www.unicode.org/Public/UNIDATA/auxiliary/LineBreakTest.txt
#wget -Nc https://www.unicode.org/Public/UNIDATA/auxiliary/WordBreakTest.txt
#wget -Nc https://www.unicode.org/Public/UNIDATA/auxiliary/GraphemeBreakTest.txt

popd

# Set timestamp on src/
touch -c -r .timestamp src

# Create archive
if [ -f ${ARCHIVE} ]; then
    mv -vf ${ARCHIVE} ${ARCHIVE}.bak
fi

tar cvzf ${ARCHIVE} src/

rm -rvf src .timestamp

echo
echo "All files downloaded and archived."
echo "Don't forget to upload ${ARCHIVE} to the side cache."
echo
