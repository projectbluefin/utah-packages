#!/bin/bash

# Copyright (c) 2016 Red Hat, Inc.
# #
# # This program is free software: you can redistribute it and/or modify
# # it under the terms of the GNU General Public License as published by
# # the Free Software Foundation, either version 3 of the License, or
# # (at your option) any later version.
# #
# # This program is distributed in the hope that it will be useful,
# # but WITHOUT ANY WARRANTY; without even the implied warranty of
# # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# # GNU General Public License for more details.
# #
# # You should have received a copy of the GNU General Public License
# # along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# # Author: Lin Li   <lilin@redhat.com>

.PHONY: all install download clean

BUILT_FILES=

FILES=$(METADATA)  Makefile PURPOSE main.sh  

run: $(FILES) build
	./main.sh

build: $(BUILT_FILES)
	chmod a+x ./main.sh

clean:
	rm -f *~ *.rpm $(BUILT_FILES)

include /usr/share/rhts/lib/rhts-make.include

$(METADATA): Makefile
	@touch $(METADATA)
	@echo "Owner:        LiLin <lilin@redhat.com>" > $(METADATA)
	@echo "Name:         $(TEST)" >> $(METADATA)
	@echo "Path:         $(TEST_DIR)"	>> $(METADATA)
	@echo "License:      GPLv3" >> $(METADATA)
	@echo "TestVersion:  $(TESTVERSION)"	>> $(METADATA)
	@echo "Description:  restate_module" >> $(METADATA)
	@echo "TestTime:     15m" >> $(METADATA)
	@echo "RunFor:       device-mapper-multipath" >> $(METADATA)
	@echo "Requires:     device-mapper-multipath" >> $(METADATA)

	rhts-lint $(METADATA)
