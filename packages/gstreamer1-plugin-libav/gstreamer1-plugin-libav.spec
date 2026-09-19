Name:           gstreamer1-plugin-libav
Version:        1.28.6
Release:        1%{?dist}
Summary:        GStreamer FFmpeg/LibAV plugin
License:        LGPLv2+
URL:            https://gstreamer.freedesktop.org/
Source0:        %{url}/src/gst-libav/gst-libav-%{version}.tar.xz

BuildRequires:  gcc-c++
BuildRequires:  meson
BuildRequires:  gstreamer1-devel >= %{version}
BuildRequires:  gstreamer1-plugins-base-devel >= %{version}
BuildRequires:  orc-devel
BuildRequires:  bzip2-devel
BuildRequires:  zlib-devel
BuildRequires:  ffmpeg-free-devel

# Rename from rpmfusion name to match convention in Fedora
Obsoletes:      gstreamer1-libav < 1:1.20.3-4
Provides:       gstreamer1-libav = 1:%{version}-%{release}
Provides:       gstreamer1-libav%{?_isa} = 1:%{version}-%{release}

%description
GStreamer is a streaming media framework, based on graphs of filters which
operate on media data. Applications using this library can do anything
from real-time sound processing to playing videos, and just about anything
else media-related.  Its plugin-based architecture means that new data
types or processing capabilities can be added simply by installing new
plugins.

This package provides FFmpeg/LibAV GStreamer plugin.

%if 0
# gstreamer1 uses hotdoc which isn't provided yet
%package devel-docs
Summary: Development documentation for the libav GStreamer plug-in
Requires: %{name} = %{version}-%{release}
BuildArch: noarch

%description devel-docs
GStreamer is a streaming media framework, based on graphs of elements which
operate on media data.

This package contains the development documentation for the FFmpeg/LibAV GStreamer
plugin.
%endif


%prep
%autosetup -p3 -n gst-libav-%{version}

%build
%meson  \
    -D package-name="Fedora GStreamer-plugin-libav package" \
    -D package-origin="http://download.fedoraproject.org" \
    -D doc=disabled

%meson_build

%install
%meson_install


%files
%doc ChangeLog README.md
%license COPYING
%{_libdir}/gstreamer-1.0/libgstlibav.so

%if 0
%files devel-docs
%doc %{_datadir}/gtk-doc/gst-libav-1.0/
%endif

%changelog
* Wed Aug 05 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.6-1
- 1.28.6

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.28.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Thu Jul 09 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.5-1
- 1.28.5

* Fri Jun 12 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.4-1
- 1.28.4

* Tue May 12 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.3-1
- 1.28.3

* Wed Apr 08 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.2-1
- 1.28.2

* Thu Feb 26 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.1-1
- 1.28.1

* Tue Jan 27 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.0-1
- 1.28.0

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.26.10-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Tue Jan 06 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.26.10-1
- 1.26.10

* Wed Dec 03 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.9-1
- 1.26.9

* Wed Nov 12 2025 Adam Williamson <awilliam@redhat.com> - 1.26.8-2
- rebuilt for ffmpeg 8

* Wed Nov 12 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.8-1
- 1.26.8

* Tue Nov 04 2025 Dominik Mierzejewski <dominik@greysector.net> - 1.26.7-2
- Rebuilt for FFmpeg 8

* Tue Oct 14 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.7-1
- 1.26.7

* Mon Sep 15 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.6-1
- 1.26.6

* Fri Aug 08 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.5-1
- 1.26.5

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.26.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jun 27 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.3-1
- 1.26.3

* Fri May 30 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.2-1
- 1.26.2

* Fri Apr 25 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.1-1
- 1.26.1

* Wed Mar 12 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.0-1
- 1.26.0

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.24.11-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Tue Jan 07 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.24.11-1
- 1.24.11

* Wed Dec 04 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.10-1
- 1.24.10

* Thu Oct 31 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.9-1
- 1.24.9

* Mon Sep 23 2024 Fabio Valentini <decathorpe@gmail.com> - 1.24.8-2
- Rebuild for ffmpeg 7

* Thu Sep 19 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.8-1
- 1.24.8

* Wed Aug 21 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.7-1
- 1.24.7

* Mon Jul 29 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.6-1
- 1.24.6

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.24.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Fri Jun 21 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.5-1
- 1.24.5

* Wed May 29 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.4-1
- 1.24.4

* Tue Apr 30 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.3-1
- 1.24.3

* Tue Mar 05 2024 Wim Taymans <wtaymans@redhat.com> - 1.24.0-1
- Update to 1.24.0

* Thu Jan 25 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.22.9-1
- 1.22.9

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.22.8-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jan 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.22.8-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Mon Dec 18 2023 Gwyn Ciesla <gwync@protonmail.com> - 1.22.8-1
- 1.22.8

