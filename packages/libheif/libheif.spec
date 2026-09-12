%global somajor 1
# this is used for breaking a self-dependency on build:
# libheif BuildRequires: pkgconfig(sdl2) == sdl2-compat-devel
# sdl2-compat-devel -> sdl2-compat
# sdl2-compat -> SDL3
# SDL3 -> libdecor
# libdecor -> gtk3
# gtk3 -> gtk-update-icon-cache
# gtk-update-icon-cache -> gdk-pixbuf2
# gdk-pixbuf2 -> glycin-libs
# glycin-libs -> glycin-loaders
# glycin-loaders -> libheif
# Bootstrap stays on here, permanently. libheif build-requires sdl2, and
# sdl2 -> SDL3 -> libdecor -> gtk3 -> gdk-pixbuf2 -> glycin-libs ->
# glycin-loaders -> libheif closes a cycle. Fedora never trips it because its
# repository is self-consistent; this accumulator is not, and the moment
# openjph moved 0.25 -> 0.31 the accumulator libheif became uninstallable and
# took its whole buildroot with it. Bootstrap costs exactly one binary, the
# heif-view example; the encoders and every library stay.
%bcond bootstrap 1

# ffmpeg is a stage 0 package, so anything else in stage 0 that links libav
# resolves it from the previous run of the accumulator rather than from this
# one -- and the moment the factory promises ffmpeg, the Fedora libav is
# excluded by name everywhere. libheif is the only stage 0 package that hit
# this: its ffmpegdec plugin wanted libavutil.so.60 from Fedora 8.x while the
# factory ffmpeg 9.x provides a later soname, so the accumulator copy became
# uninstallable and took every buildroot reaching gdk-pixbuf2, glycin,
# graphviz and doxygen with it. The aom and dav1d decoder plugins stay, which
# is what actually decodes AVIF and HEIC here; only the ffmpeg HEVC path goes.
# Narrower than %%bcond bootstrap, which would also drop rav1e, SvtEnc and sdl2.
%bcond ffmpeg 0

# openjph goes too, and this one removes a package rather than a plugin.
# libheif is the only thing in the factory that build-requires openjph, and
# Hummingbird ships no libopenjph at all -- only Fedora does, at 0.25. So
# carrying openjph 0.31 here excluded Fedora libopenjph by name, which made
# Fedora libheif uninstallable, which made this factory own glycin-loaders
# uninstallable, which took gdk-pixbuf2 and sixteen stage 1 packages with it:
#   glycin-loaders-2.2~beta from stages requires libheif.so.1
#   libheif-1.21.2-1.fc44 from fedora requires libopenjph.so.0.25
#   libopenjph-0.25.3-3.fc44 from fedora is filtered out by exclude filtering
# Ordering cannot untie it inside five stages: openjph, libheif, glycin,
# gdk-pixbuf2 and then everything reaching gdk-pixbuf2 is five waves before
# webkitgtk, gjs and gnome-shell have anywhere to go.
# Declining the encoder drops the dependency entirely, so Fedora libopenjph is
# never excluded and nothing downstream has to move. HTJ2K encoding is the
# cost; AVIF and HEIC decode through aom and dav1d, and JPEG 2000 keeps
# working through OpenJPEG, which is a different library.
%bcond openjph 0


Name:           libheif
Version:        1.23.1
Release:        %autorelease
Summary:        HEIF and AVIF file format decoder and encoder

License:        LGPL-3.0-or-later and MIT
URL:            https://github.com/strukturag/libheif
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
Patch0:         libheif-no-hevc-tests.patch
# Fix multilib issues: PLUGIN_DIRECTORY is derived from CMAKE_INSTALL_LIBDIR, the
# macro has exactly one user, get_plugin_paths() in libheif/init.cc, which is internal
# to the library, so pass it as a private compile definition instead of exporting it in
# a public header.
Patch1:         libheif-multilib-plugin-dir.patch

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(aom)
BuildRequires:  pkgconfig(dav1d)
%if !%{with bootstrap} && %{with ffmpeg}
BuildRequires:  pkgconfig(libavcodec)
%endif
BuildRequires:  pkgconfig(libbrotlidec)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(libopenjp2)
BuildRequires:  pkgconfig(libpng)
BuildRequires:  pkgconfig(libtiff-4)
%if %{with openjph}
BuildRequires:  pkgconfig(openjph) >= 0.18.0
%endif
%if !%{with bootstrap}
BuildRequires:  pkgconfig(sdl2)
%endif
BuildRequires:  pkgconfig(zlib)
%ifnarch %{ix86}
# openh264 is not available for i686, see:
# https://bugzilla.redhat.com/show_bug.cgi?id=2393742
BuildRequires:  pkgconfig(openh264)
%endif
%if ! (0%{?rhel} && 0%{?rhel} <= 9)
BuildRequires:  pkgconfig(libsharpyuv)
BuildRequires:  pkgconfig(rav1e)
BuildRequires:  pkgconfig(SvtAv1Enc)
%endif

