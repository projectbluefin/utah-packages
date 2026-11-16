# We need to use C++17 to link against the system abseil-cpp, since it was
# compiled with C++17 (an intentional abseil-cpp design decision).
%global cpp_std 17

# =====

# Parameters for third-party sources needed for their .proto files, which
# upstream expects to download at build time.
#
# See https://github.com/grpc/grpc/pull/29254 “[xDS Proto] Enhence gRPC
# buildgen for 3rd party proto compilation” and
# https://github.com/grpc/grpc/commit/99752b173cfa2fba81dedb482ee4fd74b2a46bb0,
# in which the download mechanism was added.
#
# Check CMakeLists.txt (search for “download_archive”) for a list of these
# third-party sources and the commit hashes used in the grpc release.
#
# Note that we do not treat these additional sources as bundled dependencies,
# since (provably) only the .proto files are used.
#
# In practice, it seems the generated binding code for these protos is not
# re-generated when building this package, so we could get by with creating the
# appropriate directories and touching an empty file within each. We include
# these archives in the source RPM anyway, since they are in some sense part of
# the original sources for the generated proto code.

# This will probably never be separately packaged in Fedora, since upstream can
# only build with Bazel (and Bazel is such a mess of bundled dependencies that
# it is unlikely to every be successfully packaged under the Fedora packaging
# guidelines. Note that the URL is a read-only mirror based on
# https://github.com/envoyproxy/envoy, with different commit hashes.
%global envoy_api_commit 4de3c74cf21a9958c1cf26d8993c55c6e0d28b49
%global envoy_api_url https://github.com/envoyproxy/data-plane-api
%global envoy_api_dir data-plane-api-%{envoy_api_commit}

%global googleapis_commit fe8ba054ad4f7eca946c2d14a63c3f07c0b586a0
%global googleapis_url https://github.com/googleapis/googleapis
%global googleapis_dir googleapis-%{googleapis_commit}

%global opencensus_proto_version 0.3.0
%global opencensus_proto_url https://github.com/census-instrumentation/opencensus-proto
%global opencensus_proto_dir opencensus-proto-%{opencensus_proto_version}

%global xds_commit 3a472e524827f72d1ad621c4983dd5af54c46776
%global xds_url https://github.com/cncf/xds
%global xds_dir xds-%{xds_commit}

%global protoc_gen_validate_version 1.2.1
%global protoc_gen_validate_url https://github.com/envoyproxy/protoc-gen-validate
%global protoc_gen_validate_dir protoc-gen-validate-%{protoc_gen_validate_version}

# =====

# This must be enabled to get grpc_cli, which is apparently considered part of
# the tests by upstream. This is mentioned in
# https://github.com/grpc/grpc/issues/23432.
%bcond core_tests          1

# A great many of these tests (over 20%) fail. Any help in understanding these
# well enough to fix them or report them upstream is welcome.
%bcond python_aio_tests    0

%ifnarch s390x
# There are currently a significant number of failures like:
#
#   Exception serializing message!
#   Traceback (most recent call last):
#     File "/builddir/build/BUILDROOT/grpc-1.48.0-2.fc38~bootstrap.x86_64/usr/lib64/python3.11/site-packages/grpc/_common.py", line 86, in _transform
#       return transformer(message)
#              ^^^^^^^^^^^^^^^^^^^^
#     File "/usr/lib/python3.11/site-packages/google/protobuf/internal/python_message.py", line 1082, in SerializeToString
#       if not self.IsInitialized():
#              ^^^^^^^^^^^^^^^^^^
#   AttributeError: 'NoneType' object has no attribute 'IsInitialized'
%bcond python_gevent_tests 0
%else
# A significant number of Python tests pass in test_lite but fail in
# test_gevent, mostly by dumping core without a traceback.  Since it is tedious
# to enumerate these (and it is difficult to implement “suite-specific” skips
# for shared tests, so the tests would have to be skipped in all suites), we
# just skip the gevent suite entirely on this architecture.
%bcond python_gevent_tests 0
%endif

# Running core tests under valgrind may help debug crashes. This is mostly
# ignored if the gdb build conditional is also set.
%bcond valgrind            0
# Running core tests under gdb may help debug crashes.
%bcond gdb                 0

# HTML documentation generated with Doxygen and/or Sphinx is not suitable for
# packaging due to a minified JavaScript bundle inserted by
# Doxygen/Sphinx/Sphinx themes itself. See discussion at
# https://bugzilla.redhat.com/show_bug.cgi?id=2006555.
#
# Normally we could consider enabling the Doxygen PDF documentation as a lesser
# substitute, but (after enabling it and working around some Unicode characters
# in the Markdown input) we get:
#
#   ! TeX capacity exceeded, sorry [main memory size=6000000].
#
# A similar situation applies to the Sphinx-generated HTML documentation for
# Python, except that we have not even tried to render it as a PDF because it
# is too unpleasant to try if we already cannot package the Doxygen-generated
# documentation. Instead, we have just dropped all documentation.

Name:           grpc
Version:        1.75.1
Release:        %autorelease
Summary:        High performance, open source universal RPC framework

%global srcversion %(echo '%{version}' | sed -r 's/~rc/-pre/')
%global pyversion %(echo '%{version}' | tr -d '~')

# CMakeLists.txt: gRPC_CORE_SOVERSION
%global c_so_version 50
# CMakeLists.txt: gRPC_CPP_SOVERSION
# See https://github.com/abseil/abseil-cpp/issues/950#issuecomment-843169602
# regarding unusual C++ SOVERSION style (not a single number).
%global cpp_so_version 1.75

# The entire source is Apache-2.0 except the following:
#
# BSD-3-Clause:
#   - third_party/address_sorting/
#     * Potentially linked into any compiled subpackage (but not pure-Python
#       subpackages, etc.)
#
# as well as the following which do not contribute to the base License field or
# any subpackage License field for the reasons noted:
#
# MPL-2.0:
#   - etc/roots.pem
#     * Truncated to an empty file in prep; a symlink to the shared system
#       certificates is used instead
#   - src/android/test/interop/app/src/main/assets/roots.pem
#     * Truncated to an empty file in prep
# ISC:
#   - src/boringssl/boringssl_prefix_symbols.h
#     * Removed in prep; not used when building with system OpenSSL
# BSD-3-Clause:
#   - src/objective-c/*.podspec and
#     templates/src/objective-c/*.podspec.template
#     * Unused since the Objective-C bindings are not currently built;
#       furthermore, these seem to be build-system files that would not
#       contribute their licenses to the binary RPM contents anyway
# NTP:
#   - third_party/cares/ares_build.h
#     * Removed in prep; header from system C-Ares used instead
License:        Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND MIT
URL:            https://www.grpc.io
%global forgeurl https://github.com/grpc/grpc
Source0:        %{forgeurl}/archive/v%{srcversion}/grpc-%{srcversion}.tar.gz
Source2:        %{envoy_api_url}/archive/%{envoy_api_commit}/%{envoy_api_dir}.tar.gz
Source3:        %{googleapis_url}/archive/%{googleapis_commit}/%{googleapis_dir}.tar.gz
Source4:        %{opencensus_proto_url}/archive/v%{opencensus_proto_version}/%{opencensus_proto_dir}.tar.gz
Source5:        %{xds_url}/archive/%{xds_commit}/%{xds_dir}.tar.gz
Source6:        %{protoc_gen_validate_url}/archive/v%{protoc_gen_validate_version}/%{protoc_gen_validate_dir}.tar.gz

