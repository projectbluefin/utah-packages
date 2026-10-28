#global gitrel     140
#global gitcommit  bb40668ff9e47481d4741304f22129097a0d73d7
#global shortcommit %%(c=%%{gitcommit}; echo ${c:0:5})

Name:		gst-editing-services
Version:        1.28.8
Release:        1%{?dist}
Summary:	Gstreamer editing services

License:	GPL-2.0-or-later and LGPL-2.0-or-later
URL:		http://cgit.freedesktop.org/gstreamer/gst-editing-services/		
%if 0%{?gitrel}
# git clone git://anongit.freedesktop.org/gstreamer/gstreamer
# cd gstreamer; git reset --hard %{gitcommit}; ./autogen.sh; make; make distcheck
Source0:        gst-editing-services-%{version}.tar.xz
%else
# autogen.sh was run before tarballing, because it calls git
Source0:	https://gstreamer.freedesktop.org/src/gst-editing-services/gst-editing-services-%{version}.tar.xz
%endif

BuildRequires:  meson >= 0.48.0
BuildRequires:  gcc
BuildRequires:	gstreamer1-devel >= 1.6.0
BuildRequires:	gstreamer1-plugins-base-devel >= 1.6.0
BuildRequires:	gstreamer1-plugins-bad-free-devel >= 1.6.0
BuildRequires:	gobject-introspection-devel
BuildRequires:	flex
BuildRequires:	pkgconfig(bash-completion)
BuildRequires:  python3-devel
BuildRequires:  python3-gobject-devel

%description 
This is a high-level library for facilitating the creation of audio/video
non-linear editors.

%package devel
Summary: Development files for gst-editing-services
License:	GPL-2.0-or-later and LGPL-2.0-or-later
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
This package contains libraries and header files for
developing applications that use %{name}

%prep
%autosetup -p3 -n gst-editing-services-%{version}

%build
%meson \
	-D validate=disabled \
	-D doc=disabled \
        -D tests=disabled

%meson_build

find . -name '.gitignore' | xargs rm -f


%install
%meson_install

mkdir -p %{buildroot}%{_datadir}/bash-completion/completions/
cp data/completions/ges-launch-1.0 \
        %{buildroot}%{_datadir}/bash-completion/completions/ges-launch-1.0

%ldconfig_scriptlets