* Tue Nov 14 2023 Gwyn Ciesla <gwync@protonmail.com> - 1.22.7-1
- 1.22.7

* Fri Jul 21 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.5-1
- Update to 1.22.5

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.22.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu May 25 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.3-1
- Update to 1.22.3

* Thu Apr 13 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.2-1
- Update to 1.22.2

* Mon Mar 13 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.1-1
- Update to 1.22.1

* Sun Mar 12 2023 Neal Gompa <ngompa@fedoraproject.org> - 1.22.0-2
- Patch and rebuild for ffmpeg 6.0

* Tue Jan 24 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.0-1
- Update to 1.22.0

* Fri Jan 20 2023 Wim Taymans <wtaymans@redhat.com> - 1.21.90-1
- Update to 1.21.90

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Jan 11 2023 Neal Gompa <ngompa@fedoraproject.org> - 1.20.5-1
- Update to 1.20.5

* Mon Nov 21 2022 Neal Gompa <ngompa@fedoraproject.org> - 1.20.4-1
- Update to 1.20.4

* Fri Sep 09 2022 Neal Gompa <ngompa@fedoraproject.org> - 1.20.3-5
- Add arched provides for gstreamer1-libav name

* Thu Sep 08 2022 Neal Gompa <ngompa@fedoraproject.org> - 1.20.3-4
- Rename to gstreamer1-plugin-libav to migrate to Fedora

* Sun Sep 04 2022 Leigh Scott <leigh123linux@gmail.com> - 1:1.20.3-3
- Add requires ffmpeg-libs

* Sun Aug 07 2022 RPM Fusion Release Engineering <sergiomb@rpmfusion.org> - 1:1.20.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild and ffmpeg
  5.1

* Fri Jul 22 2022 Vitaly Zaitsev <vitaly@easycoding.org> - 1:1.20.3-1
- Updated to version 1.20.3.

* Mon Jul 18 2022 Leigh Scott <leigh123linux@gmail.com> - 1:1.20.0-2
- Fix rfbz#6354

* Sun Feb 06 2022 Sérgio Basto <sergio@serjux.com> - 1:1.20.0-1
- Update gstreamer1-libav to 1.20.0

* Mon Nov 15 2021 Sérgio Basto <sergio@serjux.com> - 1:1.19.3-2
- Rebuilt for new ffmpeg snapshot

* Mon Nov 15 2021 Sérgio Basto <sergio@serjux.com> - 1:1.19.3-1
- Update gstreamer1-libav to 1.19.3

* Thu Nov 11 2021 Leigh Scott <leigh123linux@gmail.com> - 1:1.19.2-2
- Rebuilt for new ffmpeg snapshot

* Sat Oct 09 2021 Sérgio Basto <sergio@serjux.com> - 1:1.19.2-1
- Update gstreamer1-libav to 1.19.2

* Mon Aug 02 2021 RPM Fusion Release Engineering <leigh123linux@gmail.com> - 1:1.19.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild
- gstreamer1.prov is broken and hangs, workarround it

* Tue Jun 08 2021 Leigh Scott <leigh123linux@gmail.com> - 1.19.1-1
- Update

* Wed Mar 24 2021 Leigh Scott <leigh123linux@gmail.com> - 1.18.4-2
- Drop patch

* Wed Mar 17 2021 Leigh Scott <leigh123linux@gmail.com> - 1.18.4-1
- 1.18.4

* Sun Feb 28 2021 Leigh Scott <leigh123linux@gmail.com> - 1.18.2-4
- Add patch for ffmpeg-4.4

* Wed Feb 03 2021 RPM Fusion Release Engineering <leigh123linux@gmail.com> - 1.18.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Thu Dec 31 2020 Leigh Scott <leigh123linux@gmail.com> - 1.18.2-2
- Rebuilt for new ffmpeg snapshot

* Sun Dec 13 2020 Leigh Scott <leigh123linux@gmail.com> - 1.18.2-1
- 1.18.2

* Sun Nov  1 2020 Leigh Scott <leigh123linux@gmail.com> - 1.18.1-1
- 1.18.1

* Wed Sep  9 2020 Leigh Scott <leigh123linux@gmail.com> - 1.18.0-1
- 1.18.0

* Sun Aug 23 2020 Leigh Scott <leigh123linux@gmail.com> - 1.17.90-1
- 1.17.90

* Tue Aug 18 2020 RPM Fusion Release Engineering <leigh123linux@gmail.com> - 1.17.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jul 08 2020 Leigh Scott <leigh123linux@gmail.com> - 1.17.2-1
- 1.17.2

* Mon Jun 22 2020 Leigh Scott <leigh123linux@gmail.com> - 1.17.1-1
- 1.17.1

