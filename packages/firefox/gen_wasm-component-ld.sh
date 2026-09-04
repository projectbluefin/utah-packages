#!/bin/bash
set -x

# Dummy Cargo.toml file with wasm-component-ld dependency
cat > Cargo.toml <<EOL
[package]
name = "dummy"
version = "0.0.1"
description = """
This is a dummy package which contains dependency on wasm-component-ld
to be used with 'cargo vendor' commmand.
"""

[dependencies]
wasm-component-ld = "=0.5.20"

[[bin]]
name = "dummy"
path = "dummy.rs"
doc = false
EOL

cargo install cargo-vendor
cargo vendor

cd vendor
tar -cJf ../wasm-component-ld-vendor.tar.xz *
cd ..

rm -f Cargo.toml
rm -rf vendor