# Downstream grpc_cli man pages; hand-written based on “grpc_cli help” output.
Source100:      grpc_cli.1
Source101:      grpc_cli-ls.1
Source102:      grpc_cli-call.1
Source103:      grpc_cli-type.1
Source104:      grpc_cli-parse.1
Source105:      grpc_cli-totext.1
Source106:      grpc_cli-tojson.1
Source107:      grpc_cli-tobinary.1
Source108:      grpc_cli-help.1

# ~~~~ C (core) and C++ (cpp) ~~~~

BuildRequires:  gcc-c++
BuildRequires:  cmake
BuildRequires:  ninja-build
%if %{with core_tests}
# Used on grpc_cli:
BuildRequires:  chrpath
%endif

BuildRequires:  pkgconfig(zlib)
BuildRequires:  pkgconfig(protobuf)
BuildRequires:  protobuf-compiler
BuildRequires:  pkgconfig(protobuf-lite)
BuildRequires:  cmake(utf8_range)
BuildRequires:  pkgconfig(re2)
BuildRequires:  pkgconfig(openssl)
BuildRequires:  cmake(c-ares)
BuildRequires:  abseil-cpp-devel
BuildRequires:  pkgconfig(libxxhash)
BuildRequires:  pkgconfig(libsystemd)

%if %{with core_tests}
BuildRequires:  cmake(benchmark)
BuildRequires:  cmake(gtest)
BuildRequires:  pkgconfig(gmock)
%if %{with valgrind}
BuildRequires:  valgrind
%endif
%if %{with gdb}
BuildRequires:  gdb
%endif
%endif

# ~~~~ Python ~~~~

BuildRequires:  python3-devel
BuildRequires:  python3dist(setuptools)
BuildRequires:  python3dist(pip)
BuildRequires:  python3dist(wheel)

# grpcio (setup.py) setup_requires (with
#     GRPC_PYTHON_ENABLE_DOCUMENTATION_BUILD, which is NOT enabled):
# BuildRequires:  python3dist(sphinx)

# grpcio (setup.py) setup_requires (with GRPC_PYTHON_BUILD_WITH_CYTHON, or
# absent generated sources); also needed for grpcio_tools
# (tools/distrib/python/grpcio_tools/setup.py)
BuildRequires: python3dist(cython) > 0.23

# grpcio_channelz (src/python/grpcio_channelz/setup.py) install_requires:
# grpcio_health_checking (src/python/grpcio_health_checking/setup.py) install_requires:
# grpcio_reflection (src/python/grpcio_reflection/setup.py) install_requires:
# grpcio_status (src/python/grpcio_status/setup.py) install_requires:
# grpcio_testing (src/python/grpcio_testing/setup.py) install_requires:
# grpcio_tests (src/python/grpcio_tests/setup.py) install_requires:
# grpcio_tools (tools/distrib/python/grpcio_tools/setup.py) install_requires:
BuildRequires:  (python3dist(protobuf) >= 6.31.1 with python3dist(protobuf) < 7.0.0)

# grpcio_status (src/python/grpcio_status/setup.py) install_requires:
BuildRequires:  python3dist(googleapis-common-protos) >= 1.5.5

# Several packages have dependencies on grpcio or grpcio_tools—and grpcio-tests
# depends on all of the other Python packages—which are satisfied within this
# package.
#
# Similarly, grpcio_admin depends on grpcio_channelz and grpcio_csds (but we do
# not package either grpcio_admin or grpc_csds because they depend on the
# problematic xds-protos; see the note above the corresponding Obsoletes later
# in this spec file).

# grpcio_tests (src/python/grpcio_tests/setup.py) install_requires:
BuildRequires:  python3dist(oauth2client) >= 1.4.7

# grpcio_tests (src/python/grpcio_tests/setup.py) install_requires:
BuildRequires:  python3dist(google-auth) >= 1.17.2

# grpcio_tests (src/python/grpcio_tests/setup.py) install_requires:
BuildRequires:  python3dist(requests) >= 2.14.2

# dns_server.py imports
BuildRequires:  python3dist(twisted)
BuildRequires:  python3dist(service-identity)
BuildRequires:  python3dist(pyyaml)

%if %{with python_gevent_tests}
# Required for “test_gevent” tests:
BuildRequires:  python3dist(gevent)
%endif

# For stopping the port server
BuildRequires:  curl

# ~~~~ Miscellaneous ~~~~

# https://bugzilla.redhat.com/show_bug.cgi?id=1893533
%global _lto_cflags %{nil}

# Reference documentation, which is *not* enabled
# BuildRequires:  doxygen

BuildRequires:  ca-certificates
# For converting absolute symlinks in the buildroot to relative ones
BuildRequires:  symlinks
# For hardlinking duplicate files in the examples
BuildRequires:  hardlink

# Apply Fedora system crypto policies. Since this is Fedora-specific, the patch
# is not suitable for upstream.
# https://docs.fedoraproject.org/en-US/packaging-guidelines/CryptoPolicies/#_cc_applications
#
# In fact, this may not be needed, since only testing code is patched.
Patch0:         grpc-1.74.1-Use-the-system-OpenSSL-profile.patch
# Fix errors like:
#   TypeError: super(type, obj): obj must be an instance or subtype of type
# It is not clear why these occur.
# Patch:          grpc-1.36.4-python-grpcio_tests-fixture-super.patch
# Skip tests requiring non-loopback network access when the
# FEDORA_NO_NETWORK_TESTS environment variable is set.
Patch1:         grpc-1.40.0-python-grpcio_tests-make-network-tests-skippable.patch
# A handful of compression tests miss the compression ratio threshold. It seems
# to be inconsistent which particular combinations fail in a particular test
# run. It is not clear that this is a real problem. Any help in understanding
# the actual cause well enough to fix this or usefully report it upstream is
# welcome.
Patch2:         grpc-1.60.0-python-grpcio_tests-skip-compression-tests.patch
# The upstream requirement to link gtest/gmock from grpc_cli is spurious.
# Remove it. We still have to build the core tests and link a test library
# (libgrpc++_test_config.so…)
# Patch:          grpc-1.56.1-Do-not-link-gtest-gmock-from-grpc_cli.patch
# Skip failing ChannelzServicerTest tests on Python 3.11
#
# Partially works around:
#
# grpc fails to build with Python 3.11: AttributeError: module 'inspect' has no
#   attribute 'getargspec'
# https://bugzilla.redhat.com/show_bug.cgi?id=2095027
#
# TODO: Attempt to reproduce this outside the RPM build environment and submit
# a useful/actionable upstream bug report.
Patch3:         grpc-1.60.0-ChannelzServicerTest-python3.11-regressions.patch
# Running Python “test_lite”, in grpcio_tests,
# unit._dynamic_stubs_test.DynamicStubTest.test_grpc_tools_unimportable hangs.
# This may be related to:
#   [FLAKE] DynamicStubTest timeout under gevent macOS
#   https://github.com/grpc/grpc/issues/25368
# The patch simply skips the test.
Patch4:         grpc-1.60.0-Skip-hanging-DynamicStubTest.patch

# Use system gtest
Patch5:         grpc-1.75.1-system-gtest.patch

# Use system upb
Patch6:         grpc-1.75.1-use-system-upb.patch

# Use shared xxhash
Patch7:         grpc-1.74.1-use-shared-xxhash.patch

# Don't include <openssl/engine.h>
# OpenSSL in Fedora provides this header in a separate openssl-devel-engine
# RPM, which is deprecated and subject to future removal.. RHEL10 has no
# such package, nor has this version of grpc has not caught up with the
# removal of engine and related headers.
Patch8:         grpc-1.74.1-openssl-no-engine.patch

# Downstream-only patch to remove usage of coverage, per the packaging
# guidelines.  This reduces the build-time dependencies, which slightly speeds
# up builds.  It also makes this package easier port to new EPEL branches.
# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_linters
Patch9:         0001-Remove-usage-of-coverage.patch

