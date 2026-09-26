Name:           zimg
Version:        3.0.6
Release:        %autorelease
Summary:        Scaling, color space conversion, and dithering library
License:        WTFPL
URL:            https://github.com/sekrit-twc/zimg

Source0:        %{url}/archive/release-%{version}/%{name}-%{version}.tar.gz

# Rebased from master on top of 3.0.6, should be removed in the next update
Patch0:         b013c7b006e6bee05b7964162f3a00402168e77f.patch
Patch1:         0e56801f98db3e363c974fca794fa06022d40ee4.patch

BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  gcc-c++
BuildRequires:  libtool
BuildRequires:  make

%description
The "z" library implements the commonly required image processing basics of
scaling, color space conversion, and depth conversion. A simple API enables
conversion between any supported formats to operate with minimal knowledge from
the programmer. All library routines were designed from the ground-up with
correctness, flexibility, and thread-safety as first priorities. Allocation,
buffering, and I/O are cleanly separated from processing, allowing the
programmer to adapt "z" to many scenarios.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1 -n zimg-release-%{version}

%build
autoreconf -vif
%configure \
    --disable-static \
    --enable-testapp
%make_build V=1

%install
%make_install
install -m 755 -p -D testapp %{buildroot}%{_bindir}/testapp

find %{buildroot} -name '*.la' -delete

# Pick up docs in the files section
rm -fr %{buildroot}%{_docdir}/%{name}

%files
%license COPYING
%doc README.md ChangeLog
%{_libdir}/lib%{name}.so.2.0.0
%{_libdir}/lib%{name}.so.2

%check
./testapp cpuinfo

%files devel
%{_bindir}/testapp
%{_includedir}/zimg.h
%{_includedir}/zimg++.hpp
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%changelog
%autochangelog