* Thu Mar 12 2020 Leigh Scott <leigh123linux@gmail.com> - 1.16.2-3
- Rebuilt for i686

* Tue Feb 04 2020 RPM Fusion Release Engineering <leigh123linux@gmail.com> - 1.16.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Sat Feb 01 2020 Leigh Scott <leigh123linux@googlemail.com> - 1.16.2-1
- 1.16.2

* Wed Sep 25 2019 Leigh Scott <leigh123linux@googlemail.com> - 1.16.1-1
- 1.16.1

* Wed Aug 07 2019 Leigh Scott <leigh123linux@gmail.com> - 1.16.0-2
- Rebuild for new ffmpeg version

* Wed Apr 24 2019 Leigh Scott <leigh123linux@gmail.com> - 1.16.0-1
- 1.16.0

* Tue Mar 19 2019 Leigh Scott <leigh123linux@googlemail.com> - 1.15.2-1
- 1.15.2

* Mon Mar 04 2019 RPM Fusion Release Engineering <leigh123linux@gmail.com> - 1.15.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Sat Feb 09 2019 Leigh Scott <leigh123linux@googlemail.com> - 1.15.1-1
- 1.15.1

* Tue Oct 09 2018 Rex Dieter <rdieter@fedoraproject.org> - 1.14.4-1
- 1.14.4

* Tue Sep 18 2018 Leigh Scott <leigh123linux@googlemail.com> - 1.14.3-1
- 1.14.3

* Sat Aug 18 2018 Rex Dieter <rdieter@fedoraproject.org> - 1.14.2-1
- 1.14.2

* Thu Jul 26 2018 RPM Fusion Release Engineering <leigh123linux@gmail.com> - 1.14.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Thu May 31 2018 Rex Dieter <rdieter@fedoraproject.org> - 1.14.1-1
- 1.14.1

* Thu Mar 22 2018 Rex Dieter <rdieter@fedoraproject.org> - 1.14.0-1
- Update to 1.14.0

* Sun Mar 04 2018 Leigh Scott <leigh123linux@googlemail.com> - 1.13.1-2
- Use bundled libav for F28 as it doesn't build with ffmpeg git

* Wed Feb 28 2018 Rex Dieter <rdieter@fedoraproject.org> - 1.13.1-1
- 1.13.1

* Fri Jan 19 2018 Leigh Scott <leigh123linux@googlemail.com> - 1.12.4-3
- Use bundled libav for F28

* Thu Jan 18 2018 Leigh Scott <leigh123linux@googlemail.com> - 1.12.4-2
- Rebuilt for ffmpeg-3.5 git

* Mon Dec 11 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.12.4-1
- Update to 1.12.4
- Remove patch for FFMpeg 3.4 APIs (fixed in ffmpeg-3.4.1)

* Sat Nov 18 2017 Simone Caronni <negativo17@gmail.com> - 1.12.3-3
- Temporary patch for FFMpeg 3.4 APIs.

* Mon Oct 16 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.12.3-2
- Rebuild for ffmpeg update

* Wed Sep 20 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.12.3-1
- Update to 1.12.3

* Thu Aug 31 2017 RPM Fusion Release Engineering <kwizart@rpmfusion.org> - 1.12.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Tue Jul 18 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.12.2-1
- Update to 1.12.2

* Fri Jun 23 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.12.1-1
- Update to 1.12.1

* Wed May 17 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.12.0-2
- Rebuilt for f26 ffmpeg bump

* Fri May 12 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.12.0-1
- Update to 1.12.0

* Sat Apr 29 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.11.90-2
- Rebuild for ffmpeg update

* Tue Apr 18 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.11.90-1
- Update to 1.11.90

* Sun Mar 19 2017 RPM Fusion Release Engineering <kwizart@rpmfusion.org> - 1.11.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Mon Feb 27 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.11.2-1
- Update to 1.11.2

* Mon Jan 16 2017 Leigh Scott <leigh123linux@googlemail.com> - 1.11.1-1
- Update to 1.11.1

* Wed Nov 30 2016 leigh scott <leigh123linux@googlemail.com> - 1.10.2-1
- Update to 1.10.2

* Fri Nov 11 2016 Hans de Goede <j.w.r.degoede@gmail.com> - 1.10.0-2
- Drop no longer needed ignore_vaapi.patch

* Fri Nov 11 2016 Hans de Goede <j.w.r.degoede@gmail.com> - 1.10.0-1
- Update to 1.10.0

