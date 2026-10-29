# SPDX-License-Identifier: LGPL-2.1+
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Makefile of /CoreOS/ipset
#   Description: Test if ipset working ok
#   Author: Susant Sahani<susant@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
export TEST=/CoreOS/ipset
export TESTVERSION=1.0
BUILT_FILES=
FILES=$(METADATA) runtest.sh Makefile
.PHONY: all install download clean
run: $(FILES) build
	./runtest.sh
build: $(BUILT_FILES)
	test -x runtest.sh || chmod a+x runtest.sh
clean:
	rm -f *~ $(BUILT_FILES)
include /usr/share/rhts/lib/rhts-make.include
$(METADATA): Makefile
	@echo "Owner:           Susant Sahani<susant@redhat.com>" > $(METADATA)
	@echo "Name:            $(TEST)" >> $(METADATA)
	@echo "TestVersion:     $(TESTVERSION)" >> $(METADATA)
	@echo "Path:            $(TEST_DIR)" >> $(METADATA)
	@echo "Description:     Test ipset sanity" >> $(METADATA)
	@echo "Type:            Sanity" >> $(METADATA)
	@echo "TestTime:        5m" >> $(METADATA)
	@echo "RunFor:          ipset " >> $(METADATA)
	@echo "Requires:        ipset iperf3 python3 systemd python3-pyroute2 iptables" >> $(METADATA)
	@echo "Priority:        Normal" >> $(METADATA)
	@echo "License:         GPLv2" >> $(METADATA)
	@echo "Confidential:    no" >> $(METADATA)
	@echo "Destructive:     no" >> $(METADATA)
	@echo "Releases:        -Fedora 29" >> $(METADATA)
	rhts-lint $(METADATA)
