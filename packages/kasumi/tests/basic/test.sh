#! /bin/sh
exec 2>&1
export GDK_BACKEND=x11
export XDG_SESSION_TYPE=x11

mutter --x11 &
sleep 5
echo "mutter started"

kasumi --help

exit $?
