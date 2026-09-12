#!/bin/bash

set -ex

# is alsactl present and working?
alsactl --version

# is amixer present and working?
amixer --help

# is alsamixer present and working?
alsamixer --version

# is amidi present and working?
amidi --version

# is speaker-test preset and working?
speaker-test -h

# aplay test (like for alsa-lib)
str=$(aplay -L | grep -E "^null$")
if [ "$str" != "null" ]; then
  echo "The 'null' pcm plugin was not found!"
  exit 99
fi

# alsa-info.sh present and working?
alsa-info.sh --help
