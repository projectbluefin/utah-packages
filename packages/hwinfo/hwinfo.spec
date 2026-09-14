# el6 compatibility
%{!?__global_ldflags: %global __global_ldflags -Wl,-z,relro}

%global make_flags \\\
        LDFLAGS="%{__global_ldflags} -Lsrc" \\\
        LIBDIR=%{_libdir} \\\
        HWINFO_VERSION=%{version}

Name:           hwinfo
Version:        25.5
Release:        %autorelease
Summary:        Hardware information tool

License:        GPL-1.0-or-later
URL:            https://github.com/openSUSE/hwinfo
Source0:        https://github.com/openSUSE/hwinfo/archive/%{version}/%{name}-%{version}.tar.gz

# Fix check_hd being built without LDFLAGS
Patch0:         0000-check_hd-LDFLAGS.patch

BuildRequires:  libx86emu-devel
BuildRequires:  libuuid-devel
BuildRequires:  gcc
BuildRequires:  flex
BuildRequires:  perl-interpreter
BuildRequires:  make
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
Obsoletes:      %{name} < 22.2-1


%description
hwinfo is to probe for the hardware present in the system. It can be used to
generate a system overview log which can be later used for support.


%package libs
Summary:        Libraries for hwinfo
Obsoletes:      %{name} < 22.2-1


%description libs
Libraries for using hwinfo, a hardware information tool, in other applications.


%package devel
Summary:        Development files for hwinfo
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}


%description devel
Header files and libraries for developing with libhd library from hwinfo, a
hardware information tool.


%prep
%autosetup -p1


%build
# Parallel make disabled due to missing libhd.a dependency
make %{make_flags}


%install
%make_install %{make_flags}


%ldconfig_scriptlets libs

%if "%{_sbindir}" == "%{_bindir}"
# Makefile hardcodes sbin paths. Fix the install locations here.
mv %{buildroot}/usr/sbin  %{buildroot}%{_sbindir}
%endif

%files
%{_sbindir}/check_hd
%{_sbindir}/convert_hd
%{_sbindir}/getsysinfo
%{_sbindir}/hwinfo
%{_sbindir}/mk_isdnhwdb
%{_datadir}/hwinfo
%{bash_completions_dir}/hwinfo
%doc *.md MAINTAINER
%license COPYING


%files libs
%license COPYING
%{_libdir}/libhd.so.*


%files devel
%{_includedir}/hd.h
%{_libdir}/pkgconfig/hwinfo.pc
%{_libdir}/libhd.so


%changelog
%autochangelog
