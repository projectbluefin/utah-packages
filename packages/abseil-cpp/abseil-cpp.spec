# Disable the mingw cross-build: it doubles the build to 90+ minutes and the
# Windows DLLs are never used by Hummingbird consumers. Fedora enables it, but
# this factory only needs the native libraries (mozc links absl).
%bcond mingw 0

# Installed library version
%global lib_version 2605.0.0

Name:           abseil-cpp
Version:        20260526.0
Release:        %autorelease
Summary:        C++ Common Libraries

# The entire source is Apache-2.0, except:
#   - The following files are LicenseRef-Fedora-Public-Domain:
#       absl/time/internal/cctz/src/tzfile.h
#         ** This file is in the public domain, so clarified as of
#         ** 1996-06-05 by Arthur David Olson.
#       absl/time/internal/cctz/testdata/zoneinfo/iso3166.tab
#         # This file is in the public domain, so clarified as of
#         # 2009-05-17 by Arthur David Olson.
#       absl/time/internal/cctz/testdata/zoneinfo/zone1970.tab
#         # This file is in the public domain.
#     Public-domain license text for these files was added to the
#     public-domain-text.txt file in fedora-license-data in commit
#     538bc87d5e3c1cb08e81d690ce4122e1273dc9cd
#     (https://gitlab.com/fedora/legal/fedora-license-data/-/merge_requests/205).
License:        Apache-2.0 AND LicenseRef-Fedora-Public-Domain
URL:            https://abseil.io
Source:         https://github.com/abseil/abseil-cpp/archive/%{version}/%{name}-%{version}.tar.gz

# Omit the “bind” block in test Test Mutex::FunctorCondition
#
# Work around failure to compile with GCC 16,
# https://github.com/abseil/abseil-cpp/issues/1992.
Patch:          0001-Omit-the-bind-block-in-test-Test-Mutex-FunctorCondit.patch

# PR #2071: Include immintrin.h instead of bmi2intrin.h
# https://github.com/abseil/abseil-cpp/commit/d851fdd768b27c02b3fb786fd0987faddd279ece
#
# Fixes failure to build with GCC 16 when the BMI2 extensions are enabled,
# e.g., when targeting x86_64-v3 on ELN/RHEL.
Patch:          https://github.com/abseil/abseil-cpp/commit/d851fdd768b27c02b3fb786fd0987faddd279ece.patch

BuildRequires:  cmake
# The default make backend would work just as well; ninja is observably faster
BuildRequires:  ninja-build
BuildRequires:  gcc-c++

BuildRequires:  gmock-devel
BuildRequires:  gtest-devel

%if %{with mingw}
BuildRequires:  mingw32-filesystem
BuildRequires:  mingw32-gcc-c++

BuildRequires:  mingw64-filesystem
BuildRequires:  mingw64-gcc-c++
%endif

# The contents of absl/time/internal/cctz are derived from
# https://github.com/google/cctz (https://src.fedoraproject.org/rpms/cctz), but
# have been forked with Abseil-specific changes. It is not obvious from which
# particular version of CCTZ these sources are derived. Upstream was asked
# about a path to supporting a system copy as required by bundling guidelines:
#   Please comment on CCTZ bundling
#   https://github.com/abseil/abseil-cpp/discussions/1415
# They refused, for the time being, as follows:
#   “[…] we have no plans to change this decision, but we reserve the right to
#   change our minds.”
Provides:       bundled(cctz)

%ifarch s390x
# Symbolize.SymbolizeWithMultipleMaps fails in absl_symbolize_test on s390x
# with LTO
# https://github.com/abseil/abseil-cpp/issues/1133
%global _lto_cflags %{nil}
%endif

%description
Abseil is an open-source collection of C++ library code designed to augment
the C++ standard library. The Abseil library code is collected from
Google's own C++ code base, has been extensively tested and used in
production, and is the same code we depend on in our daily coding lives.

In some cases, Abseil provides pieces missing from the C++ standard; in
others, Abseil provides alternatives to the standard for special needs we've
found through usage in the Google code base. We denote those cases clearly
within the library code we provide you.

