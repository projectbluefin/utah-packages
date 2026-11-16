NAME := virtiofsd
VERSION ?= $(shell grep Version: virtiofsd.spec | tr -d ' ' | cut -f2 -d:)

.PHONY: all down-crate vendor clean

all: down-crate vendor clean

down-crate:
	@echo Downloading version $(VERSION)
	curl -L https://crates.io/api/v1/crates/$(NAME)/$(VERSION)/download  -o $(NAME)-$(VERSION).crate

vendor:
	# After vendorize we need to remove winapi/windows binaries
	tar xf $(NAME)-$(VERSION).crate && \
	pushd $(NAME)-$(VERSION) && \
	cargo vendor && \
	find vendor/ -name *.a -print0 | xargs -0 rm && \
	tar Jcvf ../$(NAME)-$(VERSION)-vendor.tar.xz vendor/ && \
	popd

clean:
	rm -rf $(NAME)-$(VERSION)