Obsoletes:      heif-pixbuf-loader < %{version}-%{release}

%description
libheif is an ISO/IEC 23008-12:2017 HEIF and AVIF (AV1 Image File Format)
file format decoder and encoder.

%files
%license COPYING
%doc README.md
%{_libdir}/%{name}.so.%{somajor}{,.*}
%dir %{_libdir}/%{name}
%{_libdir}/%{name}/%{name}-aomdec.so
%{_libdir}/%{name}/%{name}-aomenc.so
%{_libdir}/%{name}/%{name}-dav1d.so
%if !%{with bootstrap} && %{with ffmpeg}
%{_libdir}/%{name}/%{name}-ffmpegdec.so
%endif
%{_libdir}/%{name}/%{name}-j2kdec.so
%{_libdir}/%{name}/%{name}-j2kenc.so
%{_libdir}/%{name}/%{name}-jpegdec.so
%{_libdir}/%{name}/%{name}-jpegenc.so
%if %{with openjph}
%{_libdir}/%{name}/%{name}-jphenc.so
%endif
%ifnarch %{ix86}
%{_libdir}/%{name}/%{name}-openh264dec.so
%endif
%{_libdir}/%{name}/%{name}-rav1e.so
%{_libdir}/%{name}/%{name}-svtenc.so

# ----------------------------------------------------------------------

%package        tools
Summary:        Tools for manipulating HEIF files
License:        MIT
Requires:       %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Requires:       shared-mime-info

%description    tools
This package provides tools for manipulating HEIF files.

%files tools
%{_bindir}/heif-*
%{_mandir}/man1/heif-*
%{_datadir}/thumbnailers/heif.thumbnailer

# ----------------------------------------------------------------------

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%files devel
%{_includedir}/%{name}/
%{_libdir}/cmake/%{name}/
%{_libdir}/pkgconfig/%{name}.pc
%{_libdir}/%{name}.so

# ----------------------------------------------------------------------


%prep
%autosetup -p1
rm -rf third-party/


%build
%cmake \
 -GNinja \
 -DBUILD_SHARED_LIBS=ON \
 -DBUILD_TESTING=ON \
 -DCMAKE_COMPILE_WARNING_AS_ERROR=OFF \
 -DENABLE_PLUGIN_LOADING=ON \
 -DPLUGIN_DIRECTORY=%{_libdir}/%{name} \
 -DWITH_AOM_DECODER=ON \
 -DWITH_AOM_DECODER_PLUGIN=ON \
 -DWITH_AOM_ENCODER=ON \
 -DWITH_AOM_ENCODER_PLUGIN=ON \
 -DWITH_DAV1D=ON \
 -DWITH_DAV1D_PLUGIN=ON \
 -DWITH_EXAMPLES=ON \
%if !%{with bootstrap} && %{with ffmpeg}
 -DWITH_FFMPEG_DECODER=ON \
 -DWITH_FFMPEG_DECODER_PLUGIN=ON \
%endif
 -DWITH_JPEG_DECODER=ON \
 -DWITH_JPEG_DECODER_PLUGIN=ON \
 -DWITH_JPEG_ENCODER=ON \
 -DWITH_JPEG_ENCODER_PLUGIN=ON \
 -DWITH_LIBSHARPYUV=ON \
 -DWITH_OpenJPEG_DECODER=ON \
 -DWITH_OpenJPEG_DECODER_PLUGIN=ON \
 -DWITH_OpenJPEG_ENCODER=ON \
 -DWITH_OpenJPEG_ENCODER_PLUGIN=ON \
%if %{with openjph}
 -DWITH_OPENJPH_DECODER=ON \
 -DWITH_OPENJPH_ENCODER=ON \
 -DWITH_OPENJPH_ENCODER_PLUGIN=ON \
%endif
%ifnarch %{ix86}
 -DWITH_OpenH264_DECODER=ON \
 -DWITH_OpenH264_DECODER_PLUGIN=ON \
 -DWITH_OpenH264_ENCODER=ON \
 -DWITH_OpenJPEG_ENCODER_PLUGIN=ON \
%endif
%if ! (0%{?rhel} && 0%{?rhel} <= 9)
 -DWITH_RAV1E=ON \
 -DWITH_RAV1E_PLUGIN=ON \
 -DWITH_SvtEnc=ON \
 -DWITH_SvtEnc_PLUGIN=ON \
%endif
%if %{with bootstrap}
 -DWITH_EXAMPLE_HEIF_VIEW=OFF \
%endif
 -DWITH_UNCOMPRESSED_CODEC=ON \
 -DWITH_GDK_PIXBUF=OFF \
 -Wno-dev

%cmake_build


%install
%cmake_install


%check
%ctest


%changelog
%autochangelog
