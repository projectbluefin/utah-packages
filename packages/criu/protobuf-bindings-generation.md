# CRIU protobuf bindings shipped in this package

The factory pins `protobuf-python` **3.19.6** (runtime) but its `protoc` is **6.x**,
which regenerates `_pb2.py` files that the 3.19.6 runtime cannot import
(`google.protobuf.runtime_version` ImportError, utah-packages#983, #985).
So the 3.19.x-generated bindings are generated once and shipped as sources instead
of being regenerated at build time.

In criu 4.3 the 76 `.proto` schemas live in the top-level `images/` directory
(`lib/pycriu/images/` holds only the Python helpers), and upstream's Makefiles
generate with `-I=images`, so protoc writes each binding straight into
`--python_out` as `<name>_pb2.py`.

## Regenerating Source10 and Source11

Run from the root of the criu 4.3 source (Source0; its SHA-512 is in
`packages/criu/sources`) with protoc 3.19.6 on `PATH`, for example
`protoc-3.19.6-linux-x86_64.zip` from the protobuf v3.19.6 release. protoc
finds `google/protobuf/descriptor.proto` (imported by `opts.proto`) in the
`include/` directory next to its binary. GNU tar is required for the archive.

```sh
# Absolute path of packages/criu in a utah-packages checkout.
package_dir=/path/to/utah-packages/packages/criu
generated=$(mktemp -d)
mkdir -p "$generated/rpc" "$generated/images/criu-pycriu-images"

# Source10: criu-rpc_pb2.py. Patch100 makes lib/pycriu/Makefile copy
# $RPC_PB2_PY instead of running protoc.
protoc -I=images --python_out="$generated/rpc" images/rpc.proto
cp "$generated/rpc/rpc_pb2.py" "$package_dir/criu-rpc_pb2.py"

# Source11: criu-pycriu-images.tar, the other 75 image bindings. rpc_pb2.py
# is Source10, so it is left out of the archive.
protoc -I=images --python_out="$generated/images/criu-pycriu-images" images/*.proto
rm -f "$generated/images/criu-pycriu-images/rpc_pb2.py"
# Rooted at criu-pycriu-images/, which %prep strips with
# --strip-components=1. The fixed order, owner and mtime make the archive
# byte-identical on every run.
TZ=UTC tar --format=gnu --sort=name --mtime='2020-01-01 00:00:00' \
    --owner=0 --group=0 --numeric-owner --mode='u=rwX,go=rX' \
    -cf "$package_dir/criu-pycriu-images.tar" \
    -C "$generated/images" criu-pycriu-images
```

Both commands reproduce the committed files byte for byte. The archive holds
76 entries (the `criu-pycriu-images/` directory and 75 `*_pb2.py`), including
`opts_pb2.py` and `sk_opts_pb2.py`, which other image bindings import. Patch101
makes `lib/pycriu/images/Makefile` copy `$PYCRIU_IMAGES_PB2/*` instead of running
protoc.

All bindings are pre-3.20 codegen with no `runtime_version` import, matching the
pinned 3.19.6 runtime.
