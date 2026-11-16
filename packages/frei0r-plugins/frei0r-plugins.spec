Name:           frei0r-plugins
Version:        3.7.1
Release:        %autorelease
Summary:        Frei0r - a minimalist plugin API for video effects

License:        GPL-2.0-or-later
URL:            https://frei0r.dyne.org/
Source0:        https://github.com/dyne/frei0r/archive/v%{version}/frei0r-plugins-%{version}.tar.gz


Buildrequires:  cmake

BuildRequires:  gcc-c++
BuildRequires:  gavl-devel >= 0.2.3
BuildRequires:  libglvnd-devel
BuildRequires:  opencv-devel >= 1.0.0
BuildRequires:  cairo-devel >= 1.0.0


%description
It is a minimalist plugin API for video sources and filters. The behavior of
the effects can be controlled from the host by simple parameters. The intent is
to solve the recurring re-implementation or adaptation issue of standard effect

%package	opencv
Summary:  Frei0r plugins using OpenCV
Requires:    %{name}%{?_isa} = %{version}-%{release}

%description opencv
Frei0r plugins that use the OpenCV computer vision framework.

%package -n     frei0r-devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description -n frei0r-devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -n frei0r-%{version} -p1


%build
%cmake -DCMAKE_INSTALL_LIBDIR=%{_lib} \

%cmake_build


%install
%cmake_install

#Remove installed doc
rm -rf %{buildroot}%{_docdir}/%{name}


%files
%doc ChangeLog README.md
%license COPYING
%dir %{_libdir}/frei0r-1
%exclude %{_libdir}/frei0r-1/facebl0r.so
%exclude %{_libdir}/frei0r-1/facedetect.so
%{_libdir}/frei0r-1/*.so

%files opencv
%{_libdir}/frei0r-1/facebl0r.so
%{_libdir}/frei0r-1/facedetect.so

%files -n frei0r-devel
%{_includedir}/frei0r.h
%{_includedir}/frei0r.hpp
%dir %{_includedir}/frei0r
%{_includedir}/frei0r/*.h
%{_libdir}/pkgconfig/frei0r.pc

%changelog
%autochangelog
