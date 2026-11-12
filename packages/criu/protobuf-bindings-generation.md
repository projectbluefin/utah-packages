# CRIU protobuf bindings shipped in this package

The factory pins `protobuf-python` **3.19.6** (runtime) but its `protoc` is **6.x**,
which regenerates `_pb2.py` files that the 3.19.6 runtime cannot import
(`google.protobuf.runtime_version` ImportError, utah-packages#983, #985).
So the 3.19.x-generated bindings are generated once and shipped as sources instead
of being regenerated at build time.

## Source10 — `criu-rpc_pb2.py` (single file)

```
# From a checkout of criu 4.3 with protobuf-3.19.x on PATH:
protoc -I=lib/pycriu/images --python_out=/tmp/rpc \
    lib/pycriu/images/rpc.proto
cp /tmp/rpc/lib/pycriu/images/rpc_pb2.py packages/criu/criu-rpc_pb2.py
```

Patched into `lib/pycriu/Makefile` (Patch100) so the build copies
`$RPC_PB2_PY` instead of running protoc.

## Source11 — `criu-pycriu-images.tar` (75 image bindings)

```
# Same environment as above; generate every image binding except rpc_pb2.py:
protoc -I=lib/pycriu/images --python_out=/tmp/images \
    lib/pycriu/images/*.proto
# rpc_pb2.py is handled separately (Source10), so drop it from the image set:
rm -f /tmp/images/lib/pycriu/images/rpc_pb2.py
# Tar under a flat criu-pycriu-images/ prefix (Patch101 extracts it there):
tar cf packages/criu/criu-pycriu-images.tar -C /tmp/images lib/pycriu/images
```

The tarball holds 76 entries (the `criu-pycriu-images/` dir + 75 `*_pb2.py`),
including `opts_pb2.py`/`sk_opts_pb2.py` that some image bindings import, and
deliberably **excludes** `rpc_pb2.py` (shipped as Source10). Patch101 extracts it
into `%{_builddir}/criu-pycriu-images` and the build copies from
`$PYCRIU_IMAGES_PB2` instead of regenerating with protoc 6.x.

All bindings are pre-3.20 codegen with no `runtime_version` marker, matching the
pinned 3.19.6 runtime.