# Downstream-only patch to fix tests.
Patch10:        grpc-1.74.1-httpcli_test-fix-path.patch

# https://github.com/grpc/grpc/pull/40806
Patch11:        0001-Skip-installing-otel-plugin-pkgconfig-if-not-enabled.patch

Patch12:        grpc-1.75.1-spiffe_bundle_map_end2end_test-fix.patch

# Add missing standard library includes (<string>, <limits>, <algorithm>) that
# GCC 16's libstdc++ no longer provides transitively.
# Backport of "[build] add missing includes":
# https://github.com/grpc/grpc/pull/41351
# https://github.com/grpc/grpc/commit/d54219b508423f0a2ff6a0b98c16fb6dafd44b84
Patch13:        grpc-1.75.1-missing-includes.patch

# Use the OpenSSL accessor functions instead of reaching into structs that are
# opaque in OpenSSL 4, and honor the const qualifiers the OpenSSL 4 getters
# return.
#
# Equivalent to "[OpenSSL] Add support for OpenSSL 4", which landed in grpc
# master (the pull request shows as closed because gRPC merges via copybara):
# https://github.com/grpc/grpc/pull/41932
# and, for the removed TLSv1_2_{client,server}_method() in the handshake tests,
# "[export] [OpenSSL] Fix handshake tests for OpenSSL < 1.1.0":
# https://github.com/grpc/grpc/pull/43358
# https://github.com/grpc/grpc/commit/87f70cec62c0c675d4069af3e20d07c0f95871d9
#
# Tracking issue: https://github.com/grpc/grpc/issues/42020
Patch14:        0001-Update-OpenSSL-API-usage-for-compatibility.patch

Requires:       grpc-data = %{version}-%{release}

# Regarding third_party/address_sorting: this looks a bit like a bundled
# library, but it is not. From a source file comment:
#   This is an adaptation of Android's implementation of RFC 6724 (in Android’s
#   getaddrinfo.c). It has some cosmetic differences from Android’s
#   getaddrinfo.c, but Android’s getaddrinfo.c was used as a guide or example
#   of a way to implement the RFC 6724 spec when this was written.

%global common_description %{expand:
gRPC is a modern, open source, high-performance remote procedure call (RPC)
framework that can run anywhere. gRPC enables client and server applications to
communicate transparently, and simplifies the building of connected systems.}

%description %{common_description}

This package provides the shared C core library.


%package data
Summary:        Data for gRPC bindings
License:        Apache-2.0
BuildArch:      noarch

Requires:       ca-certificates

%description data %{common_description}

This package provides common data for gRPC bindings: currently, this contains
only a symbolic link to the system shared TLS certificates.


%package doc
Summary:        Documentation and examples for gRPC
License:        Apache-2.0
BuildArch:      noarch

Obsoletes:      python-grpcio-doc < 1.26.0-13
Provides:       python-grpcio-doc = %{version}-%{release}
Provides:       python-grpcio-admin-doc = %{version}-%{release}
Provides:       python-grpcio-csds-doc = %{version}-%{release}
Provides:       python-grpcio-channelz-doc = %{version}-%{release}
Provides:       python-grpcio-health-checking-doc = %{version}-%{release}
Provides:       python-grpcio-reflection-doc = %{version}-%{release}
Provides:       python-grpcio-status-doc = %{version}-%{release}
Provides:       python-grpcio-testing-doc = %{version}-%{release}

%description doc %{common_description}

This package provides examples and documentation sources (but not rendered
documentation) for gRPC. For rendered HTML documentation, please see
https://grpc.io/docs/.


%package cpp
Summary:        C++ language bindings for gRPC
# License:        same as base package

Requires:       grpc%{?_isa} = %{version}-%{release}
Requires:       grpc-cpp%{?_isa} = %{version}-%{release}

%description cpp %{common_description}

This package provides C++ language bindings for gRPC.


%package plugins
Summary:        Protocol buffers compiler plugins for gRPC
# License:        same as base package

Requires:       grpc%{?_isa} = %{version}-%{release}
Requires:       grpc-cpp%{?_isa} = %{version}-%{release}
Requires:       protobuf-compiler

%description plugins %{common_description}

This package provides plugins to the protocol buffers compiler to generate gRPC
sources.

%package cli
Summary:        Command-line tool for gRPC
# License:        same as base package

Requires:       grpc%{?_isa} = %{version}-%{release}
Requires:       grpc-cpp%{?_isa} = %{version}-%{release}

%description cli %{common_description}

The command line tool can do the following things:

  • Send unary rpc.
  • Attach metadata and display received metadata.
  • Handle common authentication to server.
  • Infer request/response types from server reflection result.
  • Find the request/response types from a given proto file.
  • Read proto request in text form.
  • Read request in wire form (for protobuf messages, this means serialized
    binary form).
  • Display proto response in text form.
  • Write response in wire form to a file.


%package devel
Summary:        Development files for gRPC library
# License:        same as base package
Requires:       grpc%{?_isa} = %{version}-%{release}
Requires:       grpc-cpp%{?_isa} = %{version}-%{release}
Requires:       grpc-plugins%{?_isa} = %{version}-%{release}

# grpc/impl/codegen/port_platform.h includes linux/version.h
Requires:       kernel-headers%{?_isa}
# grpcpp/impl/codegen/config_protobuf.h includes google/protobuf/…
Requires:       pkgconfig(protobuf)
# grpcpp/test/mock_stream.h includes gmock/gmock.h
Requires:       pkgconfig(gmock)
# grpcpp/impl/codegen/sync.h includes absl/synchronization/mutex.h
# grpc.pc has -labsl_[…]
Requires:       cmake(absl)
# grpc.pc has -lre2
Requires:       pkgconfig(re2)
# grpc.pc has -lcares
Requires:       cmake(c-ares)
# grpc.pc has -lz
Requires:       pkgconfig(zlib)
# gRPCTargets.cmake links libsystemd.so
Requires:       pkgconfig(libsystemd)

%description devel %{common_description}

This package provides development headers and files for gRPC libraries (both C
and C++).


%package -n python3-grpcio
Summary:        Python language bindings for gRPC
# License:        same as base package

# Note that the Python package has no runtime dependency on the base C library;
# everything it needs is linked statically. It is not practical to change this,
# and since they both come from the same source RPM, we do not need to attempt
# to do so.
Requires:       grpc-data = %{version}-%{release}

# We no longer package these because they require python3dist(xds-protos),
# which has some issues:
#   - It provides files that overlap with several other packages, including
#     python-googleapis-common-protos, python-opencensus-proto, and
#     python-opentelemetry
#   - The PyPI release is not updated regularly, and version skew only makes
#     the above-mentioned problem of overlapping files worse.
#   - The “validate” package conflicts with one belonging to python-configobj
#     (in F38+), and it is the latter package that owns
#     https://pypi.org/project/validate/.
Obsoletes:      python3-grpcio-admin < 1.48.4-7
Obsoletes:      python3-grpcio-csds < 1.48.4-7

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_provides_for_importable_modules
%py_provides python3-grpc

%description -n python3-grpcio %{common_description}

This package provides Python language bindings for gRPC (HTTP/2-based RPC
framework).


%global grpcio_egg %{python3_sitearch}/grpcio-%{pyversion}.dist-info
%{?python_extras_subpkg:%python_extras_subpkg -n python3-grpcio -i %{grpcio_egg} protobuf}


%package -n python3-grpcio-tools
Summary:       Package for gRPC Python tools
# License:        same as base package

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_provides_for_importable_modules
%py_provides python3-grpc-tools

