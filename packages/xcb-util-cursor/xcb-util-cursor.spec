Name:		xcb-util-cursor
Version:	0.1.6
Release:	%autorelease
Summary:	Cursor library on top of libxcb
License:	X11-distribute-modifications-variant
URL:		http://xcb.freedesktop.org
Source0:	http://xcb.freedesktop.org/dist/%{name}-%{version}.tar.xz
BuildRequires:	make
BuildRequires:	gcc
BuildRequires:	pkgconfig(xcb-util) >= 0.3.8
BuildRequires:	pkgconfig(xcb-render)
BuildRequires:	pkgconfig(xcb-renderutil)
BuildRequires:	pkgconfig(xcb-image)
BuildRequires:	m4

%description
XCB util-cursor module provides the following libraries:

  - cursor: port of libxcursor


%package	devel
Summary:	Development and header files for xcb-util-cursos
Requires:	%{name}%{?_isa} = %{version}-%{release}

%description	devel
Development files for xcb-util-cursor.


%prep
%setup -q


%build
%configure --with-pic --disable-static --disable-silent-rules
make %{?_smp_mflags}


%check
make check


%install
make install DESTDIR=%{buildroot} INSTALL="install -p"
rm %{buildroot}%{_libdir}/*.la


%ldconfig_post


%ldconfig_postun


%files
%doc README.md
%license COPYING
%{_libdir}/*.so.*


%files devel
%doc NEWS
%{_libdir}/pkgconfig/*.pc
%{_libdir}/*.so
%{_includedir}/xcb/*.h


%changelog
%autochangelog
