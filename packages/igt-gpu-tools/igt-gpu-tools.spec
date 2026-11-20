#%%global gitcommit 45da871dd2684227e93a2fc002b87dfc58bd5fd9
#%%global gitdate 20230215
#%%global gitrev .%%{gitdate}git%%(c=%%{gitcommit}; echo ${c:0:7})

# silent rpmlint
%undefine _debugsource_packages

Name:           igt-gpu-tools
Version:        2.5
Release:        %autorelease
Summary:        Test suite and tools for DRM drivers

# MIT AND ISC:
#  - COPYING
# GPL-1.0-or-later WITH Linux-syscall-note:
#  - include/linux-uapi/sync_file.h
# GPL-2.0-only OR MIT:
#  - docs/testplan/conf.py
#  - lib/igt_vmwgfx.c
#  - lib/igt_vmwgfx.h
#  - lib/svga/
#  - scripts/code_cov_gather_on_test
#  - scripts/doc_to_xls.py
#  - scripts/gen_rst_index
#  - scripts/igt_doc.py
#  - scripts/test_list.py
#  - scripts/xls_to_doc.py
#  - tests/vmwgfx/vmw_execution_buffer.c
#  - tests/vmwgfx/vmw_prime.c
#  - tests/vmwgfx/vmw_ref_count.c
#  - tools/intel-gfx-fw-info
# GPL-2.0-only WITH Linux-syscall-note OR MIT
#  - include/drm-uapi/lima_drm.h
#  - include/drm-uapi/pvr_drm.h
#  - include/drm-uapi/vmwgfx_drm.h
# GPL-2.0-or-later WITH Linux-syscall-note:
#  - include/drm-uapi/armada_drm.h
#  - include/drm-uapi/etnaviv_drm.h
#  - include/drm-uapi/exynos_drm.h
#  - include/drm-uapi/habanalabs_accel.h
#  - include/drm-uapi/ivpu_accel.h
#  - include/drm-uapi/omap_drm.h
#  - include/drm-uapi/qaic_accel.h
# HPND-sell-variant:
#  - assembler/brw_disasm.c
#  - assembler/disasm-main.c
#  - assembler/gen8_disasm.c
# ICU:
#  - overlay/x11/dri2.c
# ISC:
#  - lib/uwildmat/uwildmat.c
# MIT AND LGPL-3.0-or-later:
#  - assembler/ralloc.h
# X11:
#  - lib/igt_map.c
License:        (MIT AND ISC) AND (GPL-1.0-or-later WITH Linux-syscall-note) AND (GPL-2.0-only OR MIT) AND (GPL-2.0-only WITH Linux-syscall-note OR MIT) AND GPL-2.0-or-later WITH Linux-syscall-note AND HPND-sell-variant AND ICU AND ISC AND (MIT AND LGPL-3.0-or-later) AND X11
URL:            https://gitlab.freedesktop.org/drm/igt-gpu-tools

%if 0%{?gitdate}
Source0:        igt-gpu-tools-%{gitdate}.tar.bz2
%else
Source0:        https://www.x.org/archive/individual/app/%{name}-%{version}.tar.xz
%endif

%global provobs_version 2.99.917-42.20180618
Provides:       xorg-x11-drv-intel-devel = %{provobs_version}
Provides:       intel-gpu-tools = %{provobs_version}
Obsoletes:      xorg-x11-drv-intel-devel < %{provobs_version}
Obsoletes:      intel-gpu-tools < %{provobs_version}

BuildRequires:  bison
BuildRequires:  flex
BuildRequires:  gcc
BuildRequires:  kernel-headers
BuildRequires:  meson >= 0.51.0
BuildRequires:  pkgconfig(alsa)
BuildRequires:  pkgconfig(cairo) > 1.12.0
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gsl)
BuildRequires:  pkgconfig(gtk-doc)
BuildRequires:  pkgconfig(jansson)
BuildRequires:  pkgconfig(libcurl)
BuildRequires:  pkgconfig(libdrm) >= 2.4.82
BuildRequires:  pkgconfig(libdw)
BuildRequires:  pkgconfig(libkmod)
BuildRequires:  pkgconfig(liboping)
BuildRequires:  pkgconfig(libproc2)
BuildRequires:  pkgconfig(libudev)
BuildRequires:  pkgconfig(pciaccess) >= 0.10
BuildRequires:  pkgconfig(pixman-1)
BuildRequires:  pkgconfig(valgrind)
BuildRequires:  pkgconfig(xmlrpc)
BuildRequires:  pkgconfig(xmlrpc_client)
BuildRequires:  pkgconfig(xmlrpc_util)
BuildRequires:  pkgconfig(xv)
BuildRequires:  pciutils-devel
BuildRequires:  python3-docutils

# libunwind 1.4.0+ supports s390x
%if 0%{?rhel}
%ifnarch s390x
BuildRequires:  pkgconfig(libunwind)
%endif
%else
BuildRequires:  pkgconfig(libunwind) >= 1.4.0
%endif

%description
igt-gpu-tools (formerly known as intel-gpu-tools) is the standard for writing
test cases for DRM drivers. It also includes a handful of useful tools for
various drivers, such as Intel's GPU tools for i915.

%package docs
Summary:        Documentation for igt-gpu-tools
BuildArch:      noarch

%description docs
Documentation for igt-gpu-tools

%package devel
Summary:        Development files for igt-gpu-tools

%description devel
Development files for compiling against certain tools provided by
igt-gpu-tools, such as i915-perf.