%description -n python3-grpcio-tools %{common_description}

This package provides gRPC Python tools.


%package -n python3-grpcio-channelz
Summary:        Channel Level Live Debug Information Service for gRPC
License:        Apache-2.0

BuildArch:      noarch

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_provides_for_importable_modules
%py_provides python3-grpc-channelz

%description -n python3-grpcio-channelz %{common_description}

Channelz is a live debug tool in gRPC Python.


%package -n python3-grpcio-health-checking
Summary:        Standard Health Checking Service for gRPC
License:        Apache-2.0

BuildArch:      noarch

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_provides_for_importable_modules
%py_provides python3-grpc-health

%description -n python3-grpcio-health-checking %{common_description}

This is the reference package for gRPC Python health checking.


%package -n python3-grpcio-reflection
Summary:        Standard Protobuf Reflection Service for gRPC
License:        Apache-2.0

BuildArch:      noarch

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_provides_for_importable_modules
%py_provides python3-grpc-reflection

%description -n python3-grpcio-reflection %{common_description}
This is the reference package for reflection in gRPC Python.


%package -n python3-grpcio-status
Summary:        Status proto mapping for gRPC
License:        Apache-2.0

BuildArch:      noarch

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_provides_for_importable_modules
%py_provides python3-grpc-status

%description -n python3-grpcio-status %{common_description}

This is the reference package for gRPC Python status proto mapping.


%package -n python3-grpcio-testing
Summary:        Testing utilities for gRPC Python
License:        Apache-2.0

BuildArch:      noarch

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_provides_for_importable_modules
%py_provides python3-grpc-testing

%description -n python3-grpcio-testing %{common_description}

This package provides testing utilities for gRPC Python.


%prep
%autosetup -p1 -n grpc-%{srcversion}

echo '===== Patching grpcio_tools for system protobuf/abseil-cpp =====' 2>&1
# Build python3-grpcio_tools against system protobuf packages instead of
# expecting a git submodule. Must also add requisite linker flags using
# GRPC_PYTHON_LDFLAGS. This was formerly done by
# grpc-VERSION-python-grpcio_tools-use-system-protobuf.patch, but it had to be
# tediously but trivially rebased every patch release as the CC_FILES list
# changed, so we automated the patch.
cat >> 'tools/distrib/python/grpcio_tools/protoc_lib_deps.py' <<'EOF'

# Downstream patch: override or modify values so that we do not depend on
# bundled files for system libraries.

del PROTOBUF_SUBMODULE_VERSION
PROTO_INCLUDE="%{_includedir}"

_unbundle_libs = {"abseil-cpp", "protobuf", "upb", "utf8_range"}
_unbundle_prefixes = {f"third_party/{lib}" for lib in _unbundle_libs}

def _ok_prefix(path):
    return not any(map(path.startswith, _unbundle_prefixes))

CC_FILES = list(filter(_ok_prefix, CC_FILES))
CC_INCLUDES = list(filter(_ok_prefix, CC_INCLUDES))
EOF


# Extract the source tarballs needed for their .proto files, which upstream
# expects to download at build time.
%setup -q -T -D -b 2 -n grpc-%{srcversion}
%setup -q -T -D -b 3 -n grpc-%{srcversion}
%setup -q -T -D -b 4 -n grpc-%{srcversion}
%setup -q -T -D -b 5 -n grpc-%{srcversion}
%setup -q -T -D -b 6 -n grpc-%{srcversion}
{
  awk '$1 ~ /^(#|$)/ { next }; 1' <<'EOF'
../%{envoy_api_dir}/ third_party/envoy-api/
../%{googleapis_dir}/ third_party/googleapis/
../%{opencensus_proto_dir}/ third_party/opencensus-proto/
../%{xds_dir}/ third_party/xds/
../%{protoc_gen_validate_dir}/ third_party/protoc-gen-validate/
EOF
} | while read -r fromdir todir
do
  # Remove everything from the external source tree except the .proto files, to
  # prove that none of it is bundled.
  find "${fromdir}" -type f ! -name '*.proto' -print -delete
  # Remove the empty directory corresponding to the git submodule
  rm -rvf "${todir}"
  # Move the extracted source, to the location where the git submodule would be
  # in a git checkout that included it.
  mv "${fromdir}" "${todir}"
done

echo '===== Removing bundled xxhash =====' 2>&1
# Remove bundled xxhash
rm -rvf third_party/xxhash

echo '===== Fixing permissions =====' 2>&1
# https://github.com/grpc/grpc/pull/27069
find . -type f -perm /0111 \
    -exec gawk '!/^#!/ { print FILENAME }; { nextfile }' '{}' '+' |
  xargs -r chmod -v a-x

echo '===== Removing selected unused sources =====' 2>&1
# Remove unused sources that have licenses not in the License field, to ensure
# they are not accidentally used in the build. See the comment above the base
# package License field for more details.
rm -rfv \
    src/boringssl/boringssl_prefix_symbols.h \
    third_party/cares/ares_build.h \
    third_party/upb third_party/utf8_range
# Since we are replacing roots.pem with a symlink to the shared system
# certificates, we do not include its license (MPLv2.0) in any License field.
# We remove its contents so that, if we make a packaging mistake, we will have
# a bug but not an incorrect License field.
echo '' > etc/roots.pem

# Remove Android sources and examples. We do not need these on Linux, and they
# have some issues that will be flagged when reviewing the package, such as:
#   - Another copy of the MPLv2.0-licensed certificate bundle from
#     etc/roots.pem, in src/android/test/interop/app/src/main/assets/roots.pem
#   - Pre-built jar files at
#     src/android/test/interop/gradle/wrapper/gradle-wrapper.jar and
#     examples/android/helloworld/gradle/wrapper/gradle-wrapper.jar
rm -rvf examples/android src/android

# Drop the NodeJS example’s package-lock.json file, which will hopefully keep
# us from having bugs filed due to CVE’s in its (unpackaged) recursive
# dependencies.
rm -vf examples/node/package-lock.json

# Remove unwanted .gitignore files, generally in examples. One could argue that
# a sample .gitignore file is part of the example, but, well, we’re not going
# to do that.
find . -type f -name .gitignore -print -delete

echo '===== Fixing shebangs =====' 2>&1
# Find executables with /usr/bin/env shebangs in the examples, and fix them.
find . -type f -perm /0111 -exec gawk \
    '/^#!\/usr\/bin\/env[[:blank:]]/ { print FILENAME }; { nextfile }' \
    '{}' '+' |
  xargs -r sed -r -i '1{s|^(#!/usr/bin/)env[[:blank:]]+([^[:blank:]]+)|\1\2|}'

echo '===== Fixing hard-coded C++ standard =====' 2>&1
# We need to adjust the C++ standard to avoid abseil-related linker errors. For
# the main C++ build, we can use CMAKE_CXX_STANDARD. For extensions, examples,
# etc., we must patch.
sed -r -i 's/(std=c\+\+)17/\1%{cpp_std}/g' \
    setup.py Rakefile \
    examples/cpp/*/Makefile \
    examples/cpp/*/CMakeLists.txt \
    tools/run_tests/artifacts/artifact_targets.py \
    tools/distrib/python/grpcio_tools/setup.py


