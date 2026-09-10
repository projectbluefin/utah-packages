Name:           webrtc-audio-processing
Version:        2.1
Release:        %autorelease
Summary:        Library for echo cancellation

License:        BSD-3-Clause
URL:            https://www.freedesktop.org/software/pulseaudio/webrtc-audio-processing/
Source:         https://freedesktop.org/software/pulseaudio/webrtc-audio-processing/%{name}-%{version}.tar.xz

# Backports from upstream
Patch:         0001-Fix-compilation-with-gcc-15.patch
Patch:         0001-arch.h-Add-s390x-support.patch
Patch:         0001-Fix-build-with-abseil-cpp-202508.patch

BuildRequires: meson
BuildRequires: gcc gcc-c++
BuildRequires: abseil-cpp-devel

%description
%{name} is a library derived from Google WebRTC project that
provides echo cancellation functionality. This library is used by for example
PipeWire to provide echo cancellation.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header
files for developing applications that use %{name}.

%prep
%autosetup -p1


%conf
%meson \
%ifnarch %{arm32} %{arm64}
  -Dneon=disabled \
%endif
  %{nil}


%build
%meson_build


%install
%meson_install


%files
%doc NEWS AUTHORS README.md
%license COPYING
%{_libdir}/libwebrtc-audio-processing-2.so.1*

%files devel
%{_libdir}/libwebrtc-audio-processing-2.so
%{_libdir}/pkgconfig/webrtc-audio-processing-2.pc
%{_includedir}/webrtc-audio-processing-2/


%changelog
%autochangelog
