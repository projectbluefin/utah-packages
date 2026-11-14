#!/usr/bin/bash

spectool -g syncthing.spec

go2rpm github.com/syncthing/syncthing \
    --name syncthing \
    -v $(rpmspec syncthing.spec -q --srpm --queryformat "%{version}") \
    --profile vendor \
    --compression xz \
    --stdout