echo '===== Adding any neccessary Python test skips =====' 2>&1
# This appears to be merely a representation discrepancy. We haven’t been able
# to track it down to a particular change (e.g. dependency version update). It
# appears in F38 as well, if the necessary abseil-cpp and protobuf packages are
# built. Since we don’t understand this well enough to report it upstream
# usefully, we just skip it downstream for now. Assistance welcome.
#
# Sample difference:
#
# -  '  "channelz._channelz_servicer_test.ChannelzServicerTest",\n'
# ?   ^^^                                                     ^ ---
# +  'tests.channelz._channelz_servicer_test.ChannelzServicerTest',
# ?   ^^^^^^                                                     ^
from='^([[:blank:]]+)(def testTestsJsonUpToDate\()'
skip='@unittest.skip("JSON representations differ; cause not ascertained")'
sed -r -i "s/${from}/\\1${skip}\\n\\1\\2/" \
    src/python/grpcio_tests/tests/_sanity/_sanity_test.py
# With abseil-cpp-20240116.0:
# [mutex.cc : 1418] RAW: Potential Mutex deadlock:
# …
# [mutex.cc : 1428] RAW: Acquiring absl::Mutex 0x556a1fa3d0e0 while holding
# 0x556a1fa4bdc0 0x7f55cc003530; a cycle in the historical lock ordering graph
# has been observed
#
# In TestLeak:test_leak_with_single_shot_rpcs.
#
# Since this is the only test in the case, we can’t just skip it with a
# decorator or unittest explodes with a KeyError. Since this is the only test
# case in the module, we remove the entire module.
rm src/python/grpcio_tests/tests_py3_only/unit/_leak_test.py
%ifarch aarch64 s390x x86_64
# With abseil-cpp-20240116.0 on s390x or x86_64 (output from s390x):
#
# Running       tests_py3_only.unit._simple_stubs_test.SimpleStubsTest.test_total_channels_enforced
# [mutex.cc : 1418] RAW: Potential Mutex deadlock:
# 	@ 0x3ffacc8c7f0 absl::lts_20240116::Mutex::Lock()
# …
# [mutex.cc : 1428] RAW: Acquiring absl::Mutex 0x2aa274724d0 while holding  0x2aa2748aa90 0x2aa27463910; a cycle in the historical lock ordering graph has been observed
# …
# [mutex.cc : 1454] RAW: dying due to potential deadlock
#
# This failure is flaky. It’s unclear whether s390x is the only affected
# architecture or whether this is the only affected test.
#
# from='^([[:blank:]]+)(def test_total_channels_enforced\()'
# skip='@unittest.skip("Deadlock \/ lock ordering graph cycle")'
# sed -r -i "s/${from}/\\1${skip}\\n\\1\\2/" \
#     src/python/grpcio_tests/tests_py3_only/unit/_simple_stubs_test.py
#
# -----
#
# With abseil-cpp-20240116.0 on aarch64:
#
# Running       tests_py3_only.unit._simple_stubs_test.SimpleStubsTest.test_stream_stream
# /builddir/build/BUILD/grpc-1.60.0/src/python/grpcio_tests/tests_py3_only/unit/_simple_stubs_test.py:293: ExperimentalApiWarning: 'stream_stream' is an experimental API. It is subject to change or removal between minor releases. Proceed with caution.
#   for response in grpc.experimental.stream_stream(
# [mutex.cc : 1418] RAW: Potential Mutex deadlock:
# 	@ 0x21ffff84f96a38
# …
# [mutex.cc : 1428] RAW: Acquiring absl::Mutex 0xaaaadadf77a0 while holding  0xaaaadae500b0; a cycle in the historical lock ordering graph has been observed
# …
# [mutex.cc : 1454] RAW: dying due to potential deadlock
#
# This failure is flaky. It’s unclear whether aarch64 is the only affected
# architecture or whether this is the only affected test.
#
# from='^([[:blank:]]+)(def test_stream_stream\()'
# skip='@unittest.skip("Deadlock \/ lock ordering graph cycle")'
# sed -r -i "s/${from}/\\1${skip}\\n\\1\\2/" \
#     src/python/grpcio_tests/tests_py3_only/unit/_simple_stubs_test.py
#
# -----
#
# Even skipping a single test with a decorator causes unittest to explode with
# a KeyError, which is very strange. We just remove the entire test module on
# these architectures.
rm src/python/grpcio_tests/tests_py3_only/unit/_simple_stubs_test.py
%endif


%build
# ~~~~ C (core) and C++ (cpp) ~~~~

# Length of the prefix (e.g. /usr), plus a trailing slash (or newline), plus
# one, to get the index of the first relative path character after the prefix.
# This is needed because gRPC_INSTALL_*DIR options expect paths relative to the
# prefix, and supplying absolute paths causes certain subtle problems.
%global rmprefix %(echo $(($(wc -c <<<'%{_prefix}')+1)))

echo '===== Building C (core) and C++ components =====' 2>&1
# We could use either make or ninja as the backend; ninja is faster and has no
# disadvantages (except a small additional BR, given we already need Python)
#
# We need to adjust the C++ standard to avoid abseil-related linker errors.
%cmake \
    -DgRPC_INSTALL:BOOL=ON \
    -DCMAKE_CXX_STANDARD:STRING=%{cpp_std} \
    -DCMAKE_SKIP_INSTALL_RPATH:BOOL=ON \
    -DgRPC_INSTALL_BINDIR:PATH=%(cut -b %{rmprefix}- <<<'%{_bindir}') \
    -DgRPC_INSTALL_LIBDIR:PATH=%(cut -b %{rmprefix}- <<<'%{_libdir}') \
    -DgRPC_INSTALL_INCLUDEDIR:PATH=%(cut -b %{rmprefix}- <<<'%{_includedir}') \
    -DgRPC_INSTALL_CMAKEDIR:PATH=%(cut -b %{rmprefix}- <<<'%{_libdir}/cmake/grpc') \
    -DgRPC_INSTALL_SHAREDIR:PATH=%(cut -b %{rmprefix}- <<<'%{_datadir}/grpc') \
    -DgRPC_BUILD_TESTS:BOOL=%{?with_core_tests:ON}%{?!with_core_tests:OFF} \
    -DgRPC_BUILD_CODEGEN:BOOL=ON \
    -DgRPC_BUILD_CSHARP_EXT:BOOL=ON \
    -DgRPC_BACKWARDS_COMPATIBILITY_MODE:BOOL=OFF \
    -DgRPC_ZLIB_PROVIDER:STRING='package' \
    -DgRPC_CARES_PROVIDER:STRING='package' \
    -DgRPC_RE2_PROVIDER:STRING='package' \
    -DgRPC_SSL_PROVIDER:STRING='package' \
    -DgRPC_PROTOBUF_PROVIDER:STRING='package' \
    -DgRPC_BENCHMARK_PROVIDER:STRING='package' \
    -DgRPC_ABSL_PROVIDER:STRING='package' \
    -DgRPC_GTEST_PROVIDER:STRING='package' \
    -DgRPC_USE_PROTO_LITE:BOOL=OFF \
    -DgRPC_USE_SYSTEMD:BOOL=ON \
    -DgRPC_BUILD_GRPC_CPP_PLUGIN:BOOL=ON \
    -DgRPC_BUILD_GRPC_CSHARP_PLUGIN:BOOL=ON \
    -DgRPC_BUILD_GRPC_NODE_PLUGIN:BOOL=ON \
    -DgRPC_BUILD_GRPC_OBJECTIVE_C_PLUGIN:BOOL=ON \
    -DgRPC_BUILD_GRPC_PHP_PLUGIN:BOOL=ON \
    -DgRPC_BUILD_GRPC_PYTHON_PLUGIN:BOOL=ON \
    -DgRPC_BUILD_GRPC_RUBY_PLUGIN:BOOL=ON \
    -DgRPC_DOWNLOAD_ARCHIVES:BOOL=OFF \
    -GNinja
%cmake_build
# ~~~~ Python ~~~~