Abseil is not meant to be a competitor to the standard library; we've just
found that many of these utilities serve a purpose within our code base,
and we now want to provide those resources to the C++ community as a whole.

# The factory deliberately skips Abseil's test-only libraries. They are not
# runtime dependencies, and building their full test graph exceeds the
# hermetic runner's memory budget. Keep the upstream subpackage definition out
# of the generated spec rather than claiming unavailable libraries exist.
%if 0
%package testing
Summary:        Libraries needed for running tests on the installed %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

Provides:       bundled(cctz)

%description testing
%{summary}.
%endif

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

# Some of the headers from CCTZ are part of the -devel subpackage. See the
# corresponding virtual Provides in the base package for full details.
Provides:       bundled(cctz)

%description devel
Development headers for %{name}

%if %{with mingw}
%package -n mingw32-abseil-cpp
Summary:        MinGW Windows abseil-cpp library
BuildArch:      noarch

%description -n mingw32-abseil-cpp
MinGW Windows abseil-cpp library.

%package -n mingw64-abseil-cpp
Summary:        MinGW Windows abseil-cpp library
BuildArch:      noarch

%description -n mingw64-abseil-cpp
MinGW Windows abseil-cpp library.

%{?mingw_debug_package}
%endif

%prep
%autosetup -p1 -S gendiff

%build
# Test-only libraries are not part of the factory's runtime remit. Skipping
# their graph avoids an LTO-heavy build that OOMs the hermetic runner; runtime
# consumers (such as mozc) link the regular Abseil libraries. RPM_BUILD_NCPUS
# caps ninja parallelism.
#
# Fedora builds these ON, for its -testing subpackage. Turning them off here
# is therefore a deviation with one known consumer: protobuf configures test
# targets against absl::scoped_mock_log, which this build does not export, so
# packages/protobuf sets protobuf_BUILD_TESTS OFF to match. Anything else that
# wants a test-only Abseil target will fail the same way and needs the same
# treatment, or this option has to go back to ON.
%cmake \
    -GNinja \
    -DABSL_USE_EXTERNAL_GOOGLETEST:BOOL=ON \
    -DABSL_FIND_GOOGLETEST:BOOL=ON \
    -DABSL_ENABLE_INSTALL:BOOL=ON \
    -DABSL_BUILD_TESTING:BOOL=OFF \
    -DABSL_BUILD_TEST_HELPERS:BOOL=OFF \
    -DCMAKE_BUILD_TYPE:STRING=None \
    -DCMAKE_CXX_STANDARD:STRING=17
RPM_BUILD_NCPUS=2 %cmake_build

%if %{with mingw}
%mingw_cmake \
    -DABSL_BUILD_TESTING:BOOL=OFF \
    -GNinja
%mingw_ninja --verbose
%endif

%install
%cmake_install

%if %{with mingw}
%mingw_ninja_install
%mingw_debug_install_post
%endif

%check
skips='^($.'
%ifarch ppc64le %{ix86}
# [Bug]: Flaky test failures in absl_failure_signal_handler_test on ppc64le in
# Fedora
# https://github.com/abseil/abseil-cpp/issues/1804
skips="${skips}|absl_failure_signal_handler_test"
# [Bug]: StackTrace.NestedSignal in absl_stacktrace_test fails on ppc64le since
# 20250184.0
# https://github.com/abseil/abseil-cpp/issues/1925
skips="${skips}|absl_stacktrace_test"
%endif
skips="${skips})$"

%ctest --exclude-regex "${skips}"

