%bcond_with unwind

#global prerelease -rc1

Name:           libplacebo
Version:        7.387.0
Release:        %autorelease
Summary:        Reusable library for GPU-accelerated video/image rendering primitives

License:        LGPL-2.0-or-later
URL:            https://github.com/haasn/libplacebo
Source0:        %{url}/archive/v%{version}%{?prerelease}/%{name}-%{version}%{?prerelease}.tar.gz

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  meson
BuildRequires:  glad2
BuildRequires:  lcms2-devel
# libdovi (Dolby Vision) is out of scope for #475: its canonical upstream
# code.mpv.org is unreachable from the build environment, so libplacebo is
# built without Dolby Vision support until libdovi is imported.
BuildRequires:  libepoxy-devel
%if %{with unwind}
BuildRequires:  libunwind-devel
%endif
BuildRequires:  libshaderc-devel
BuildRequires:  python3-devel
BuildRequires:  python3-jinja2
BuildRequires:  python3-mako
BuildRequires:  python3-markupsafe
BuildRequires:  spirv-tools-devel
BuildRequires:  vulkan-devel
BuildRequires:  glslang-devel
BuildRequires:  xxhash-devel


%description
libplacebo is essentially the core rendering algorithms and ideas of
mpv turned into a library. This grew out of an interest to accomplish
the following goals:

- Clean up mpv's internal API and make it reusable for other projects.
- Provide a standard library of useful GPU-accelerated image processing
  primitives based on GLSL, so projects like VLC or Firefox can use them
  without incurring a heavy dependency on `libmpv`.
- Rewrite core parts of mpv's GPU-accelerated video renderer on top of
  redesigned abstractions. (Basically, I wanted to eliminate code smell
  like `shader_cache.c` and totally redesign `gpu/video.c`)


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1 -n %{name}-%{version}%{?prerelease}


%build
# libdovi (Dolby Vision) is disabled: its canonical upstream code.mpv.org is
# unreachable from the build environment, so libplacebo builds without Dolby
# Vision support until libdovi is imported (#475).
%meson \
 -Dd3d11=disabled \
 -Ddemos=False \
 -Dlibdovi=disabled \
 %if %{with unwind}
 -Dunwind=enabled
%else
 -Dunwind=disabled
%endif

%meson_build


%install
%meson_install


%files
%license LICENSE
%doc README.md
%{_libdir}/libplacebo.so.387

%files devel
%{_includedir}/libplacebo
%{_libdir}/libplacebo.so
%{_libdir}/pkgconfig/libplacebo.pc


%changelog
%autochangelog