* Fri Nov 11 2016 Leigh Scott <leigh123linux@googlemail.com> - 1.8.2-4
- Add patch to disable ffmpeg hardware acceleration for nvenc and qsv (rfbz#4334)

* Fri Nov 11 2016 Leigh Scott <leigh123linux@googlemail.com> - 1.8.2-3
- Add patch to ignore VAAPI decoders and VAAPI/nvenc encoders (rfbz#4334)

* Sat Jul 30 2016 Julian Sikorski <belegdol@fedoraproject.org> - 1.8.2-2
- Rebuilt for ffmpeg-3.1.1

* Sun Jun 12 2016 Hans de Goede <j.w.r.degoede@gmail.com> - 1.8.2-1
- Update to 1.8.2

* Wed May 18 2016 Hans de Goede <j.w.r.degoede@gmail.com> - 1.8.1-1
- Update to 1.8.1

* Sat Jan 23 2016 Hans de Goede <j.w.r.degoede@gmail.com> - 1.6.3-1
- Update to 1.6.3

* Thu Dec 24 2015 Hans de Goede <j.w.r.degoede@gmail.com> - 1.6.2-1
- Update to 1.6.2

* Sat Oct 31 2015 Hans de Goede <j.w.r.degoede@gmail.com> - 1.6.1-1
- Update to 1.6.1
- Upstream is using ffmpeg instead of libav now, switch to system ffmpeg-libs

* Sat May 16 2015 Hans de Goede <j.w.r.degoede@gmail.com> - 1.4.5-1
- Update to 1.4.5
- Update libav to 10.6

* Wed Oct  1 2014 Hans de Goede <j.w.r.degoede@gmail.com> - 1.4.3-1
- Update to 1.4.3
- Includes libav 10.5

* Fri Aug 29 2014 Hans de Goede <j.w.r.degoede@gmail.com> - 1.4.1-1
- Update to 1.4.1 (rf#3343)
- Includes libav 10.4

* Sun Jun 15 2014 Hans de Goede <j.w.r.degoede@gmail.com> - 1.2.4-1
- Update to 1.2.4 (rf#3269)
- Update libav to 9.13

* Sat Feb 15 2014 Michael Kuhn <suraia@ikkoku.de> - 1.2.3-1
- Update to 1.2.3.
- Update libav to 9.11.

* Sat Jan 04 2014 Michael Kuhn <suraia@ikkoku.de> - 1.2.2-1
- Update to 1.2.2.

* Sat Nov 16 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.2.1-1
- Rebase to 1.2.1

* Sun Oct 13 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.2.0-1
- Rebase to 1.2.0
- Upgrade the buildin libav to 9.10 to get all the security fixes from
  upstream libav
- Switch back to included libav copy again, libav and ffmpeg have
  deviated to much to use a system ffmpeg lib as libav replacement,
  this fixes a bad memory-leak (rpmfusion#2976)

* Mon Sep 30 2013 Nicolas Chauvet <kwizart@gmail.com> - 1.1.3-4
- Rebuilt

* Tue Aug 27 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.1.3-3
- Rebuild now devel properly points to f20

* Mon Aug 26 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.1.3-2
- Rebuild for ffmpeg-2.0

* Thu Aug  8 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.1.3-1
- Rebase to 1.1.3
- Switch back to using system ffmpeg

* Tue Aug  6 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.0.9-1
- Rebase to 1.0.9
- This includes an upgrade of the buildin libav to 0.8.8 which includes a
  bunch of security fixes from
- No longer overwrite the included libav, as the bundled one is the latest

* Mon Mar 25 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.0.6-1
- Rebase to 1.0.6
- Upgrade the buildin libav to 0.8.6 to get all the security fixes from
  upstream libav

* Sun Mar 10 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.0.5-2
- Add a patch from upstream git to fix h264 decoding artifacts (rf#2710)
- Add a patch from upstream libav to fix miscompilation with gcc-4.8
  (rf#2710, gnome#695166, libav#388)

* Sat Mar  2 2013 Hans de Goede <j.w.r.degoede@gmail.com> - 1.0.5-1
- Rebase to 1.0.5 (rf#2688)
- Upgrade the buildin libav to 0.8.5 to get all the security fixes from
  upstream libav

* Sat Nov  3 2012 Hans de Goede <j.w.r.degoede@gmail.com> - 1.0.2-2
- Build included libav with the default RPM_OPT_FLAGS (rf#2560, rf#2472)

* Sun Oct 28 2012 Hans de Goede <j.w.r.degoede@gmail.com> - 1.0.2-1
- Rebase to 1.0.2
- Included libav copy updated to 0.8.4
- Change the license to LGPLv2+, as the GPL only postproc plugin is no longer
  included
- Replace references to ffmpeg with libav (rf#2472)
- Add COPYING.LIB to %%doc (rf#2472)
- Run make with V=1 (rf#2472)

* Sun Sep 23 2012 Hans de Goede <j.w.r.degoede@gmail.com> - 0.11.99-1
- New upstream release 0.11.99

* Sun Sep  9 2012 Hans de Goede <j.w.r.degoede@gmail.com> - 0.11.93-1
- First version of gstreamer1-libav for rpmfusion