%files
%license LICENSE
%doc FAQ.md README.md UPGRADES.md
# All shared libraries except installed TESTONLY libraries; see the %%files
# list for the -testing subpackage for those.
%{_libdir}/libabsl_base.so.%{lib_version}
%{_libdir}/libabsl_city.so.%{lib_version}
%{_libdir}/libabsl_civil_time.so.%{lib_version}
%{_libdir}/libabsl_clock_interface.so.%{lib_version}
%{_libdir}/libabsl_cord.so.%{lib_version}
%{_libdir}/libabsl_cord_internal.so.%{lib_version}
%{_libdir}/libabsl_cordz_functions.so.%{lib_version}
%{_libdir}/libabsl_cordz_handle.so.%{lib_version}
%{_libdir}/libabsl_cordz_info.so.%{lib_version}
%{_libdir}/libabsl_cordz_sample_token.so.%{lib_version}
%{_libdir}/libabsl_crc32c.so.%{lib_version}
%{_libdir}/libabsl_crc_cord_state.so.%{lib_version}
%{_libdir}/libabsl_crc_cpu_detect.so.%{lib_version}
%{_libdir}/libabsl_crc_internal.so.%{lib_version}
%{_libdir}/libabsl_debugging_internal.so.%{lib_version}
%{_libdir}/libabsl_decode_rust_punycode.so.%{lib_version}
%{_libdir}/libabsl_demangle_internal.so.%{lib_version}
%{_libdir}/libabsl_demangle_rust.so.%{lib_version}
%{_libdir}/libabsl_die_if_null.so.%{lib_version}
%{_libdir}/libabsl_examine_stack.so.%{lib_version}
%{_libdir}/libabsl_exponential_biased.so.%{lib_version}
%{_libdir}/libabsl_failure_signal_handler.so.%{lib_version}
%{_libdir}/libabsl_flags_commandlineflag.so.%{lib_version}
%{_libdir}/libabsl_flags_commandlineflag_internal.so.%{lib_version}
%{_libdir}/libabsl_flags_config.so.%{lib_version}
%{_libdir}/libabsl_flags_internal.so.%{lib_version}
%{_libdir}/libabsl_flags_marshalling.so.%{lib_version}
%{_libdir}/libabsl_flags_parse.so.%{lib_version}
%{_libdir}/libabsl_flags_private_handle_accessor.so.%{lib_version}
%{_libdir}/libabsl_flags_program_name.so.%{lib_version}
%{_libdir}/libabsl_flags_reflection.so.%{lib_version}
%{_libdir}/libabsl_flags_usage.so.%{lib_version}
%{_libdir}/libabsl_flags_usage_internal.so.%{lib_version}
%{_libdir}/libabsl_generic_printer_internal.so.%{lib_version}
%{_libdir}/libabsl_graphcycles_internal.so.%{lib_version}
%{_libdir}/libabsl_hash.so.%{lib_version}
%{_libdir}/libabsl_hashtable_profiler.so.%{lib_version}
%{_libdir}/libabsl_hashtablez_sampler.so.%{lib_version}
%{_libdir}/libabsl_int128.so.%{lib_version}
%{_libdir}/libabsl_kernel_timeout_internal.so.%{lib_version}
%{_libdir}/libabsl_leak_check.so.%{lib_version}
%{_libdir}/libabsl_log_entry.so.%{lib_version}
%{_libdir}/libabsl_log_flags.so.%{lib_version}
%{_libdir}/libabsl_log_globals.so.%{lib_version}
%{_libdir}/libabsl_log_initialize.so.%{lib_version}
%{_libdir}/libabsl_log_internal_check_op.so.%{lib_version}
%{_libdir}/libabsl_log_internal_conditions.so.%{lib_version}
%{_libdir}/libabsl_log_internal_fnmatch.so.%{lib_version}
%{_libdir}/libabsl_log_internal_format.so.%{lib_version}
%{_libdir}/libabsl_log_internal_globals.so.%{lib_version}
%{_libdir}/libabsl_log_internal_log_sink_set.so.%{lib_version}
%{_libdir}/libabsl_log_internal_message.so.%{lib_version}
%{_libdir}/libabsl_log_internal_nullguard.so.%{lib_version}
%{_libdir}/libabsl_log_internal_proto.so.%{lib_version}
%{_libdir}/libabsl_log_internal_structured_proto.so.%{lib_version}
%{_libdir}/libabsl_log_severity.so.%{lib_version}
%{_libdir}/libabsl_log_sink.so.%{lib_version}
%{_libdir}/libabsl_malloc_internal.so.%{lib_version}
%{_libdir}/libabsl_periodic_sampler.so.%{lib_version}
%{_libdir}/libabsl_poison.so.%{lib_version}
%{_libdir}/libabsl_profile_builder.so.%{lib_version}
%{_libdir}/libabsl_random_distributions.so.%{lib_version}
%{_libdir}/libabsl_random_internal_distribution_test_util.so.%{lib_version}
%{_libdir}/libabsl_random_internal_entropy_pool.so.%{lib_version}
%{_libdir}/libabsl_random_internal_platform.so.%{lib_version}
%{_libdir}/libabsl_random_internal_randen.so.%{lib_version}
%{_libdir}/libabsl_random_internal_randen_hwaes.so.%{lib_version}
%{_libdir}/libabsl_random_internal_randen_hwaes_impl.so.%{lib_version}
%{_libdir}/libabsl_random_internal_randen_slow.so.%{lib_version}
%{_libdir}/libabsl_random_internal_seed_material.so.%{lib_version}
%{_libdir}/libabsl_random_seed_gen_exception.so.%{lib_version}
%{_libdir}/libabsl_random_seed_sequences.so.%{lib_version}
%{_libdir}/libabsl_raw_hash_set.so.%{lib_version}
%{_libdir}/libabsl_raw_logging_internal.so.%{lib_version}
%{_libdir}/libabsl_scoped_set_env.so.%{lib_version}
%{_libdir}/libabsl_source_location.so.%{lib_version}
%{_libdir}/libabsl_spinlock_wait.so.%{lib_version}
%{_libdir}/libabsl_stacktrace.so.%{lib_version}
%{_libdir}/libabsl_status.so.%{lib_version}
%{_libdir}/libabsl_status_builder.so.%{lib_version}
%{_libdir}/libabsl_statusor.so.%{lib_version}
%{_libdir}/libabsl_str_format_internal.so.%{lib_version}
%{_libdir}/libabsl_strerror.so.%{lib_version}
%{_libdir}/libabsl_strings.so.%{lib_version}
%{_libdir}/libabsl_strings_internal.so.%{lib_version}
%{_libdir}/libabsl_symbolize.so.%{lib_version}
%{_libdir}/libabsl_synchronization.so.%{lib_version}
%{_libdir}/libabsl_throw_delegate.so.%{lib_version}
%{_libdir}/libabsl_time.so.%{lib_version}
%{_libdir}/libabsl_time_zone.so.%{lib_version}
%{_libdir}/libabsl_tracing_internal.so.%{lib_version}
%{_libdir}/libabsl_utf8_for_code_point.so.%{lib_version}
%{_libdir}/libabsl_vlog_config_internal.so.%{lib_version}

