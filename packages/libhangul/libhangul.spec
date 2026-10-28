Name:		libhangul
Version:	0.2.0
Release:	%autorelease

License:	LGPL-2.1-or-later
URL:		https://github.com/libhangul/libhangul
Source0:	https://github.com/libhangul/libhangul/releases/download/libhangul-%{version}/libhangul-%{version}.tar.gz
Patch:  	%{name}-HEAD.patch

Summary:	Hangul input library
BuildRequires:	  gettext-devel, automake, libtool
BuildRequires:	  git
BuildRequires:	  make


%description
libhangul provides common features for Hangul input method programs.


%package devel
Summary:	Development files for libhangul
Requires:	%{name} = %{version}-%{release}
Requires:	pkgconfig
%description devel
This package contains development files necessary to develop programs
providing Hangul input.


%prep
%autosetup -S git

%build
autoreconf -fi
%configure --disable-static

%make_build

%install
%make_install

rm $RPM_BUILD_ROOT%{_libdir}/%{name}.la
%find_lang %{name}


%ldconfig_scriptlets


%files -f %{name}.lang
%doc AUTHORS COPYING ChangeLog NEWS README
%{_libdir}/lib*.so.*
%{_datadir}/%{name}
%{_bindir}/hangul

%files devel
%{_includedir}/hangul-*
%{_libdir}/pkgconfig/*.pc
%{_libdir}/*.so


%changelog
%autochangelog
