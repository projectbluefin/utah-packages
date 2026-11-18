%global		pkg	mozc
%undefine	_hardened_build

%bcond_without	zinnia
%bcond_without	qt

Name:		mozc
Version:	2.29.5111.102
Release:	22%{?dist}
Summary:	A Japanese Input Method Editor (IME) designed for multi-platform

License:	BSD-3-Clause AND Apache-2.0 AND Unicode-DFS-2015 AND NAIST-2003
URL:		https://github.com/google/mozc
# data/unicode/: UCD
#  Copyright (c) 1991-2008 Unicode, Inc.
# data/test/stress_test/sentences.txt: Public Domain
#   See https://gitlab.com/fedora/legal/fedora-license-data/-/issues/178#note_1331790847
# data/dictionary_oss/: mecab-ipadic and BSD
#   See http://code.google.com/p/mozc/issues/detail?id=20
#   also data/installer/credits_en.html

##Source0:	http://mozc.googlecode.com/files/mozc-%%{version}.tar.bz2
# No upstream releases downloadable from the download services due to:
#   http://google-opensource.blogspot.jp/2013/05/a-change-to-google-code-download-service.html
#
# How to checkout the tree from the repository:
#   https://github.com/google/mozc/blob/master/docs/build_mozc_in_docker.md
#
# How to make a tarball after updating:
#   (cd src;
#    python build_mozc.py gyp --target_platform=Linux
#   )
#   major=$(grep MAJOR src/mozc_version.txt|sed -e 's/MAJOR=//g')
#   minor=$(grep MINOR src/mozc_version.txt|sed -e 's/MINOR=//g')
#   build=$(grep BUILD src/mozc_version.txt|sed -e 's/BUILD=//g')
#   rev=$(grep REVISION src/mozc_version.txt|sed -e 's/REVISION=//g')
#   version="$major.$minor.$build.$rev"
#   (cd src;
#    for f in $(find -type f -regex '.*.[ch]' -o -regex '.*.html' -o -regex '.*README*'); do chmod a-x $f; done
#    tar -a --exclude-vcs --exclude third_party/gyp* -cf ../mozc-$version.tar.bz2 *
#   )
#
Source0:	%{name}-%{version}.tar.xz
Source1:	mozc-init.el
# Public Domain
## https://gitlab.com/fedora/legal/fedora-license-data/-/issues/181#note_1339185494
Source2:	http://www.post.japanpost.jp/zipcode/dl/kogaki/zip/ken_all.zip
Source3:	http://www.post.japanpost.jp/zipcode/dl/jigyosyo/zip/jigyosyo.zip
Source4:	ibus-setup-mozc-jp.desktop
Source5:	ibus-mozc-launch-xwayland.desktop
Source6:	ibus-mozc-launch-xwayland.sh
Patch0:		mozc-build-ninja.patch
## to avoid undefined symbols with clang.
Patch1:		mozc-build-gcc.patch
Patch2:		mozc-build-verbosely.patch
Patch3:		mozc-build-id.patch
Patch4:		mozc-build-gcc-common.patch
Patch5:		mozc-use-system-abseil-cpp.patch
Patch6:		mozc-build-gyp.patch
Patch7:		mozc-build-new-abseil.patch
# Add #include directives for compatibility with abseil-cpp-20240116.
# Downstream-only because these are fixed upstream in a later release.
Patch8:         mozc-abseil-cpp-20240116-includes.patch
Patch9:		mozc-fix-2257171.patch