echo '===== Building Python grpcio package =====' 2>&1
# Since there are some interdependencies in the Python packages (e.g., many
# have setup_requires: grpcio-tools), we do temporary installs of built
# packages into a local directory as needed, and add it to the PYTHONPATH.
PYROOT="${PWD}/%{_vpath_builddir}/pyroot"
if [ -n "${PYTHONPATH-}" ]; then PYTHONPATH="${PYTHONPATH}:"; fi
PYTHONPATH="${PYTHONPATH-}${PYROOT}%{python3_sitelib}"
PYTHONPATH="${PYTHONPATH}:${PYROOT}%{python3_sitearch}"
export PYTHONPATH

# ~~ grpcio ~~
export GRPC_PYTHON_BUILD_WITH_CYTHON='True'
export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL='True'
export GRPC_PYTHON_BUILD_SYSTEM_ZLIB='True'
export GRPC_PYTHON_BUILD_SYSTEM_CARES='True'
export GRPC_PYTHON_BUILD_SYSTEM_RE2='True'
export GRPC_PYTHON_BUILD_SYSTEM_ABSL='True'
export GRPC_PYTHON_BUILD_SYSTEM_UPB='True'
export GRPC_PYTHON_BUILD_SYSTEM_UTF8_RANGE='True'
export GRPC_PYTHON_BUILD_SYSTEM_XXHASH='True'
export GRPC_PYTHON_DISABLE_LIBC_COMPATIBILITY='True'
export GRPC_PYTHON_ENABLE_DOCUMENTATION_BUILD='False'
# Use the upstream defaults for GRPC_PYTHON_CFLAGS adn GRPC_PYTHON_LDFLAGS,
# except:
#
# - Add any flags necessary for using the system protobuf library.
# - Drop -lpthread and -lrt, since these are not needed on glibc 2.34 and
#   later.
# - Do not link libgcc statically (-static-libgcc).
#
# See also:
# https://developers.redhat.com/articles/2021/12/17/why-glibc-234-removed-libpthread
export GRPC_PYTHON_CFLAGS="$(
  pkg-config --cflags protobuf
) -std=c++%{cpp_std} -fvisibility=hidden -fno-wrapv -fno-exceptions"
export GRPC_PYTHON_LDFLAGS="$(pkg-config --libs protobuf)"
%pyproject_wheel
%{__python3} %{py_setup} %{?py_setup_args} install \
    -O1 --skip-build --root "${PYROOT}" --prefix %{_prefix}

# ~~ grpcio-tools ~~
echo '===== Building Python grpcio_tools package =====' 2>&1
pushd "tools/distrib/python/grpcio_tools/" >/dev/null
# When copying more things in here, make sure the subpackage License field
# stays correct. We need copies, not symlinks, so that the “graft” in
# MANIFEST.in works.
mkdir -p grpc_root/src
for srcdir in compiler
do
  cp -rp "../../../../src/${srcdir}" "grpc_root/src/"
done
cp -rp '../../../../include' 'grpc_root/'
# We must set GRPC_PYTHON_CFLAGS and GRPC_PYTHON_LDFLAGS again; grpcio_tools
# does not have the same default upstream flags as grpcio does, and it needs to
# link the protobuf compiler library.
export GRPC_PYTHON_CFLAGS="-fno-wrapv -frtti $(pkg-config --cflags protobuf)"
export GRPC_PYTHON_LDFLAGS="$(pkg-config --libs protobuf) -lprotoc"
%pyproject_wheel
# Remove unwanted shebang from grpc_tools.protoc source file, which will be
# installed without an executable bit:
find . -type f -name protoc.py -execdir sed -r -i '1{/^#!/d}' '{}' '+'
%{__python3} %{py_setup} %{?py_setup_args} install \
    -O1 --skip-build --root "${PYROOT}" --prefix %{_prefix}
popd >/dev/null

# ~~ xds_protos ~~
echo '===== Building Python xds_protos package =====' 2>&1
pushd "tools/distrib/python/xds_protos" >/dev/null
%pyproject_wheel
%{__python3} %{py_setup} %{?py_setup_args} install \
      -O1 --skip-build --root "${PYROOT}" --prefix %{_prefix}
popd >/dev/null


echo '===== Building pure-Python packages =====' 1>&2
for suffix in channelz health_checking reflection status testing tests
do
  echo "----> grpcio_${suffix} <----" 1>&2
  pushd "src/python/grpcio_${suffix}/" >/dev/null
  if ! echo "${suffix}" | grep -E "^(admin|csds)$" >/dev/null
  then
    %{__python3} %{py_setup} %{?py_setup_args} preprocess
  fi
  if ! echo "${suffix}" | grep -E "^(admin|csds|testing)$" >/dev/null
  then
    %{__python3} %{py_setup} %{?py_setup_args} build_package_protos
  fi
  %pyproject_wheel
  %{__python3} %{py_setup} %{?py_setup_args} install \
      -O1 --skip-build --root "${PYROOT}" --prefix %{_prefix}
  popd >/dev/null
done


%install
# ~~~~ C (core) and C++ (cpp) ~~~~
%cmake_install

%if %{with core_tests}
# For some reason, grpc_cli is not installed. Do it manually.
install -t '%{buildroot}%{_bindir}' -p -D '%{_vpath_builddir}/grpc_cli'
# grpc_cli build does not respect CMAKE_INSTALL_RPATH
# https://github.com/grpc/grpc/issues/25176
chrpath --delete '%{buildroot}%{_bindir}/grpc_cli'

# This library is also required for grpc_cli; it is built as part of the test
# code.
install -t '%{buildroot}%{_libdir}' -p \
    '%{_vpath_builddir}/libgrpc++_test_config.so.%{cpp_so_version}'
chrpath --delete \
    '%{buildroot}%{_libdir}/libgrpc++_test_config.so.%{cpp_so_version}'

install -d '%{buildroot}/%{_mandir}/man1'
install -t '%{buildroot}/%{_mandir}/man1' -p -m 0644 \
    %{SOURCE100} %{SOURCE101} %{SOURCE102} %{SOURCE103} %{SOURCE104} \
    %{SOURCE106} %{SOURCE107} %{SOURCE108}
%endif

# Remove any static libraries that may have been installed against our wishes
find %{buildroot} -type f -name '*.a' -print -delete
# Fix wrong permissions on installed headers
find %{buildroot}%{_includedir}/grpc* -type f -name '*.h' -perm /0111 \
    -execdir chmod -v a-x '{}' '+'

# ~~~~ Python ~~~~

# Since several packages have an install_requires: grpcio-tools, we must ensure
# the buildroot Python site-packages directories are in the PYTHONPATH.
pushd '%{buildroot}'
PYROOT="${PWD}"
popd
if [ -n "${PYTHONPATH-}" ]; then PYTHONPATH="${PYTHONPATH}:"; fi
PYTHONPATH="${PYTHONPATH-}${PYROOT}%{python3_sitelib}"
PYTHONPATH="${PYTHONPATH}:${PYROOT}%{python3_sitearch}"
export PYTHONPATH

# The grpcio_tests package should not be installed; it would provide top-level
# packages with generic names like “tests” or “tests_aio”.
rm -rvf %{_pyproject_wheeldir}/grpcio_tests-*.whl
rm -rvf %{_pyproject_wheeldir}/xds_protos-*.whl

%pyproject_install

# ~~~~ Miscellaneous ~~~~

# Replace copies of the certificate bundle with symlinks to the shared system
# certificates. This has the following benefits:
#   - Reduces duplication and save space
#   - Respects system-wide administrative trust configuration
#   - Keeps “MPLv2.0” from having to be added to a number of License fields
%global sysbundle /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
# We do not own this file; we temporarily install it in the buildroot so we do
# not have dangling symlinks.
install -D -t "%{buildroot}$(dirname '%{sysbundle}')" -m 0644 '%{sysbundle}'