%files
%doc ChangeLog README
%license AUTHORS COPYING*
%{_bindir}/ges-launch-1.0
%{_libdir}/*.so.*
%{_libdir}/girepository-1.0/GES-1.0.typelib
%{_datadir}/bash-completion/completions/ges-launch-1.0
%doc %{_mandir}/man1/ges-launch-1.0.*
#%%{_libdir}/gst-validate-launcher/
%{python3_sitearch}/gi/overrides/*
#%%{_datadir}/gstreamer-1.0/validate/scenarios/ges-edit-clip-while-paused.scenario
#%%dir %%{_datadir}/gstreamer-1.0/validate/
#%%dir %%{_datadir}/gstreamer-1.0/validate/scenarios/

# plugins 
%{_libdir}/gstreamer-1.0/*.so

%files devel
%doc docs/
%{_libdir}/*.so
%{_includedir}/gstreamer-1.0/ges/
%{_libdir}/pkgconfig/gst-editing-services-1.0.pc
%{_datadir}/gir-1.0/GES-1.0.gir

%changelog
* Thu Oct 08 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.8-1
- 1.28.8

* Thu Sep 10 2026 Zbigniew Jędrzejewski-Szmek <zbyszek@in.waw.pl> - 1.28.7-2
- Rebuilt for libxml-2.5.4

* Tue Sep 08 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.7-1
- 1.28.7

* Wed Aug 05 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.6-1
- 1.28.6

* Wed Jul 22 2026 Python Maint <python-maint@redhat.com> - 1.28.5-3
- Rebuilt for Python 3.15.0b4 ABI change

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.28.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Thu Jul 09 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.5-1
- 1.28.5

* Fri Jun 12 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.4-1
- 1.28.4

* Wed Jun 03 2026 Python Maint <python-maint@redhat.com> - 1.28.3-2
- Rebuilt for Python 3.15

* Tue May 12 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.3-1
- 1.28.3

* Wed Apr 08 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.2-1
- 1.28.2

* Thu Feb 26 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.1-1
- 1.28.1

* Wed Jan 28 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.28.0-1
- 1.28.0

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.26.10-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Tue Jan 06 2026 Gwyn Ciesla <gwync@protonmail.com> - 1.26.10-1
- 1.26.10

* Wed Dec 03 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.9-1
- 1.26.9

* Wed Nov 12 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.8-1
- 1.26.8

* Tue Oct 14 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.7-1
- 1.26.7

* Fri Sep 19 2025 Python Maint <python-maint@redhat.com> - 1.26.6-2
- Rebuilt for Python 3.14.0rc3 bytecode

* Mon Sep 15 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.6-1
- 1.26.6

* Fri Aug 15 2025 Python Maint <python-maint@redhat.com> - 1.26.5-2
- Rebuilt for Python 3.14.0rc2 bytecode

* Fri Aug 08 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.5-1
- 1.26.5

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.26.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jun 27 2025 Gwyn Ciesla <gwync@protonmail.com> - 1.26.3-1
- 1.26.3

* Tue Jun 03 2025 Python Maint <python-maint@redhat.com> - 1.26.2-2
- Rebuilt for Python 3.14

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

* Fri Jun 07 2024 Python Maint <python-maint@redhat.com> - 1.24.4-3
- Rebuilt for Python 3.13

* Fri May 31 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.4-2
- Fix directory ownership.

* Wed May 29 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.4-1
- 1.24.4

* Tue May 28 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.3-1
- 1.24.3

* Mon Apr 15 2024 Gwyn Ciesla <gwync@protonmail.com> - 1.24.0-2
- Update python3-gobject BuildRequires

* Tue Mar 05 2024 Wim Taymans <wtaymans@redhat.com> - 1.24.0-1
- Update to 1.24.0

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.22.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jan 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.22.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jul 21 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.5-1
- Update to 1.22.5

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.22.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jun 15 2023 Python Maint <python-maint@redhat.com> - 1.22.3-2
- Rebuilt for Python 3.12

* Thu May 25 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.3-1
- Update to 1.22.3

* Thu Apr 13 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.2-1
- Update to 1.22.2

* Mon Mar 13 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.1-1
- Update to 1.22.1

* Fri Mar 03 2023 Gwyn Ciesla <gwync@protonmail.com> - 1.22.0-2
- migrated to SPDX license

* Tue Jan 24 2023 Wim Taymans <wtaymans@redhat.com> - 1.22.0-1
- Update to 1.22.0

* Fri Jan 20 2023 Wim Taymans <wtaymans@redhat.com> - 1.21.90-1
- Update to 1.21.90

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Jan 11 2023 Wim Taymans <wtaymans@redhat.com> - 1.20.5-1
- Update to 1.20.5

* Thu Oct 13 2022 Wim Taymans <wtaymans@redhat.com> - 1.20.4-1
- Update to 1.20.4

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Mon Jul 18 2022 Wim Taymans <wtaymans@redhat.com> - 1.20.3-1
- Update to 1.20.3

* Mon Jun 13 2022 Python Maint <python-maint@redhat.com> - 1.20.0-2
- Rebuilt for Python 3.11

* Fri Feb 4 2022 Wim Taymans <wtaymans@redhat.com> - 1.20.0-1
- Update to 1.20.0
- remove old patch

* Mon Jan 24 2022 David King <amigadave@amigadave.com> - 1.19.3-3}
- Fix missing ges-image-source.h header (#2036385)

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.19.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Nov 11 2021 Wim Taymans <wtaymans@redhat.com> - 1.19.3-1
- Update to 1.19.3

* Thu Sep 23 2021 Wim Taymans <wtaymans@redhat.com> - 1.19.2-1
- Update to 1.19.2

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.19.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Fri Jun 04 2021 Python Maint <python-maint@redhat.com> - 1.19.1-2
- Rebuilt for Python 3.10

* Thu Jun 03 2021 Wim Taymans <wtaymans@redhat.com> - 1.19.1-1
- Update to 1.19.1

* Tue Mar 16 2021 Wim Taymans <wtaymans@redhat.com> - 1.18.4-1
- Update to 1.18.4

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.18.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Thu Dec 10 2020 Wim Taymans <wtaymans@redhat.com> - 1.18.2-1
- Update to 1.18.2

* Wed Nov 11 2020 Gwyn Ciesla <gwync@protonmail.com> - 1.18.1-2
- Fix for Python 3.10

* Fri Oct 30 2020 Wim Taymans <wtaymans@redhat.com> - 1.18.1-1
- Update to 1.18.1

* Tue Sep 8 2020 Wim Taymans <wtaymans@redhat.com> - 1.18.0-1
- Update to 1.18.0

* Fri Aug 21 2020 Wim Taymans <wtaymans@redhat.com> - 1.17.90-1
- Update to 1.17.90

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.17.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Mon Jul 6 2020 Wim Taymans <wtaymans@redhat.com> - 1.17.2-1
- Update to 1.17.2

* Mon Jun 22 2020 Wim Taymans <wtaymans@redhat.com> - 1.17.1-1
- Update to 1.17.1

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.16.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jan 2 2020 Wim Taymans <wtaymans@redhat.com> - 1.16.2-1
- Update to 1.16.2

* Tue Sep 24 2019 Wim Taymans <wtaymans@redhat.com> - 1.16.1-1
- Update to 1.16.1

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.16.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Tue Apr 23 2019 Wim Taymans <wtaymans@redhat.com> - 1.16.0-1
- Update to 1.16.0

* Fri Mar 01 2019 Wim Taymans <wtaymans@redhat.com> - 1.15.2-1
- Update to 1.15.2

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.15.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jan 25 2019 Wim Taymans <wtaymans@redhat.com> - 1.15.1-1
- Update to 1.15.1

* Wed Oct 03 2018 Wim Taymans <wim.taymans@gmail.com> - 1.14.4-1
- update to 1.14.4

* Tue Sep 18 2018 Wim Taymans <wim.taymans@gmail.com> - 1.14.3-1
- update to 1.14.3

* Mon Jul 23 2018 Wim Taymans <wim.taymans@gmail.com> - 1.14.2-1
- update to 1.14.2

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.14.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Mon May 21 2018 Wim Taymans <wim.taymans@gmail.com> - 1.14.1-1
- update to 1.14.1

* Tue Mar 20 2018 Wim Taymans <wim.taymans@gmail.com> - 1.14.0-1
- update to 1.14.0

* Wed Mar 14 2018 Wim Taymans <wim.taymans@gmail.com> - 1.13.91-1
- update to 1.13.91

* Mon Mar 05 2018 Wim Taymans <wim.taymans@gmail.com> - 1.13.90-1
- update to 1.13.90

* Thu Feb 22 2018 Wim Taymans <wim.taymans@gmail.com> - 1.13.1-1
- update to 1.13.1

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.12.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Mon Dec 11 2017 Wim Taymans <wim.taymans@gmail.com> - 1.12.4-1
- update to 1.12.4

* Tue Sep 19 2017 Wim Taymans <wim.taymans@gmail.com> - 1.12.3-1
- update to 1.12.3

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.12.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.12.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Mon Jul 17 2017 Wim Taymans <wim.taymans@gmail.com> - 1.12.2-1
- update to 1.12.2

* Tue Jun 20 2017 Wim Taymans <wim.taymans@gmail.com> - 1.12.1-1
- update to 1.12.1

* Wed May 10 2017 Wim Taymans <wim.taymans@gmail.com> - 1.12.0-1
- update to 1.12.0

* Fri Apr 28 2017 Wim Taymans <wim.taymans@gmail.com> - 1.11.91-1
- update to 1.11.91

* Tue Apr 11 2017 Wim Taymans <wim.taymans@gmail.com> - 1.11.90-1
- update to 1.11.90

* Fri Feb 24 2017 Wim Taymans <wim.taymans@gmail.com> - 1.11.2-1
- update to 1.11.2

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.11.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Fri Jan 13 2017 Wim Taymans <wim.taymans@gmail.com> - 1.11.1-1
- update to 1.11.1
- Add man page

* Mon Dec 05 2016 Wim Taymans <wim.taymans@gmail.com> - 1.10.2-1
- update to 1.10.2

* Mon Nov 28 2016 Wim Taymans <wim.taymans@gmail.com> - 1.10.1-1
- update to 1.10.1

* Thu Nov 03 2016 Wim Taymans <wim.taymans@gmail.com> - 1.10.0-1
- update to 1.10.0

* Sat Oct 01 2016 Wim Taymans <wim.taymans@gmail.com> - 1.9.90-1
- update to 1.9.90

* Thu Sep 01 2016 Wim Taymans <wim.taymans@gmail.com> - 1.9.2-1
- update to 1.9.2

* Thu Jul 07 2016 Wim Taymans <wim.taymans@gmail.com> - 1.9.1-1
- update to 1.9.1

* Thu Jun 09 2016 Wim Taymans <wim.taymans@gmail.com> - 1.8.2-1
- update to 1.8.2

* Thu Apr 21 2016 Wim Taymans <wim.taymans@gmail.com> - 1.8.1-1
- update to 1.8.1

* Wed Apr 06 2016 Jon Ciesla <limburgher@gmail.com> - 1.8.0-2
- Drop python-gstreamer1 Requires, BZ 1215054.

* Thu Mar 24 2016 Wim Taymans <wim.taymans@gmail.com> - 1.8.0-1
- update to 1.8.0

* Wed Mar 16 2016 Wim Taymans <wim.taymans@gmail.com> - 1.7.91-1
- update to 1.7.91

* Thu Mar 03 2016 Wim Taymans <wim.taymans@gmail.com> - 1.7.90-1
- update to 1.7.90

* Wed Feb 24 2016 Wim Taymans <wim.taymans@gmail.com> - 1.7.2-1
- update to 1.7.2

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Fri Jan 8 2016 Wim Taymans <wim.taymans@gmail.com> - 1.7.1-1
- update to 1.7.1

* Tue Dec 15 2015 Wim Taymans <wim.taymans@gmail.com> - 1.6.2-1
- update to 1.6.2

* Mon Nov 23 2015 Wim Taymans <wim.taymans@gmail.com> - 1.6.1-1
- update to 1.6.1

* Mon Nov 23 2015 Wim Taymans <wim.taymans@gmail.com> - 1.6.0-1
- update to 1.6.0
- Add GStreamer nle plugins
- build with right version

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Tue Nov 04 2014 Jon Ciesla <limburgher@gmail.com> - 1.4.0-1
- 1.4.0, BZ 1159986.

* Sat Aug 16 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.2.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Tue Jul 22 2014 Kalev Lember <kalevlember@gmail.com> - 1.2.1-3
- Rebuilt for gobject-introspection 1.41.4

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.2.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Thu May 01 2014 Jon Ciesla <limburgher@gmail.com> - 1.2.1-1
- 1.2.1, BZ 1093138.

* Thu Jan 23 2014 Jon Ciesla <limburgher@gmail.com> - 1.2.0-1
- 1.2.0, BZ 1077939.

* Thu Jan 23 2014 Jon Ciesla <limburgher@gmail.com> - 1.1.90-5.20140123git105d901
- More recent snapshot.

* Thu Jan 16 2014 Jon Ciesla <limburgher@gmail.com> - 1.1.90-4.20131206git289b04f
- Added dep on python-gstreamer1.
- Moved .dir to -devel.

* Fri Dec 06 2013 Jon Ciesla <limburgher@gmail.com> - 1.1.90-3.20131206git289b04f
- Added BuildRequires for gobject-introspection, gtk-doc
- Added ownershipo of GES files.

* Tue Oct 29 2013 Jon Ciesla <limburgher@gmail.com> - 1.1.90-2.20131015git71a6d75
- Multiple review fixes, BZ 1019403 comment 1.

* Tue Oct 15 2013 Jon Ciesla <limburgher@gmail.com> - 1.1.90-1.20131015git71a6d75
- Initial package creation.