BuildRequires:	python gettext
BuildRequires:	libstdc++-devel zlib-devel libxcb-devel glib2-devel gtk2-devel
BuildRequires:  protobuf-devel < 4
# protobuf3-c exists only from Fedora 45 on, where the base protobuf is 33.x
# and a protobuf-3 compat build of the C bindings is needed alongside it.
# Fedora 44 -- the release Hummingbird pairs with -- already ships protobuf
# 3.19.6, so its plain protobuf-c is that same protobuf-3 build under the
# original name, and protobuf3-c is absent entirely.
%if 0%{?fedora} >= 45
BuildRequires:  protobuf3-c
%else
BuildRequires:  protobuf-c
%endif
BuildRequires:	abseil-cpp-devel
%if %{with qt}
BuildRequires:	qt5-qtbase-devel
%endif
%if %{with zinnia}
BuildRequires:	zinnia-devel
%endif
BuildRequires:	clang ninja-build
BuildRequires:	gyp >= 0.1-0.4.840svn
BuildRequires:	ibus-devel >= 1.5.4
BuildRequires:	emacs
%if 0%{?fedora} < 36
BuildRequires:	xemacs xemacs-packages-extra
%endif
BuildRequires:  desktop-file-utils
BuildRequires:	libappstream-glib
BuildRequires:  %{py3_dist six}
BuildRequires:  binutils
# https://bugzilla.redhat.com/show_bug.cgi?id=1419949
ExcludeArch:	ppc ppc64 sparcv9 sparc64 s390x

%if %{with zinnia}
Recommends:	zinnia-tomoe-ja
%endif
Requires:	emacs-filesystem >= %{_emacs_version}
%if 0%{?fedora} < 36
Requires:	xemacs-filesystem >= %{_xemacs_version}
%endif
Provides:	emacs-mozc <= 2.17.2077.102-4, emacs-mozc-el <= 2.17.2077.102-4
Obsoletes:	emacs-mozc <= 2.17.2077.102-4, emacs-mozc-el <= 2.17.2077.102-4
Provides:	xemacs-mozc <= 2.17.2077.102-4, xemacs-mozc-el <= 2.17.2077.102-4
Obsoletes:	xemacs-mozc <= 2.17.2077.102-4, xemacs-mozc-el <= 2.17.2077.102-4
Provides:	emacs-common-mozc <= 2.17.2077.102-4
Obsoletes:	emacs-common-mozc <= 2.17.2077.102-4

%description
Mozc is a Japanese Input Method Editor (IME) designed for
multi-platform such as Chromium OS, Windows, Mac and Linux.

%package	-n ibus-mozc
Summary:	The mozc engine for IBus input platform
Requires:	%{name}%{?_isa} = %{version}-%{release}
Requires:	ibus%{?_isa} >= 1.5.4
Requires:	xrefresh

%description	-n ibus-mozc
Mozc is a Japanese Input Method Editor (IME) designed for
multi-platform such as Chromium OS, Windows, Mac and Linux.

This package contains the Input Method Engine for IBus.


%prep
%setup -q -c -n %{name}-%{version} -a 2 -a 3
%autopatch -p1
(cd data/dictionary_oss;
PYTHONPATH="${PYTHONPATH}:../.." python ../../dictionary/gen_zip_code_seed.py --zip_code=../../KEN_ALL.CSV --jigyosyo=../../JIGYOSYO.CSV >> dictionary09.txt;
)
rm -rf third_party/abseil-cpp


%build
# replace compiler flags to build with the proper debugging information
t=`mktemp /tmp/mozc.gyp-XXXXXXXX`
opts=$(for i in $(echo $RPM_OPT_FLAGS); do #|sed -e 's/-fstack-clash-protection//g' -e 's/-fcf-protection//g'); do
	echo "i \\"
	echo "\"$i\","
done)
sed -ne "/'linux_cflags':/{p;n;p;:a;/[[:space:]]*\],/{\
$opts
p;b b};n;b a;};{p};:b" gyp/common.gypi > $t && mv $t gyp/common.gypi || exit 1
GYP_DEFINES="use_libprotobuf=1 use_system_abseil_cpp=1 %{?with_zinnia:use_libzinnia=1 zinnia_model_file=/usr/share/zinnia/model/tomoe/handwriting-ja.model} %{!?with_zinnia:use_libzinnia=0} ibus_mozc_path=%{_libexecdir}/ibus-engine-mozc ibus_mozc_icon_path=%{_datadir}/ibus-mozc/product_icon.png" python build_mozc.py gyp --gypdir=%{_bindir} --server_dir=%{_libexecdir}/mozc --target_platform=Linux %{!?with_qt:--noqt}
python build_mozc.py build -c Release unix/ibus/ibus.gyp:ibus_mozc unix/emacs/emacs.gyp:mozc_emacs_helper server/server.gyp:mozc_server gui/gui.gyp:mozc_tool renderer/renderer.gyp:mozc_renderer


