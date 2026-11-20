#!/bin/bash

set -ex

# install speaker-test
dnf install -y alsa-utils

# create patest user
adduser patest

# run pulseaudio daemon
su - patest -c "pulseaudio --start --log-target=stderr"

# run pulseaudio test (null sink)
su - patest -c "speaker-test -D pulse -l 1"
