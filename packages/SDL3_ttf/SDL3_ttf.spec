Name:       SDL3_ttf
Version:    3.2.2
Release:    %autorelease
Summary:    Support for TrueType (.ttf) font files with Simple Directmedia Layer
License:    Zlib AND MIT
URL:        https://github.com/libsdl-org/SDL_ttf

Source0:    %{url}/releases/download/release-%{version}/%{name}-%{version}.tar.gz
# Backport test binaries install location:
Patch0:     https://github.com/libsdl-org/SDL_ttf/commit/81c273d952b9946a48b99e990c66fb49a76de9b5.patch

BuildRequires:  cmake
BuildRequires:  gcc
BuildRequires:  cmake(SDL3)
BuildRequires:  cmake(zlib)
# For tests:
BuildRequires:  dejavu-sans-fonts
BuildRequires:  dos2unix
BuildRequires:  libGL-devel
BuildRequires:  freetype-devel
BuildRequires:  harfbuzz-devel
BuildRequires:  perl-base
BuildRequires:  plutosvg-devel

%description
This library is a wrapper around the FreeType and Harfbuzz libraries, allowing
you to use TrueType fonts to render text in SDL applications.

%package devel
Summary:    Development files for %{name}
Requires:   %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Requires:   SDL3-devel%{?_isa}

%description devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1

dos2unix CHANGES.txt README.md

%build
%cmake \
    -DSDLTTF_HARFBUZZ:BOOL=ON \
    -DSDLTTF_INSTALL:BOOL=ON \
    -DSDLTTF_INSTALL_CPACK:BOOL=ON \
    -DSDLTTF_INSTALL_MAN:BOOL=ON \
    -DSDLTTF_PLUTOSVG:BOOL=ON \
    -DSDLTTF_RELOCATABLE:BOOL=OFF \
    -DSDLTTF_SAMPLES:BOOL=ON \
    -DSDLTTF_SAMPLES_INSTALL:BOOL=ON \
    -DSDLTTF_STRICT:BOOL=ON \
    -DSDLTTF_VENDORED:BOOL=OFF \
    -DSDLTTF_WERROR:BOOL=OFF

%cmake_build

%install
%cmake_install

%check
# Taken from https://github.com/libsdl-org/SDL_ttf/blob/main/.github/workflows/main.yml#L111-L117:
env -C %{_vpath_builddir}/ SDL_VIDEODRIVER=dummy ./showfont --dump /usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf
file %{_vpath_builddir}/glyph-100.bmp | grep -q "PC bitmap, Windows 3.x format"

%files
%license LICENSE.txt
%doc README.md CHANGES.txt
%{_libdir}/lib%{name}.so.0
%{_libdir}/lib%{name}.so.0.2.2

%files devel
%doc docs/README-migration.md
%{_includedir}/%{name}
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/sdl3-ttf.pc
%{_libdir}/cmake/%{name}
%dir %{_libexecdir}/installed-tests
%{_libexecdir}/installed-tests/%{name}
%{_mandir}/man3/SDL_TTF_*.3*
%{_mandir}/man3/TTF_*.3*

%changelog
%autochangelog
