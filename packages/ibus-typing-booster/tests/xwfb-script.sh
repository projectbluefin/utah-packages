#!/bin/bash
# Run this with `xwfb-run -e /tmp/xwfb-run.log -n 99 xwfb-script.sh`

# Redirect stderr to stdout:
exec 2>&1
# without setting GDK_BACKEND=x11, Gtk programs cannot open windows in xfwb-run:
export GDK_BACKEND=x11
export XDG_SESSION_TYPE=x11
echo "starting mutter ..."
mutter --x11 &
sleep 5
echo "mutter started"
ibus-daemon --verbose \
            --replace \
            --single \
            --desktop=mutter \
            --panel=disable \
            --config=disable &
sleep 5
echo "ibus-daemon started."
pushd /usr/share/ibus-typing-booster/engine
/usr/libexec/installed-tests/ibus-typing-booster/test_0_gtk.py -v &
TEST_PID=$!
# A screenshot for debugging can be made here:
#sleep 1
#import -window root /tmp/screenshot.png
#echo "screenshot done."
# Wait for test_0_gtk.py to finish and get its exit code
wait $TEST_PID
EXIT_CODE=$?
echo "The exit code of test_0_gtk.py: $EXIT_CODE"
exit $EXIT_CODE