%if 0
%files testing
%endif

%files devel
%{_includedir}/absl
%{_libdir}/libabsl_*.so
%{_libdir}/cmake/absl
%{_libdir}/pkgconfig/absl_*.pc

%if %{with mingw}
%files -n mingw32-abseil-cpp
%license LICENSE
%{mingw32_bindir}/libabsl_base.dll
%{mingw32_bindir}/libabsl_city.dll
%{mingw32_bindir}/libabsl_civil_time.dll
%{mingw32_bindir}/libabsl_clock_interface.dll
%{mingw32_bindir}/libabsl_cord.dll
%{mingw32_bindir}/libabsl_cord_internal.dll
%{mingw32_bindir}/libabsl_cordz_functions.dll
%{mingw32_bindir}/libabsl_cordz_handle.dll
%{mingw32_bindir}/libabsl_cordz_info.dll
%{mingw32_bindir}/libabsl_cordz_sample_token.dll
%{mingw32_bindir}/libabsl_crc32c.dll
%{mingw32_bindir}/libabsl_crc_cord_state.dll
%{mingw32_bindir}/libabsl_crc_cpu_detect.dll
%{mingw32_bindir}/libabsl_crc_internal.dll
%{mingw32_bindir}/libabsl_debugging_internal.dll
%{mingw32_bindir}/libabsl_decode_rust_punycode.dll
%{mingw32_bindir}/libabsl_demangle_internal.dll
%{mingw32_bindir}/libabsl_demangle_rust.dll
%{mingw32_bindir}/libabsl_die_if_null.dll
%{mingw32_bindir}/libabsl_examine_stack.dll
%{mingw32_bindir}/libabsl_exponential_biased.dll
%{mingw32_bindir}/libabsl_failure_signal_handler.dll
%{mingw32_bindir}/libabsl_flags_commandlineflag.dll
%{mingw32_bindir}/libabsl_flags_commandlineflag_internal.dll
%{mingw32_bindir}/libabsl_flags_config.dll
%{mingw32_bindir}/libabsl_flags_internal.dll
%{mingw32_bindir}/libabsl_flags_marshalling.dll
%{mingw32_bindir}/libabsl_flags_parse.dll
%{mingw32_bindir}/libabsl_flags_private_handle_accessor.dll
%{mingw32_bindir}/libabsl_flags_program_name.dll
%{mingw32_bindir}/libabsl_flags_reflection.dll
%{mingw32_bindir}/libabsl_flags_usage.dll
%{mingw32_bindir}/libabsl_flags_usage_internal.dll
%{mingw32_bindir}/libabsl_generic_printer_internal.dll
%{mingw32_bindir}/libabsl_graphcycles_internal.dll
%{mingw32_bindir}/libabsl_hash.dll
%{mingw32_bindir}/libabsl_hashtable_profiler.dll
%{mingw32_bindir}/libabsl_hashtablez_sampler.dll
%{mingw32_bindir}/libabsl_int128.dll
%{mingw32_bindir}/libabsl_kernel_timeout_internal.dll
%{mingw32_bindir}/libabsl_leak_check.dll
%{mingw32_bindir}/libabsl_log_entry.dll
%{mingw32_bindir}/libabsl_log_flags.dll
%{mingw32_bindir}/libabsl_log_globals.dll
%{mingw32_bindir}/libabsl_log_initialize.dll
%{mingw32_bindir}/libabsl_log_internal_check_op.dll
%{mingw32_bindir}/libabsl_log_internal_conditions.dll
%{mingw32_bindir}/libabsl_log_internal_fnmatch.dll
%{mingw32_bindir}/libabsl_log_internal_format.dll
%{mingw32_bindir}/libabsl_log_internal_globals.dll
%{mingw32_bindir}/libabsl_log_internal_log_sink_set.dll
%{mingw32_bindir}/libabsl_log_internal_message.dll
%{mingw32_bindir}/libabsl_log_internal_nullguard.dll
%{mingw32_bindir}/libabsl_log_internal_proto.dll
%{mingw32_bindir}/libabsl_log_internal_structured_proto.dll
%{mingw32_bindir}/libabsl_log_severity.dll
%{mingw32_bindir}/libabsl_log_sink.dll
%{mingw32_bindir}/libabsl_malloc_internal.dll
%{mingw32_bindir}/libabsl_periodic_sampler.dll
%{mingw32_bindir}/libabsl_poison.dll
%{mingw32_bindir}/libabsl_profile_builder.dll
%{mingw32_bindir}/libabsl_random_distributions.dll
%{mingw32_bindir}/libabsl_random_internal_distribution_test_util.dll
%{mingw32_bindir}/libabsl_random_internal_entropy_pool.dll
%{mingw32_bindir}/libabsl_random_internal_platform.dll
%{mingw32_bindir}/libabsl_random_internal_randen.dll
%{mingw32_bindir}/libabsl_random_internal_randen_hwaes.dll
%{mingw32_bindir}/libabsl_random_internal_randen_hwaes_impl.dll
%{mingw32_bindir}/libabsl_random_internal_randen_slow.dll
%{mingw32_bindir}/libabsl_random_internal_seed_material.dll
%{mingw32_bindir}/libabsl_random_seed_gen_exception.dll
%{mingw32_bindir}/libabsl_random_seed_sequences.dll
%{mingw32_bindir}/libabsl_raw_hash_set.dll
%{mingw32_bindir}/libabsl_raw_logging_internal.dll
%{mingw32_bindir}/libabsl_scoped_set_env.dll
%{mingw32_bindir}/libabsl_source_location.dll
%{mingw32_bindir}/libabsl_spinlock_wait.dll
%{mingw32_bindir}/libabsl_stacktrace.dll
%{mingw32_bindir}/libabsl_status.dll
%{mingw32_bindir}/libabsl_status_builder.dll
%{mingw32_bindir}/libabsl_statusor.dll
%{mingw32_bindir}/libabsl_strerror.dll
%{mingw32_bindir}/libabsl_str_format_internal.dll
%{mingw32_bindir}/libabsl_strings.dll
%{mingw32_bindir}/libabsl_strings_internal.dll
%{mingw32_bindir}/libabsl_symbolize.dll
%{mingw32_bindir}/libabsl_synchronization.dll
%{mingw32_bindir}/libabsl_throw_delegate.dll
%{mingw32_bindir}/libabsl_time.dll
%{mingw32_bindir}/libabsl_time_zone.dll
%{mingw32_bindir}/libabsl_tracing_internal.dll
%{mingw32_bindir}/libabsl_utf8_for_code_point.dll
%{mingw32_bindir}/libabsl_vlog_config_internal.dll
%{mingw32_includedir}/absl/
%{mingw32_libdir}/libabsl_*.dll.a
%{mingw32_libdir}/cmake/absl/
%{mingw32_libdir}/pkgconfig/absl_*.pc

