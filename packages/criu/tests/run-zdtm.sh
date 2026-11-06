#!/bin/bash

set -xe

uname -a
rpm -qi criu || true
criu --version

# These zdtm tests are skipped because they fail only in CI system
EXCLUDES=" \
	-x zdtm/static/socket-tcp-reseted \
	-x zdtm/static/socket-tcp-closed \
	-x zdtm/static/socket-tcp-closed-last-ack \
	-x zdtm/static/socket-tcp6-closed \
	-x zdtm/static/socket-tcp4v6-closed \
	-x zdtm/static/maps01 \
	-x zdtm/static/maps04 \
	-x zdtm/static/del_standalone_un \
	-x zdtm/static/del_standalone_un_seqpacket \
	-x zdtm/static/deleted_unix_sock \
	-x zdtm/static/fifo_upon_unix_socket00 \
	-x zdtm/static/sk-unix-dgram-ghost \
	-x zdtm/static/sk-unix01 \
	-x zdtm/static/sk-unix01-seqpacket \
	-x zdtm/static/socket-tcpbuf \
	-x zdtm/static/socket-tcpbuf6 \
	-x zdtm/static/sockets00 \
	-x zdtm/static/sockets00-seqpacket \
	-x zdtm/static/sockets03 \
	-x zdtm/static/sockets03-seqpacket \
	-x zdtm/static/cgroup04 \
	-x zdtm/static/cgroup_ifpriomap \
	-x zdtm/static/netns_sub \
	-x zdtm/static/netns_sub_veth \
	-x zdtm/static/file_locks01 \
	-x zdtm/static/mntns_link_remap \
	-x zdtm/static/unlink_fstat03 \
	-x zdtm/static/unlink_regular00 \
	-x zdtm/static/cgroup02 "

run_test() {
	python3 ./zdtm.py run --criu-bin /usr/sbin/criu ${EXCLUDES} \
		-a --ignore-taint --keep-going

	RESULT=$?
}


RESULT=42

# this socket breaks CRIU's test cases
rm -f /var/lib/sss/pipes/nss

cd ../criu-$(crit --version)

echo "Build CRIU"
make -j"$(nproc)"

cd test

echo "Run the actual CRIU test suite"
run_test

if [ "$RESULT" -ne "0" ]; then
	# Run tests a second time to make sure it is a real failure
	echo "Something failed. Run the actual CRIU test suite a second time"
	run_test
	if [ "$RESULT" -ne "0" ]; then
		echo "Still a test suite error. Something seems to be actually broken"
		exit $RESULT
	fi
fi

exit 0
