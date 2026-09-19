Name:           exiv2
Version:        0.28.9
Release:        %autorelease
Summary:        Exif, IPTC and XMP metadata manipulation library

# GPL-2.0-or-later: main library
# BSD-3-Clause: xmpsdk/ 
# LicenseRef-Fedora-Public-Domain:
#  - app/getopt.cpp
#  - src/properties.cpp
#  - src/tzfile.h
#  - xmpsdk/include/MD5.h
#  - xmpsdk/src/MD5.cpp
License:        GPL-2.0-or-later AND BSD-3-Clause AND LicenseRef-Fedora-Public-Domain
URL:            http://www.exiv2.org/
VCS:            https://github.com/Exiv2/exiv2/
%if 0%{?beta:1}
Source:         %{vcs}/archive/v%{version}-%{beta}/%{name}-%{version}-%{beta}.tar.gz
%else
Source:         %{vcs}/archive/v%{version}/%{name}-%{version}.tar.gz
%endif

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  gettext
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(expat)
BuildRequires:  pkgconfig(INIReader)
BuildRequires:  pkgconfig(libbrotlidec)
BuildRequires:  pkgconfig(zlib)
# docs
BuildRequires:  doxygen
BuildRequires:  graphviz
BuildRequires:  libxslt

Requires:       %{name}-libs%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description
A command line utility to access image metadata, allowing one to:
* print the Exif metadata of Jpeg images as summary info, interpreted values,
  or the plain data for each tag
* print the Iptc metadata of Jpeg images
* print the Jpeg comment of Jpeg images
* set, add and delete Exif and Iptc metadata of Jpeg images
* adjust the Exif timestamp (that's how it all started...)
* rename Exif image files according to the Exif timestamp
* extract, insert and delete Exif metadata (including thumbnails),
  Iptc metadata and Jpeg comments


%package      devel
Summary:      Header files, libraries and development documentation for %{name}
Requires:     %{name}-libs%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description  devel
%{summary}.


%package      libs
Summary:      Exif, IPTC and XMP metadata manipulation library
# not strictly required, but convenient and expected
%if 0%{?rhel} && 0%{?rhel} <= 7
Requires:     %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
%else
Recommends:   %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
%endif

%description  libs
A C++ library to access image metadata, supporting full read and write access
to the Exif and Iptc metadata, Exif MakerNote support, extract and delete
methods for Exif thumbnails, classes to access Ifd and so on.


%package      doc
Summary:      API documentation for %{name}
# MIT:
# - clipboard.js
# - cookie.js
# - dynsections.js
# - jquery.js
# - menu.js
# - menudata.js
# - resize.js
# GPL-2.0-only:
# - css and icons from Doxygen
License:      MIT AND GPL-2.0-only
BuildArch:    noarch

%description  doc
%{summary}.

API documentation for %{name}.


%prep
%autosetup -n %{name}-%{version}%{?beta:-%{beta}} -p1


%build
%cmake \
  -DCMAKE_INSTALL_DOCDIR="%{_pkgdocdir}" \
  -DEXIV2_BUILD_DOC:BOOL=ON \
  -DEXIV2_BUILD_SAMPLES:BOOL=OFF \
  -DEXIV2_ENABLE_NLS:BOOL=ON
%cmake_build
%cmake_build --target doc


%install
%cmake_install
%find_lang exiv2 --with-man


%check
export PKG_CONFIG_PATH="%{buildroot}%{_libdir}/pkgconfig${PKG_CONFIG_PATH:+:}${PKG_CONFIG_PATH}"
test "$(pkg-config --modversion exiv2)" = "%{version}"
test "$(pkg-config --variable=libdir exiv2)" = "%{_libdir}"
test -x %{buildroot}%{_libdir}/libexiv2.so


%files -f exiv2.lang
%license COPYING doc/COPYING-XMPSDK
%doc doc/ChangeLog exiv2.md SECURITY.md
%{_bindir}/exiv2
%{_mandir}/man1/exiv2*.1*


%files libs
%{_libdir}/libexiv2.so.28*
%{_libdir}/libexiv2.so.%{version}


%files devel
%{_includedir}/exiv2/
%{_libdir}/cmake/exiv2/
%{_libdir}/libexiv2.so
%{_libdir}/pkgconfig/exiv2.pc


%files doc
%{_pkgdocdir}/


%changelog
%autochangelog