%files -n mingw64-abseil-cpp
%license LICENSE
%{mingw64_bindir}/libabsl_base.dll
%{mingw64_bindir}/libabsl_city.dll
%{mingw64_bindir}/libabsl_civil_time.dll
%{mingw64_bindir}/libabsl_clock_interface.dll
%{mingw64_bindir}/libabsl_cord.dll
%{mingw64_bindir}/libabsl_cord_internal.dll
%{mingw64_bindir}/libabsl_cordz_functions.dll
%{mingw64_bindir}/libabsl_cordz_handle.dll
%{mingw64_bindir}/libabsl_cordz_info.dll
%{mingw64_bindir}/libabsl_cordz_sample_token.dll
%{mingw64_bindir}/libabsl_crc32c.dll
%{mingw64_bindir}/libabsl_crc_cord_state.dll
%{mingw64_bindir}/libabsl_crc_cpu_detect.dll
%{mingw64_bindir}/libabsl_crc_internal.dll
%{mingw64_bindir}/libabsl_debugging_internal.dll
%{mingw64_bindir}/libabsl_decode_rust_punycode.dll
%{mingw64_bindir}/libabsl_demangle_internal.dll
%{mingw64_bindir}/libabsl_demangle_rust.dll
%{mingw64_bindir}/libabsl_die_if_null.dll
%{mingw64_bindir}/libabsl_examine_stack.dll
%{mingw64_bindir}/libabsl_exponential_biased.dll
%{mingw64_bindir}/libabsl_failure_signal_handler.dll
%{mingw64_bindir}/libabsl_flags_commandlineflag.dll
%{mingw64_bindir}/libabsl_flags_commandlineflag_internal.dll
%{mingw64_bindir}/libabsl_flags_config.dll
%{mingw64_bindir}/libabsl_flags_internal.dll
%{mingw64_bindir}/libabsl_flags_marshalling.dll
%{mingw64_bindir}/libabsl_flags_parse.dll
%{mingw64_bindir}/libabsl_flags_private_handle_accessor.dll
%{mingw64_bindir}/libabsl_flags_program_name.dll
%{mingw64_bindir}/libabsl_flags_reflection.dll
%{mingw64_bindir}/libabsl_flags_usage.dll
%{mingw64_bindir}/libabsl_flags_usage_internal.dll
%{mingw64_bindir}/libabsl_generic_printer_internal.dll
%{mingw64_bindir}/libabsl_graphcycles_internal.dll
%{mingw64_bindir}/libabsl_hash.dll
%{mingw64_bindir}/libabsl_hashtable_profiler.dll
%{mingw64_bindir}/libabsl_hashtablez_sampler.dll
%{mingw64_bindir}/libabsl_int128.dll
%{mingw64_bindir}/libabsl_kernel_timeout_internal.dll
%{mingw64_bindir}/libabsl_leak_check.dll
%{mingw64_bindir}/libabsl_log_entry.dll
%{mingw64_bindir}/libabsl_log_flags.dll
%{mingw64_bindir}/libabsl_log_globals.dll
%{mingw64_bindir}/libabsl_log_initialize.dll
%{mingw64_bindir}/libabsl_log_internal_check_op.dll
%{mingw64_bindir}/libabsl_log_internal_conditions.dll
%{mingw64_bindir}/libabsl_log_internal_fnmatch.dll
%{mingw64_bindir}/libabsl_log_internal_format.dll
%{mingw64_bindir}/libabsl_log_internal_globals.dll
%{mingw64_bindir}/libabsl_log_internal_log_sink_set.dll
%{mingw64_bindir}/libabsl_log_internal_message.dll
%{mingw64_bindir}/libabsl_log_internal_nullguard.dll
%{mingw64_bindir}/libabsl_log_internal_proto.dll
%{mingw64_bindir}/libabsl_log_internal_structured_proto.dll
%{mingw64_bindir}/libabsl_log_severity.dll
%{mingw64_bindir}/libabsl_log_sink.dll
%{mingw64_bindir}/libabsl_malloc_internal.dll
%{mingw64_bindir}/libabsl_periodic_sampler.dll
%{mingw64_bindir}/libabsl_poison.dll
%{mingw64_bindir}/libabsl_profile_builder.dll
%{mingw64_bindir}/libabsl_random_distributions.dll
%{mingw64_bindir}/libabsl_random_internal_distribution_test_util.dll
%{mingw64_bindir}/libabsl_random_internal_entropy_pool.dll
%{mingw64_bindir}/libabsl_random_internal_platform.dll
%{mingw64_bindir}/libabsl_random_internal_randen.dll
%{mingw64_bindir}/libabsl_random_internal_randen_hwaes.dll
%{mingw64_bindir}/libabsl_random_internal_randen_hwaes_impl.dll
%{mingw64_bindir}/libabsl_random_internal_randen_slow.dll
%{mingw64_bindir}/libabsl_random_internal_seed_material.dll
%{mingw64_bindir}/libabsl_random_seed_gen_exception.dll
%{mingw64_bindir}/libabsl_random_seed_sequences.dll
%{mingw64_bindir}/libabsl_raw_hash_set.dll
%{mingw64_bindir}/libabsl_raw_logging_internal.dll
%{mingw64_bindir}/libabsl_scoped_set_env.dll
%{mingw64_bindir}/libabsl_source_location.dll
%{mingw64_bindir}/libabsl_spinlock_wait.dll
%{mingw64_bindir}/libabsl_stacktrace.dll
%{mingw64_bindir}/libabsl_status.dll
%{mingw64_bindir}/libabsl_status_builder.dll
%{mingw64_bindir}/libabsl_statusor.dll
%{mingw64_bindir}/libabsl_strerror.dll
%{mingw64_bindir}/libabsl_str_format_internal.dll
%{mingw64_bindir}/libabsl_strings.dll
%{mingw64_bindir}/libabsl_strings_internal.dll
%{mingw64_bindir}/libabsl_symbolize.dll
%{mingw64_bindir}/libabsl_synchronization.dll
%{mingw64_bindir}/libabsl_throw_delegate.dll
%{mingw64_bindir}/libabsl_time.dll
%{mingw64_bindir}/libabsl_time_zone.dll
%{mingw64_bindir}/libabsl_tracing_internal.dll
%{mingw64_bindir}/libabsl_utf8_for_code_point.dll
%{mingw64_bindir}/libabsl_vlog_config_internal.dll
%{mingw64_includedir}/absl/
%{mingw64_libdir}/libabsl_*.dll.a
%{mingw64_libdir}/cmake/absl/
%{mingw64_libdir}/pkgconfig/absl_*.pc
%endif

%changelog
%autochangelog