find '%{buildroot}' -type f -name 'roots.pem' |
  while read -r fn
  do
    ln -s -f "%{buildroot}%{sysbundle}" "${fn}"
    symlinks -c -o "${fn}"
  done

rm -rvf "%{buildroot}$(dirname '%{sysbundle}')"

# ~~ documentation and examples ~~

install -D -t '%{buildroot}%{_pkgdocdir}' -m 0644 -p \
    AUTHORS \
    CONCEPTS.md \
    MAINTAINERS.md \
    README.md \
    SECURITY.md \
    TROUBLESHOOTING.md
cp -rvp doc examples '%{buildroot}%{_pkgdocdir}'
# Hardlink duplicate files in the examples
hardlink -v '%{buildroot}%{_pkgdocdir}/examples/'


%check
%ifarch %{ix86} s390x

cat <<'EOF'
Tests are skipped on these secondary arches:

- i686: not a leaf package so we still build it, but skip tests to avoid
  tracking 32-bit-specific issues (see the F37 ARMv7-retirement and
  i686-leaf-removal changes).
  https://fedoraproject.org/wiki/Changes/RetireARMv7
  https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval

- s390x (big-endian): grpc has open upstream big-endian bugs that fail %check,
  e.g. address_sorting (grpc/grpc#35350), ALTS (grpc/grpc#43067), and
  buffer_list (atomic reads back 1<<32). The 1.75.x suite hits enough of these
  that per-test exclusion is unmaintainable, so skip %check on s390x. Big-endian
  support is tracked upstream (grpc#35350) and with the Fedora s390x WG.
EOF

%else

export FEDORA_NO_NETWORK_TESTS=1

%if %{with core_tests}
PORT_SERVER_PORT="$(awk '
  /_PORT_SERVER_PORT[[:blank:]]*=[[:blank:]]*[[:digit:]]+$/ { print $NF }
' tools/run_tests/python_utils/start_port_server.py)"

# Note that no tests are actually found by ctest:
%ctest

# Exclude tests that are known to hang or otherwise fail. Assistance welcome in
# figuring out what is wrong with these.  Note, however, that we are running
# the tests very differently from upstream, which uses scripts in
# tools/run_tests/ that rebuild the entire source and use Docker, so it is
# likely to be difficult to get help from upstream for any failures here. Note
# that some of these tests would never work in an environment without Internet
# access.
{ sed -r -e '/^(#|$)/d' -e 's|^(.*)$|%{_vpath_builddir}/\1_test|' <<'EOF'

# Requires (or may require) network:
resolve_address_using_ares_resolver
resolve_address_using_ares_resolver_posix
resolve_address_using_native_resolver
resolve_address_using_native_resolver_posix
ssl_transport_security

# Seems to require privilege:
flaky_network

%ifarch ppc64le
# timeout: sending signal KILL to command
#
# Confirmed in 1.74.1 2024-09-10
channel_init
%endif

%if 0%{?fedora} <= 42
# absl_stacktrace is broken on abseil-cpp 20240722.1
examine_stack
stack_tracer
%endif

# TODO: Which architectures? Traceback?
#
# timeout: the monitored command dumped core
#
# Confirmed in 1.74.1 2024-09-10
filter_test

# Unexplained:
#
# [ RUN      ] GrpcToolTest.CallCommandWithTimeoutDeadlineSet
# [libprotobuf ERROR google/protobuf/text_format.cc:335] Error parsing text-format grpc.testing.SimpleRequest: 1:7: Message type "grpc.testing.SimpleRequest" has no field named "redhat".
# Failed to convert text format to proto.
# Failed to parse request.
# /builddir/build/BUILD/grpc-1.48.1/test/cpp/util/grpc_tool_test.cc:915: Failure
# Value of: 0 == GrpcToolMainLib(ArraySize(argv), argv, TestCliCredentials(), std::bind(PrintStream, &output_stream, std::placeholders::_1))
#   Actual: false
# Expected: true
# /builddir/build/BUILD/grpc-1.48.1/test/cpp/util/grpc_tool_test.cc:920: Failure
# Value of: nullptr != strstr(output_stream.str().c_str(), "message: \"true\"")
#   Actual: false
# Expected: true
# [  FAILED  ] GrpcToolTest.CallCommandWithTimeoutDeadlineSet (5 ms)
#
# Confirmed in 1.48.1 2022-09-14
grpc_tool

# TODO: Traceback?
#
# Timeout on aarch64, core dump on x86_64
#
# Confirmed in 1.74.1 2024-09-13
thread_pool

# Unexplained:
#
# [  FAILED  ] XdsTest/XdsServerSecurityTest.TestMtlsWithBothPluginsUpdated/V3BootstrapFromEnvVar, where GetParam() = 20-byte object <00-00 00-93 00-00 00-00 02-00 00-00 02-00 00-00 00-00 00-00>
#
# Confirmed in 1.74.1 2024-09-15
xds_security_end2end

# A timing-sensitive stress test. It spawns up to 1000 threads and requires
# every one of them to finish within a hard-coded 30s timeout, which is not
# met on a loaded or slow builder. It passes on an idle 16-core machine but
# fails in Copr:
#
# [ RUN      ] PartyMpscTest/PartyMpscTest.ManySendersSeeCloseStressTest/Q62000_U31_B0_T1000
# party_mpsc_test.cc:125] Check failed:
#     collector->done[i].WaitForNotificationWithTimeout(absl::Seconds(30))
#
# Confirmed in 1.75.1 2026-10-23
party_mpsc

# These three tests all authenticate against the SPIFFE test PKI in
# test/core/tsi/test_creds/spiffe_end2end/, and its CA certificate expired on
# 2026-03-07:
#
#   $ openssl x509 -in test/core/tsi/test_creds/spiffe_end2end/ca.pem \
#         -noout -subject -enddate
#   subject=C=US, ST=VA, O=Internet Widgits Pty Ltd, CN=foo.bar.hoo.ca.com
#   notAfter=Mar  7 19:34:46 2026 GMT
#
# It is the only expired certificate in the test tree; the leaf certificates
# it signs are valid until 2035. Every TLS handshake in these tests therefore
# fails certificate verification, so the tests cannot pass no matter what we
# do to the build. This is a time bomb in the 1.75.1 tarball rather than
# anything specific to Fedora.
#
# Upstream has since regenerated the whole credential set (the CA on master
# runs 2026-03-09 to 2027-03-09), but with a new key, so the new ca.pem is not
# a drop-in replacement: backporting it means carrying all 23 files of
# test/core/tsi/test_creds/spiffe_end2end/, and buys only until March 2027,
# when the replacement expires in turn. These tests are therefore simply
# skipped. Re-enable them after a rebase to a release whose bundled SPIFFE CA
# is still valid.
#
# Confirmed in 1.75.1 2026-10-24
spiffe_bundle_map_end2end
spiffe_ssl_transport_security
xds_security_spiffe_end2end

EOF
} | xargs -r chmod -v a-x

# Ignore SIGPIPE for the test executables. A disposition of SIG_IGN (unlike a
# signal handler) survives exec, so every test below inherits it.
#
# This is needed because c-ares does the actual socket I/O for the DNS
# resolver, and when gRPC installs its own socket callbacks, the c-ares
# compatibility shim writes with writev() rather than send(..., MSG_NOSIGNAL).
# If the peer has already closed the connection, the test is killed by
# SIGPIPE. For example, cancel_ares_query_test dies in
# CancelDuringAresQuery.TestQueryFailsWithDataRemainingInReadBuffer:
#
#   writev () from /lib64/libc.so.6
#   legacycb_asendto () from /lib64/libcares.so.2
#   ares_socket_write () / ares_conn_flush () / ares_send_query_int ()
#   ares_process_fds () from /lib64/libcares.so.2
#   grpc_event_engine::experimental::AresResolver::OnAresBackupPollAlarm ()
#
# Upstream does not hit this because it builds against its own bundled c-ares.
# Ignoring SIGPIPE is the normal expectation for processes doing socket I/O,
# so this only makes the tests behave like a well-behaved gRPC application.
trap '' PIPE

find %{_vpath_builddir} -type f -perm /0111 -name '*_test' | sort |
  while read -r testexe
  do
    echo "==== $(date -u --iso-8601=ns): $(basename "${testexe}") ===="
    %{__python3} tools/run_tests/start_port_server.py

%if %{without gdb}
    # There is a history of some tests failing by hanging. We use “timeout” so
    # that a test that does hang breaks the build in a vagurely reasonable
    # amount of time. Some tests really can be slow, so the timeout is long!
    timeout -k 61m -v 60m \
%if %{with valgrind}
        valgrind --trace-children=yes --leak-check=full --track-origins=yes \
%endif
        "${testexe}"
%else
    # Script gdb to run the test file and record any backtrace. Note that this
    # reports an error when tests fail, because there is no stack on which to
    # report a backtrace after the test exits successfully, and that this keeps
    # going after a test fails, because we ignore the mentioned error. A
    # cleverer gdb script would be nice, but this is good enough for the
    # intended purpose.
    tee "${testexe}-script.gdb" <<EOF
set pagination off
set logging file ${testexe}-gdb.log
set logging on
file ${testexe}
run
bt -full
set logging off
quit
EOF
    gdb -q -x "${testexe}-script.gdb" --batch </dev/null || :
%endif
  done

# Stop the port server
curl "http://localhost:${PORT_SERVER_PORT}/quitquitquit" || :
%endif

pushd src/python/grpcio_tests
# disabled test_lite because it wants admin and csds and xds_protos, see Obsolete comment
for suite in \
    %{?with_python_aio_tests:test_aio} \
    %{?with_python_gevent_tests:test_gevent} \
    test_py3_only
do
  echo "==== $(date -u --iso-8601=ns): Python ${suite} ===="
  # See the implementation of the %%pytest macro, upon which the following is
  # based. We add a timeout that is rather long, as it must apply to the entire
  # test suite. (Patching in a per-test timeout would be harder.)
  %{py3_test_envvars} timeout -k 31m -v 30m \
      %{python3} %{py_setup} %{?py_setup_args} "${suite}"
done
popd

%endif

%if %{without system_gtest}
# As a sanity check for our claim that gtest/gmock are not bundled, check
# installed executables for symbols that appear to have come from gtest/gmock.
foundgtest=0
if find %{buildroot} -type f -perm /0111 \
      -execdir objdump --syms --dynamic-syms --demangle '{}' '+' 2>/dev/null |
    grep -E '[^:]testing::'
then
  echo 'Found traces of gtest/gmock' 1>&2
  exit 1
fi
%endif


%files
%license LICENSE NOTICE.txt
%{_libdir}/libaddress_sorting.so.%{c_so_version}{,.*}
%{_libdir}/libgpr.so.%{c_so_version}{,.*}
%{_libdir}/libgrpc.so.%{c_so_version}{,.*}
%{_libdir}/libgrpc_unsecure.so.%{c_so_version}{,.*}


%files data
%license LICENSE NOTICE.txt
%dir %{_datadir}/grpc/
%{_datadir}/grpc/roots.pem


%files doc
%license LICENSE NOTICE.txt

%doc %{_pkgdocdir}/AUTHORS
%doc %{_pkgdocdir}/CONCEPTS.md
%doc %{_pkgdocdir}/MAINTAINERS.md
%doc %{_pkgdocdir}/README.md
%doc %{_pkgdocdir}/SECURITY.md
%doc %{_pkgdocdir}/TROUBLESHOOTING.md

%doc %{_pkgdocdir}/doc/
%doc %{_pkgdocdir}/examples/



%files cpp
%{_libdir}/libgrpc++.so.%{cpp_so_version}{,.*}
%{_libdir}/libgrpc++_alts.so.%{cpp_so_version}{,.*}
%{_libdir}/libgrpc++_error_details.so.%{cpp_so_version}{,.*}
%{_libdir}/libgrpc++_reflection.so.%{cpp_so_version}{,.*}
%{_libdir}/libgrpc++_unsecure.so.%{cpp_so_version}{,.*}
%{_libdir}/libgrpc_authorization_provider.so.%{cpp_so_version}{,.*}
%{_libdir}/libgrpc_plugin_support.so.%{cpp_so_version}{,.*}

%{_libdir}/libgrpcpp_channelz.so.%{cpp_so_version}{,.*}


%if %{with core_tests}
%files cli
%{_bindir}/grpc_cli
%{_libdir}/libgrpc++_test_config.so.%{cpp_so_version}
%{_mandir}/man1/grpc_cli.1*
%{_mandir}/man1/grpc_cli-*.1*
%endif


%files plugins
# These are for program use and do not offer a CLI for the end user, so they
# should really be in %%{_libexecdir}; however, too many downstream users
# expect them in $PATH to change this for the time being.
%{_bindir}/grpc_*_plugin


%files devel
%{_libdir}/libaddress_sorting.so
%{_libdir}/libgpr.so
%{_libdir}/libgrpc.so
%{_libdir}/libgrpc_authorization_provider.so
%{_libdir}/libgrpc_unsecure.so

%{_includedir}/grpc/
%{_libdir}/pkgconfig/gpr.pc
%{_libdir}/pkgconfig/grpc.pc
%{_libdir}/pkgconfig/grpc_unsecure.pc
%{_libdir}/cmake/grpc/

%{_libdir}/libgrpc++.so
%{_libdir}/libgrpc++_alts.so
%{_libdir}/libgrpc++_error_details.so
%{_libdir}/libgrpc++_reflection.so
%{_libdir}/libgrpc++_unsecure.so
%{_libdir}/libgrpc_plugin_support.so
%{_includedir}/grpc++/
%{_libdir}/pkgconfig/grpc++.pc
%{_libdir}/pkgconfig/grpc++_unsecure.pc

%{_libdir}/libgrpcpp_channelz.so
%{_includedir}/grpcpp/


%files -n python3-grpcio
%{python3_sitearch}/grpc/
%{python3_sitearch}/grpcio-%{pyversion}.dist-info/
%license LICENSE NOTICE.txt


%files -n python3-grpcio-tools
%{_bindir}/python-grpc-tools-protoc
%{python3_sitearch}/grpc_tools/
%{python3_sitearch}/grpcio_tools-%{pyversion}.dist-info/
%license LICENSE NOTICE.txt


%files -n python3-grpcio-channelz
%{python3_sitelib}/grpc_channelz/
%{python3_sitelib}/grpcio_channelz-%{pyversion}.dist-info/


%files -n python3-grpcio-health-checking
%{python3_sitelib}/grpc_health/
%{python3_sitelib}/grpcio_health_checking-%{pyversion}.dist-info/


%files -n python3-grpcio-reflection
%{python3_sitelib}/grpc_reflection/
%{python3_sitelib}/grpcio_reflection-%{pyversion}.dist-info/


%files -n python3-grpcio-status
%{python3_sitelib}/grpc_status/
%{python3_sitelib}/grpcio_status-%{pyversion}.dist-info/


%files -n python3-grpcio-testing
%{python3_sitelib}/grpc_testing/
%{python3_sitelib}/grpcio_testing-%{pyversion}.dist-info/


%changelog
%autochangelog
