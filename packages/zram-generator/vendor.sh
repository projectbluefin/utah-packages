#!/usr/bin/bash

set -e

NAME=zram-generator
SPEC="${NAME}.spec"
VERSION=$(rpmspec -q --srpm --queryformat "%{version}" ${SPEC})

spectool -g ${SPEC}

tar -xzf ${NAME}-${VERSION}.tar.gz

pushd ${NAME}-${VERSION}
patch -p1 < ../238.patch
cargo vendor --versioned-dirs vendor
tar -Jcf ../${NAME}-${VERSION}-vendor.tar.xz vendor/
popd

rm -rf ${NAME}-${VERSION}/