%prep
%autosetup -p1
# Panthor lacks big-endian support and has no Meson toggle.
# Strip it from the build files entirely for s390x and ppc64:
%ifarch s390x ppc64 ppc64le
sed -i -e "/panthor/d" lib/meson.build
sed -i -e "/panthor/d" tests/meson.build
%endif
# Temporarily disable AMDGPU on BE+AArch64 due assembler-related test failures
%ifarch s390x ppc64 ppc64le aarch64
sed -i -e "/amdgpu/d" tests/meson.build
%endif

%build
%if 0%{?rhel}
  %ifarch s390x
    %global with_libunwind disabled
  %else
    %global with_libunwind enabled
  %endif
%else
  %global with_libunwind enabled
%endif

# gcc-11 issues a false positive for accesses to hdmi_vsdb in
# cea_vsdb_get_hdmi_default
# Some explanations here
# - We don't build overlay yet due to Fedora not shipping /usr/bin/leg, but we
#   probably don't care about that anyway
# - We specify -Db_ndebug=false because upstream has explicitly stated that
#   anything else is officially unsupported
# - Attempting to resolve all of the symbols within IGT at executable start
#   causes some of igt's symbols to be resolved in the wrong order, resulting in
#   certain runtime function resolvers (e.g. __attribute__((ifunc))) attempting
#   to call functions which have not been resolved yet - causing everything to
#   segfault. Because of this, we specify "-Dc_link_args=-z lazy" to force lazy
#   symbol resolution.
%meson \
        -Dc_args="-Wno-array-bounds" \
        -Db_ndebug=false \
        -Dc_link_args="-z lazy" \
        -Doverlay=disabled \
        -Dlibunwind=%{with_libunwind}
%meson_build
ninja -C %{_vpath_builddir} igt-gpu-tools-doc

%install
%meson_install
rm %{buildroot}/%{_libdir}/pkgconfig/intel-gen4asm.pc

# Remove the unversioned libigt symlinks
rm %{buildroot}/%{_libdir}/libigt.so

# Fix non-standard executable permissions
find %{buildroot}%{_bindir} -type f -exec chmod 755 {} +
find %{buildroot}%{_libexecdir}/igt-gpu-tools -type f -exec chmod 755 {} +

%check
# The timeout multiplier here is required due to certain tests timing out on
# koji builders that are under heavy load.
# Disable tests on non-x86 due to https://gitlab.freedesktop.org/drm/igt-gpu-tools/-/issues/171
%ifarch %{ix86} x86_64
%meson_test --timeout-multiplier 16
%endif

%files
%license COPYING
%{_bindir}/intel_hdcp
%{_bindir}/intel-gen4asm
%{_bindir}/intel-gen4disasm
%{_libdir}/libigt.so.0
%{_libdir}/libi915_perf.so.*
%{_libdir}/libxe_oa.so.1.*
%{_libexecdir}/igt-gpu-tools/*
%{_datadir}/igt-gpu-tools/*
%{_bindir}/code_cov_capture
%{_bindir}/code_cov_gather_on_build
%{_bindir}/code_cov_gather_on_test
%{_bindir}/code_cov_gen_report
%{_bindir}/code_cov_parse_info
%{_bindir}/dpcd_reg
%{_bindir}/igt_*
%{_bindir}/i915-perf-*
%{_bindir}/intel_audio_dump
%{_bindir}/intel_backlight
%{_bindir}/intel_bios_dumper
%{_bindir}/intel_display_bandwidth
%{_bindir}/intel_display_crc
%{_bindir}/intel_display_poller
%{_bindir}/intel_dp_compliance
%{_bindir}/intel_dump_decode
%{_bindir}/intel_error_decode
%{_bindir}/intel_firmware_decode
%{_bindir}/intel_forcewaked
%{_bindir}/intel_framebuffer_dump
%{_bindir}/intel_gem_info
%{_bindir}/intel_gpu_abrt
%{_bindir}/intel_gpu_frequency
%{_bindir}/intel_gpu_time
%{_bindir}/intel_gpu_top
%{_bindir}/intel_gtt
%{_bindir}/intel_guc_logger
%{_bindir}/intel_gvtg_test
%{_bindir}/intel_infoframes
%{_bindir}/intel_l3_parity
%{_bindir}/intel_lid
%{_bindir}/intel_opregion_decode
%{_bindir}/intel_panel_fitter
%{_bindir}/intel_perf_counters
%{_bindir}/intel_reg
%{_bindir}/intel_reg_checker
%{_bindir}/intel_residency
%{_bindir}/intel_stepping
%{_bindir}/intel_vbt_decode
%{_bindir}/intel_watermark
%{_bindir}/intel_pm_rpm
%{_bindir}/amd_hdmi_compliance
%{_bindir}/msm_dp_compliance
%{_bindir}/lsgpu
%{_bindir}/gputop
%{_bindir}/intel-gfx-fw-info
%{_bindir}/intel_tiling_detect
%{_bindir}/xe-perf-configs
%{_bindir}/xe-perf-control
%{_bindir}/xe-perf-reader
%{_bindir}/xe-perf-recorder
%{_mandir}/man1/intel_*.1*
%{_mandir}/man1/lsgpu.1*

%files devel
%license COPYING
%{_includedir}/i915-perf/*
%{_includedir}/xe-oa/*
%{_libdir}/pkgconfig/i915-perf.pc
%{_libdir}/pkgconfig/xe-oa.pc
%{_libdir}/libi915_perf.so
%{_libdir}/libxe_oa.so

%files docs
%license COPYING
%{_datadir}/gtk-doc/html/igt-gpu-tools/*

%changelog
%autochangelog