%install
install -d $RPM_BUILD_ROOT%{_libexecdir}/mozc
install -d $RPM_BUILD_ROOT%{_libexecdir}/mozc/documents
install -d $RPM_BUILD_ROOT%{_bindir}
install -d $RPM_BUILD_ROOT%{_datadir}/ibus/component
install -d $RPM_BUILD_ROOT%{_datadir}/ibus-mozc
install -d $RPM_BUILD_ROOT%{_emacs_sitelispdir}/%{pkg}
install -d $RPM_BUILD_ROOT%{_emacs_sitestartdir}

install -p -m0755 out_linux/Release/mozc_server $RPM_BUILD_ROOT%{_libexecdir}/mozc
install -p -m0755 out_linux/Release/mozc_tool $RPM_BUILD_ROOT%{_libexecdir}/mozc
install -p -m0755 out_linux/Release/mozc_renderer $RPM_BUILD_ROOT%{_libexecdir}/mozc
install -p -m0644 data/installer/credits_en.html $RPM_BUILD_ROOT%{_libexecdir}/mozc/documents

# ibus-mozc
install -p -m0755 %{SOURCE6} $RPM_BUILD_ROOT%{_libexecdir}/mozc
install -p -m0755 out_linux/Release/ibus_mozc $RPM_BUILD_ROOT%{_libexecdir}/ibus-engine-mozc
install -p -m0644 out_linux/Release/gen/unix/ibus/mozc.xml $RPM_BUILD_ROOT%{_datadir}/ibus/component/
(cd data/images/unix;
install -p -m0644 ime_product_icon_opensource-32.png $RPM_BUILD_ROOT%{_datadir}/ibus-mozc/product_icon.png
for i in ui-*.png; do
	install -p -m0644 $i $RPM_BUILD_ROOT%{_datadir}/ibus-mozc/${i//ui-/}
done)
desktop-file-install --dir=${RPM_BUILD_ROOT}%{_datadir}/applications %{SOURCE4}
desktop-file-install --dir=${RPM_BUILD_ROOT}%{_sysconfdir}/xdg/autostart %{SOURCE5}

# emacs-common-mozc
install -p -m0755 out_linux/Release/mozc_emacs_helper $RPM_BUILD_ROOT%{_bindir}

# emacs-mozc*
install -p -m0644 unix/emacs/mozc.el $RPM_BUILD_ROOT%{_emacs_sitelispdir}/%{pkg}
install -p -m0644 %{SOURCE1} $RPM_BUILD_ROOT%{_emacs_sitestartdir}

emacs -batch -f batch-byte-compile $RPM_BUILD_ROOT%{_emacs_sitelispdir}/%{pkg}/mozc.el

%if 0%{?fedora} < 36
# xemacs-mozc*
install -d $RPM_BUILD_ROOT%{_xemacs_sitelispdir}/%{pkg}
install -d $RPM_BUILD_ROOT%{_xemacs_sitestartdir}
install -p -m0644 unix/emacs/mozc.el $RPM_BUILD_ROOT%{_xemacs_sitelispdir}/%{pkg}
install -p -m0644 %{SOURCE1} $RPM_BUILD_ROOT%{_xemacs_sitestartdir}

xemacs -batch -f batch-byte-compile $RPM_BUILD_ROOT%{_xemacs_sitelispdir}/%{pkg}/mozc.el
%endif

# Register as an AppStream component to be visible in the software center
#
# NOTE: It would be *awesome* if this file was maintained by the upstream
# project, translated and installed into the right place during `make install`.
#
# See http://www.freedesktop.org/software/appstream/docs/ for more details.
#
install -d -m 0755 %{buildroot}%{_metainfodir}
cat > %{buildroot}%{_metainfodir}/mozc.appdata.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="inputmethod">
  <id>mozc.xml</id>
  <metadata_license>CC0-1.0</metadata_license>
  <name>Mozc</name>
  <summary>Japanese input method</summary>
  <description>
    <p>
      The Mozc input method is designed for entering Japanese text.
      It is multi-platform and is available on Chromium OS, Windows, Mac and Linux.
    </p>
    <p>
      Input methods are typing systems allowing users to input complex languages.
      They are necessary because these contain too many characters to simply be laid
      out on a traditional keyboard.
    </p>
  </description>
  <url type="homepage">https://github.com/google/mozc</url>
  <url type="bugtracker">https://github.com/google/mozc/issues</url>
  <url type="help"><!-- https://code.google.com/p/ibus/wiki/FAQ --></url>
  <languages>
    <lang percentage="100">ja</lang>
  </languages>
  <update_contact><!-- upstream-contact_at_email.com --></update_contact>
</component>
EOF

%check
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/*.appdata.xml

%files
%dir %{_libexecdir}/mozc
%{_bindir}/mozc_emacs_helper
%{_libexecdir}/mozc/mozc_server
%{_libexecdir}/mozc/mozc_tool
%{_libexecdir}/mozc/documents
%dir %{_emacs_sitelispdir}/%{pkg}
%{_emacs_sitelispdir}/%{pkg}/*.elc
%{_emacs_sitestartdir}/*.el
%{_emacs_sitelispdir}/%{pkg}/*.el
%if 0%{?fedora} < 36
%dir %{_xemacs_sitelispdir}/%{pkg}
%{_xemacs_sitelispdir}/%{pkg}/*.elc
%{_xemacs_sitestartdir}/*.el
%{_xemacs_sitelispdir}/%{pkg}/*.el
%endif

%files	-n ibus-mozc
%dir %{_datadir}/ibus-mozc
%{_libexecdir}/mozc/ibus-mozc-launch-xwayland.sh
%{_libexecdir}/ibus-engine-mozc
%{_libexecdir}/mozc/mozc_renderer
%{_metainfodir}/*.appdata.xml
%{_datadir}/applications/ibus-setup-mozc-jp.desktop
%{_datadir}/ibus/component/mozc.xml
%{_datadir}/ibus-mozc/*.png
%{_sysconfdir}/xdg/autostart/ibus-mozc-launch-xwayland.desktop


%changelog
* Fri Sep 25 2026 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-22
- Adjust abseil-cpp unbundling patch for abseil-cpp 20260817.0
- Rebuilt for abseil-cpp 20260817.0

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.29.5111.102-21
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Wed Jun 24 2026 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-20
- Rebuilt for abseil-cpp 20260526.0

* Thu May 21 2026 Miroslav Suchy <msuchy@redhat.com> - 2.29.5111.102-19
- Use protobuf2 because of https://fedoraproject.org/wiki/Changes/Protobuf_5.x/6.x

* Wed Jan 28 2026 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-18
- Rebuilt for abseil-cpp 20260107.0

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.29.5111.102-17
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Sep 10 2025 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-16
- Rebuilt for abseil-cpp 20250814.0

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.29.5111.102-15
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Tue May 27 2025 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-14
- Adapt use-system-abseil-cpp patch for abseil-cpp 20250512
- Rebuilt for abseil-cpp-20250512.0

* Tue Feb 18 2025 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-13
- Adapt use-system-abseil-cpp patch for abseil-cpp 20250127

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.29.5111.102-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Mon Oct  7 2024 Akira TAGOH <tagoh@redhat.com> - 2.29.5111.102-11
- Backport a patch to fix key event behavior with modifier keys.
  Resolves rhbz#2257171

* Sun Aug 25 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-10
- Rebuilt for abseil-cpp-20240722.0

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.29.5111.102-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Sun Feb 04 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-8
- Rebuilt for abseil-cpp-20240116.0

* Thu Jan 25 2024 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-7
- Don’t link the top-level absl_flags library; it is not required in
  absl-cpp-20230802, and not present in absl-cpp-20240116
- Add #include directives for compatibility with absl-cpp-20240116

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.29.5111.102-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.29.5111.102-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Nov 16 2023 Benjamin A. Beasley <code@musicinmybrain.net> - 2.29.5111.102-4
- Add missing BuildRequires: desktop-file-utils

* Thu Aug 17 2023 Akira TAGOH <tagoh@redhat.com> - 2.29.5111.102-3
- Fix the build issue with newer abseil.
  Resolves: rhbz#2231905

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.29.5111.102-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Fri Jun 23 2023 Akira TAGOH <tagoh@redhat.com> - 2.29.5111.102-1
- Update to 2.29.5111.102.
  Resolves: rhbz#2213058
- Update dictionaries.

* Tue Apr  4 2023 Akira TAGOH <tagoh@redhat.com> - 2.28.4950.102-5
- Migrated license tag to SPDX.

* Fri Mar 24 2023 Akira TAGOH <tagoh@redhat.com> - 2.28.4950.102-4
- Rebuilt for abseil-cpp 20230125.1

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.28.4950.102-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Jan 11 2023 Akira TAGOH <tagoh@redhat.com> - 2.28.4950.102-2
- Fix another compiler warnings in mozc.el
  Resolves: rhbz#2158787

* Thu Jan  5 2023 Akira TAGOH <tagoh@redhat.com> - 2.28.4950.102-1
- Update to 2.28.4950.102.
- Update dictionaries.
- Fix obsolete function warnings in mozc.el
  Resolves: rhbz#2155094

* Mon Aug 22 2022 Akira TAGOH <tagoh@redhat.com> - 2.28.4730.102-3
- Rebuilt for abseil-cpp 20220623.0

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.28.4730.102-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu May 12 2022 Akira TAGOH <tagoh@redhat.com> - 2.28.4730.102-1
- Update to 2.28.4730.102.

* Wed Mar 09 2022 Akira TAGOH <akira@tagoh.org> - 2.26.4577.102-3
- Rebuild for abseil-cpp 20211102.0

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.26.4577.102-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Fri Dec 17 2021 Akira TAGOH <tagoh@redhat.com> - 2.26.4577.102-1
- Update to 2.26.4577.102.
- Make sure Xwayland is running at the startup.
  Resolves: rhbz#2031477

* Tue Nov  9 2021 Jerry James <loganjerry@gmail.com> - 2.25.4190.102-10
- Drop support for XEmacs in F36 and later

* Sat Nov 06 2021 Adrian Reber <adrian@lisas.de> - 2.25.4190.102-9
- Rebuilt for protobuf 3.19.0

* Tue Oct 26 2021 Adrian Reber <adrian@lisas.de> - 2.25.4190.102-8
- Rebuilt for protobuf 3.18.1

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.25.4190.102-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Fri Jun 18 2021 Takao Fujiwara <tfujiwar@redhat.com> - 2.25.4190.102-6
- Delete ibus write-cache in scriptlet

* Wed Apr 21 2021 Takao Fujiwara <tfujiwar@redhat.com> - 2.25.4190.102-5
- Resolves: #1948197 Change post to posttrans in ibus-mozc

* Tue Mar 30 2021 Jonathan Wakely <jwakely@redhat.com> - 2.25.4190.102-4
- Rebuilt for removed libstdc++ symbol (#1937698)

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.25.4190.102-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Thu Jan 14 08:32:28 CET 2021 Adrian Reber <adrian@lisas.de> - 2.25.4190.102-2
- Rebuilt for protobuf 3.14

* Thu Nov 19 2020 Akira TAGOH <tagoh@redhat.com> - 2.25.4190.102-1
- Updates to 2.25.4190.102.

* Thu Sep 24 2020 Adrian Reber <adrian@lisas.de> - 2.23.2815.102-14
- Rebuilt for protobuf 3.13

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.23.2815.102-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Jun 23 2020 Akira TAGOH <tagoh@redhat.com> - 2.23.2815.102-12
- Fix the build failure with the latest protobuf.

* Sun Jun 14 2020 Adrian Reber <adrian@lisas.de> - 2.23.2815.102-11
- Rebuilt for protobuf 3.12

* Wed Apr  8 2020 Akira TAGOH <tagoh@redhat.com> - 2.23.2815.102-10
- BR qt5-qtbase-devel instead of qt5-devel.

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.23.2815.102-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Aug  1 2019 Akira TAGOH <tagoh@redhat.com> - 2.23.2815.102-8
- Port python code to get it work in python 3.

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.23.2815.102-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Wed Jun  5 2019 Akira TAGOH <tagoh@redhat.com> - 2.23.2815.102-6
- Install appdata file under %%{_metainfodir}.

* Fri May 10 2019 Akira TAGOH <tagoh@redhat.com> - 2.23.2815.102-5
- Add new Japanese era to dictionary.
- Update zipcode dictionaries.
- Make zinnia-tomoe-ja the weak dependency.

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.23.2815.102-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Wed Nov 21 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 2.23.2815.102-3
- Rebuild for protobuf 3.6

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.23.2815.102-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed May 30 2018 Akira TAGOH <tagoh@redhat.com> - 2.23.2815.102-1
- Updates to 2.23.2815.102.

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.23.2785.102-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Fri Jan 26 2018 Akira TAGOH <tagoh@redhat.com> - 2.23.2785.102-1
- Updates to 2.23.2785.102.
- Update zipcode dictionaries.

* Wed Nov 29 2017 Igor Gnatenko <ignatenko@redhat.com> - 2.20.2677.102-7
- Rebuild for protobuf 3.5

* Mon Nov 13 2017 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 2.20.2677.102-6
- Rebuild for protobuf 3.4

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.20.2677.102-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.20.2677.102-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Mon Jun 19 2017 Akira TAGOH <tagoh@redhat.com> - 2.20.2677.102-3
- Add s390x to ExcludeArch.

* Tue Jun 13 2017 Orion Poplawski <orion@cora.nwra.com> - 2.20.2677.102-2
- Rebuild for protobuf 3.3.1

* Mon Feb  6 2017 Akira TAGOH <tagoh@redhat.com> - 2.20.2677.102-1
- New upstream release. (#1410982)
- Update zipcode dictionaries.

* Thu Jan 26 2017 Orion Poplawski <orion@cora.nwra.com> - 2.17.2322.102-3
- Rebuild for protobuf 3.2.0

* Sat Nov 19 2016 Orion Poplawski <orion@cora.nwra.com> - 2.17.2322.102-2
- Rebuild for protobuf 3.1.0

* Fri Jun  3 2016 Akira TAGOH <tagoh@redhat.com> - 2.17.2322.102-1
- Update to 2.17.2322.102.

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 2.17.2077.102-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Mon Jan  4 2016 Akira TAGOH <tagoh@redhat.com>
- Use %%global instead of %%define.

* Wed Sep 16 2015 Richard Hughes <rhughes@redhat.com> - 2.17.2077.102-6
- Increase AppStream search result weighting when using the 'ja' locale.

* Tue Jun 23 2015 Akira TAGOH <tagoh@redhat.com> - 2.17.2077.102-5
- Merge emacs sub-packages into main (#1234578)

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.17.2077.102-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Mon May 11 2015 Akira TAGOH <tagoh@redhat.com> - 2.17.2077.102-3
- Build with the proper compiler options to get the debugging information. (#1219594)

* Wed Apr 29 2015 Kalev Lember <kalevlember@gmail.com> - 2.17.2077.102-2
- Rebuilt for protobuf soname bump

* Tue Apr 28 2015 Akira TAGOH <tagoh@redhat.com> - 2.17.2077.102-1
- rebase to 2.17.2077.102.

* Wed Mar 25 2015 Richard Hughes <rhughes@redhat.com> - 1.15.1814.102-4
- Register as an AppStream component.

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.15.1814.102-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Wed Aug  6 2014 Akira TAGOH <tagoh@redhat.com> - 1.15.1814.102-2
- Drop BR: openssl-devel (#1126245)
- Fix the broken deps for the recent changes in zinnia.

* Thu Jun 26 2014 Akira TAGOH <tagoh@redhat.com> - 1.15.1814.102-1
- New upstream release.
- Update zipcode.

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.13.1651.102-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Wed Jan  8 2014 Akira TAGOH <tagoh@redhat.com> - 1.13.1651.102-1
- New upstream release (#1048793)

* Tue Nov  5 2013 Akira TAGOH <tagoh@redhat.com> - 1.12.1599.102-1
- New upstream release (#1026004)
- Update zipcode.

* Tue Oct  1 2013 Akira TAGOH <tagoh@redhat.com> - 1.11.1522.102-3
- Disable ibus-mozc on the password box in gtk. (#1013789)
- Update zipcode.

* Fri Sep 27 2013 Akira TAGOH <tagoh@redhat.com> - 1.11.1522.102-2
- Update ibus cache at %%post/%%postun.

* Tue Sep  3 2013 Akira TAGOH <tagoh@redhat.com> - 1.11.1522.102-1
- New upstream release (#1003331)

* Fri Aug 16 2013 Akira TAGOH <tagoh@redhat.com> - 1.11.1502.102-3
- Fix no setup icon at gnome-control-center.

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.11.1502.102-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Fri Jul 19 2013 Akira TAGOH <tagoh@redhat.com> - 1.11.1502.102-1
- New upstream release. (#985318)
- Update zipcode dictionaries.

* Mon Apr 15 2013 Akira TAGOH <tagoh@redhat.com> - 1.10.1390.102-1
- New upstream release. (#328711)
- Move credit text since it was referenced by the program at runtime.

* Thu Mar 28 2013 Akira TAGOH <tagoh@redhat.com> - 1.10.1389.102-1
- New upstream release. (#928711)
- Improve the spec file (#891078)

* Wed Mar 13 2013 Akira TAGOH <tagoh@redhat.com> - 1.6.1187.102-4
- Apply an upstream patch to fix a text property for menus (#920122)
- Update zipcode dictionaries.

* Tue Mar 12 2013 Akira TAGOH <tagoh@redhat.com> - 1.6.1187.102-3
- Rebuild against latest protobuf.

* Mon Jan 28 2013 Akira TAGOH <tagoh@redhat.com> - 1.6.1187.102-2
- Add ibus-setup-mozc-jp.desktop to make the configuration tool accessible
  from the input source configuration on control-center. (#904625)
- Updated License, BR, and Summary. partially fixes of #891078

* Fri Aug 31 2012 Akira TAGOH <tagoh@redhat.com> - 1.6.1187.102-1
- New upstream release. (#853362)
  - no SCIM support anymore.
- Update zipcode dictionaries.

* Fri Jul 20 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.5.1090.102-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Thu Jun  7 2012 Akira TAGOH <tagoh@redhat.com> - 1.5.1090.102-2
- Enable mozc_renderer.

* Tue Jun  5 2012 Akira TAGOH <tagoh@redhat.com> - 1.5.1090.102-1
- New upstream release. (#828202)
- Update zipcode dictionaries.
- set "default" to the layout in mozc.xml to avoid adding jp keyboard layout
  unexpectedly.

* Thu Apr 26 2012 Akira TAGOH <tagoh@redhat.com> - 1.5.1053.102-1
- New upstream release. (#816526)
- Update zipcode dictionaries.

* Mon Mar 26 2012 Akira TAGOH <tagoh@redhat.com> - 1.4.1033.102-1
- New upstream release.

* Fri Mar  9 2012 Takao Fujiwara <tfujiwar@redhat.com> - 1.4.1003.102-2
- Rebuild for ibus 1.4.99.20120304

* Thu Mar  8 2012 Akira TAGOH <tagoh@redhat.com> - 1.4.1003.102-1
- New upstream release.
- Update zipcode dictionaries.

* Wed Mar  7 2012 Takao Fujiwara <tfujiwar@redhat.com> - 1.3.975.102-3
- Rebuild for ibus 1.4.99.20120304

* Mon Feb 27 2012 Akira TAGOH <tagoh@redhat.com> - 1.3.975.102-2
- Fix docdir.

* Mon Feb 13 2012 Akira TAGOH <tagoh@redhat.com> - 1.3.975.102-1
- New upstream release.
- Update zipcode dictionaries.

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.3.930.102-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Wed Dec 21 2011 Akira TAGOH <tagoh@redhat.com> - 1.3.930.102-1
- New upstream release.

* Thu Dec  1 2011 Akira TAGOH <tagoh@redhat.com> - 1.3.911.102-1
- New upstream release.

* Tue Nov 29 2011 Akira TAGOH <tagoh@redhat.com> - 1.2.855.102-2
- Add zipcode dictionary.

* Tue Nov 15 2011 Akira TAGOH <tagoh@redhat.com> - 1.2.855.102-1
- New upstream release.

* Fri Sep 30 2011 Akira TAGOH <tagoh@redhat.com> - 1.2.831.102-1
- New upstream release.

* Wed Aug 17 2011 Akira TAGOH <tagoh@redhat.com> - 1.2.809.102-1
- New upstream release.

* Thu Aug 11 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.773.102-3
- Re-enable hotkeys support and add a symbol. (#727022)

* Thu Jul 21 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.773.102-1
- New upstream release.

* Mon Jul 11 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.758.102-2
- Revert hotkeys patch.

* Mon Jul  4 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.758.102-1
- New upstream release.

* Mon Jun 13 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.717.102-3
- Rebuild against new protobuf.

* Wed Jun  1 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.717.102-2
- Fix broken emacs-mozc package.

* Mon May 23 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.717.102-1
- New upstream release.

* Wed Apr 20 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.690.102-0.2.20110419svn
- Fix a wrong path to the model file for handwriting.
- add dep to zinnia-tomoe.

* Tue Apr 19 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.690.102-0.1.20110419svn
- Update to 1.1.690.102.

* Tue Mar  8 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.626.102-0.2.20110301svn
- Fix mozc.el not working when byte-compiled.

* Wed Mar  2 2011 Akira TAGOH <tagoh@redhat.com> - 1.1.626.102-0.1.20110301svn
- Update to 1.1.626.102.

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.558.102-0.2.20101216svn
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Thu Dec 16 2010 Akira TAGOH <tagoh@redhat.com> - 1.0.558.102-0.1.20101216svn
- Update to 1.0.558.102.

* Mon Nov  8 2010 Akira TAGOH <tagoh@redhat.com> - 0.13.523.102-0.2.20101104svn
- Rebuilt against ibus-1.3.99.

* Thu Nov  4 2010 Akira TAGOH <tagoh@redhat.com> - 0.13.523.102-0.1.20101104svn
- Update to 0.13.523.102.

* Fri Oct  8 2010 Akira TAGOH <tagoh@redhat.com> - 0.13.499.102-0.1.20101008svn
- Update to 0.13.499.102.

* Mon Sep 27 2010 Akira TAGOH <tagoh@redhat.com> - 0.13.481.102-0.1.20100927svn
- Update to 0.13.481.102.
- Add emacs-common-mozc, emacs-mozc, emacs-mozc-el, xemacs-mozc and xemacs-mozc-el subpackage.

* Fri Sep 10 2010 Akira TAGOH <tagoh@redhat.com> - 0.13.464.102-0.1.20100910svn
- Update to 0.13.464.102.

* Mon Aug 23 2010 Akira TAGOH <tagoh@redhat.com> - 0.12.434.102-0.2.20100823svn
- Drop the unnecessary Obsoletes tag.
- Output more build messages. (Mamoru Tasaka)
- Own %%{_datadir}/ibus-mozc
- add credits_*.html
- rebase to drop more exec bits.

* Fri Aug 20 2010 Akira TAGOH <tagoh@redhat.com> - 0.12.434.102-0.1.20100820svn
- drop exec bits for source code.
- clean up spec file.
- add mecab-ipadic to License tag.

* Tue Aug 17 2010 Akira TAGOH <tagoh@redhat.com> - 0.12.434.102-0.1.20100817svn
- Update to 0.12.434.102.

* Thu Jul 29 2010 Akira TAGOH <tagoh@redhat.com> - 0.12.422.102-0.1.20100729svn
- Update to 0.12.422.102.

* Mon Jul 12 2010 Akira TAGOH <tagoh@redhat.com> - 0.12.410.102-0.1.20100712svn
- Update to 0.12.410.102.

* Tue Jun 22 2010 Akira TAGOH <tagoh@redhat.com> - 0.11.383.102-0.1.20100621svn
- Update to 0.11.383.102.
- Add a subpackage for scim.

* Thu May 27 2010 Akira TAGOH <tagoh@redhat.com> - 0.11.365.102-0.1.20100527svn
- Update to 0.11.365.102.
- Update mozc-config.
- correct the server directory.

* Thu May 20 2010 Akira TAGOH <tagoh@redhat.com> - 0.11.354.100-0.1.20100520svn
- Updates from svn.
- Add mozc-config from git.

* Tue May 11 2010 Akira TAGOH <tagoh@redhat.com> - 0.10.288.102-0.1.20100511svn
- Initial build.

