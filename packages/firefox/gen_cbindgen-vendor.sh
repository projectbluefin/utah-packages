#!/bin/bash
set -x

# Dummy Cargo.toml file with cbindgen dependency
cat > Cargo.toml <<EOL
[package]
name = "dummy"
version = "0.0.1"
description = """
This is a dummy package which contains dependency on cbindgen
to be used with 'cargo vendor' commmand.
"""

[dependencies]
cbindgen = "0.29.4"

[[bin]]
name = "dummy"
path = "dummy.rs"
doc = false
EOL

cargo install cargo-vendor
cargo vendor

cd vendor
tar -cJf ../cbindgen-vendor.tar.xz *
cd ..

rm -f Cargo.toml
rm -rf vendor

