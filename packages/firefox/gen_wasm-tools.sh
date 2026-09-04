#!/bin/bash
set -x

# Dummy Cargo.toml file with wasm-tools dependency
cat > Cargo.toml <<EOL
[package]
name = "dummy"
version = "0.0.1"
description = """
This is a dummy package which contains dependency on wasm-component-ld
to be used with 'cargo vendor' commmand.
"""

[dependencies]
wasm-tools = "1.245.1"

[[bin]]
name = "dummy"
path = "dummy.rs"
doc = false
EOL

cargo install cargo-vendor
cargo vendor

cd vendor
tar -cJf ../wasm-tools-vendor.tar.xz *
cd ..

rm -f Cargo.toml
rm -rf vendor

