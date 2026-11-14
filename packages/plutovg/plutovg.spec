Name:           plutovg
Version:        1.3.3
Release:        %autorelease
Summary:        Tiny 2D vector graphics library in C
License:        MIT AND FTL
URL:            https://github.com/sammycage/plutovg

Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
Patch0:         %{name}-system-stb.patch
Patch1:         %{name}-soversion-cmake.patch

BuildRequires:  cmake
BuildRequires:  gcc
BuildRequires:  stb_image-devel
BuildRequires:  stb_image_write-devel
BuildRequires:  stb_truetype-devel

%description
PlutoVG is a standalone 2D vector graphics library in C.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package        samples
Summary:        Sample programs for %{name}

%description    samples
Sample programs that use %{name}.

%prep
%autosetup -p1
# Remove bundled stb:
rm -fv source/%{name}-stb-*.h

%build
%cmake \
    -DCMAKE_SKIP_RPATH=ON \
    -DPLUTOVG_BUILD_EXAMPLES=ON
%cmake_build

%install
%cmake_install
install -p -m 0755 -D %{_vpath_builddir}/examples/smiley %{buildroot}%{_bindir}/smiley

%check
%ctest
# At the moment there are no meson tests defined and the above command is a no-op,
# so run the sample program as a test:
export LD_LIBRARY_PATH=%{_vpath_builddir}
%{_vpath_builddir}/examples/smiley

%files
%license LICENSE source/FTL.TXT
%doc README.md
%{_libdir}/lib%{name}.so.1
%{_libdir}/lib%{name}.so.%{version}

%files devel
%{_libdir}/cmake/%{name}
%{_includedir}/%{name}
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%files samples
%{_bindir}/smiley

%changelog
%autochangelog
