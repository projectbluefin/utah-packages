Name:           libpinyin
Version:        2.11.92
Release:        1%{?dist}
Summary:        Library to deal with pinyin

License:        GPL-3.0-or-later
URL:            https://github.com/libpinyin/libpinyin
Source0:        http://downloads.sourceforge.net/libpinyin/libpinyin/%{name}-%{version}.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  kyotocabinet-devel, glib2-devel
BuildRequires:  make
Requires:       %{name}-data%{?_isa} = %{version}-%{release}

%description
The libpinyin project aims to provide the algorithms core
for intelligent sentence-based Chinese pinyin input methods.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name} = %{version}-%{release}
Requires:       libzhuyin = %{version}-%{release}
Provides:       libzhuyin-devel = %{version}-%{release}
Obsoletes:      libzhuyin-devel < %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%package        data
Summary:        Data files for %{name}
Requires:       %{name} = %{version}-%{release}

%description data
The %{name}-data package contains data files.

%package        tools
Summary:        Tools for %{name}
Requires:       %{name} = %{version}-%{release}

%description tools
The %{name}-tools package contains tools.

%package -n     libzhuyin
Summary:        Library to deal with zhuyin
Requires:       %{name} = %{version}-%{release}

%description -n libzhuyin
The libzhuyin package contains libzhuyin compatibility library.


%prep
%setup -q

%build
%configure --disable-static \
           --with-dbm=KyotoCabinet \
           --enable-libzhuyin
%make_build

%check
make check

%install
%make_install
find $RPM_BUILD_ROOT -name '*.la' -exec rm -f {} ';'


%files
%doc AUTHORS COPYING README
%{_libdir}/libpinyin*.so.*
%dir %{_libdir}/libpinyin

%files devel
%doc
%dir %{_includedir}/libpinyin-%{version}
%{_includedir}/libpinyin-%{version}/*
%{_libdir}/libpinyin.so
%{_libdir}/pkgconfig/libpinyin.pc
%{_libdir}/libzhuyin.so
%{_libdir}/pkgconfig/libzhuyin.pc

%files data
%doc
%{_libdir}/libpinyin/data

%files tools
%{_bindir}/gen_binary_files
%{_bindir}/import_interpolation
%{_bindir}/gen_unigram
%{_mandir}/man1/*.1.*

%files -n libzhuyin
%{_libdir}/libzhuyin*.so.*

%changelog
* Tue Sep 29 2026 Peng Wu <alexepico@gmail.com> - 2.11.92-1
- Update to 2.11.92
- bug fixes

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.11.91-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.11.91-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Sun Jan 04 2026 Peng Wu <pwu@redhat.com> - 2.11.91-1
- Update to 2.11.91
- support "sua" and "zua" pinyin input

* Thu Sep 18 2025 Peng Wu <pwu@redhat.com> - 2.10.3-1
- Update to 2.10.3
- bug fixes

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.10.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri May 16 2025 Peng Wu <pwu@redhat.com> - 2.10.2-1
- Update to 2.10.2
- fix memory leaks

* Mon Mar 24 2025 Peng Wu <pwu@redhat.com> - 2.10.1-1
- Update to 2.10.1
- bug fixes

* Fri Mar 21 2025 Peng Wu <pwu@redhat.com> - 2.10.0-2
- bug fixes

* Sat Feb  8 2025 Peng Wu <pwu@redhat.com> - 2.10.0-1
- Update to 2.10.0
- bug fixes

* Mon Jan 20 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.9.93-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.9.93-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Tue Dec 17 2024 Peng Wu <pwu@redhat.com> - 2.9.93-1
- Update to 2.9.93
- bug fixes

* Mon Oct 21 2024 Peng Wu <pwu@redhat.com> - 2.9.92-1
- Update to 2.9.92
- support punctuation candidate

* Tue Aug 13 2024 Peng Wu <pwu@redhat.com> - 2.9.91-1
- Update to 2.9.91
- auto clean user data when data corruption
- support to export bigram phrase

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.8.1-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.8.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.8.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Aug 23 2023 Peng Wu <pwu@redhat.com> - 2.8.1-5
- Switch to use Kyoto Cabinet

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.8.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Fri May 19 2023 Peng Wu <pwu@redhat.com> - 2.8.1-3
- Migrate to SPDX license

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.8.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Mon Jan 16 2023 Peng Wu <pwu@redhat.com> - 2.8.1-1
- Update to 2.8.1
- bug fixes

* Wed Jan  4 2023 Peng Wu <pwu@redhat.com> - 2.8.0-1
- Update to 2.8.0
- bug fixes for ARMv7

* Wed Oct 19 2022 Peng Wu <pwu@redhat.com> - 2.7.92-1
- Update to 2.7.92
- bug fixes

* Wed Oct 19 2022 Peng Wu <pwu@redhat.com> - 2.7.91-1
- Update to 2.7.91
- improve suggestion candidates
- support longer candidates

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.6.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Wed Apr 13 2022 Peng Wu <pwu@redhat.com> - 2.6.2-1
- Update to 2.6.2
- bug fixes

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.6.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Wed Oct 27 2021 Peng Wu <pwu@redhat.com> - 2.6.1-2
- Rebuild the package

* Wed Sep 15 2021 Peng Wu <pwu@redhat.com> - 2.6.1-1
- Update to 2.6.1
- bug fixes

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.6.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.6.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Dec 15 2020 Peng Wu <pwu@redhat.com> - 2.6.0-1
- Update to 2.6.0
- bug fixes

* Thu Oct 22 2020 Peng Wu <pwu@redhat.com> - 2.4.92-1
- Update to 2.4.92
- update pinyin data
- bug fixes

* Wed Aug 26 2020 Peng Wu <pwu@redhat.com> - 2.4.91-1
- Update to 2.4.91
- improve full pinyin auto correction
- bug fixes

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.3.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jul 22 2020 Tom Stellard <tstellar@redhat.com> - 2.3.0-4
- Use make macros
- https://fedoraproject.org/wiki/Changes/UseMakeBuildInstallMacro

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.3.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.3.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Mon Mar 18 2019 Peng Wu <pwu@redhat.com> - 2.3.0-1
- Update to 2.3.0
- update pinyin data

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Mon Jan 21 2019 Peng Wu <pwu@redhat.com> - 2.2.2-1
- Update to 2.2.2
- minor fixes

* Tue Oct  9 2018 Peng Wu <pwu@redhat.com> - 2.2.1-1
- Update to 2.2.1
- fixes predicted candidates

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Tue Apr 17 2018 Peng Wu <pwu@redhat.com> - 2.2.0-1
- Update to 2.2.0
- bug fixes

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.1.91-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Jan 25 2018 Peng Wu <pwu@redhat.com> - 2.1.91-1
- Update to 2.1.91
- fixes zhuyin parsers

* Thu Aug 24 2017 Peng Wu <pwu@redhat.com> - 2.1.0-1
- Update to 2.1.0
- support sort option in pinyin_guess_candidates function

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.92-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.0.92-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Mon Jul 10 2017 Peng Wu <pwu@redhat.com> - 2.0.92-1
- Update to 2.0.92
- reduce memory consumption after imported user dictionary

* Thu Jun  8 2017 Peng Wu <pwu@redhat.com> - 2.0.91-1
- Update to 2.0.91
- merge libzhuyin code

* Thu Apr 20 2017 Peng Wu <pwu@redhat.com> - 2.0.0-1
- Update to 2.0.0

* Tue Mar  7 2017 Peng Wu <pwu@redhat.com> - 1.9.92-1
- Update to 1.9.92
- fixes crash

* Tue Feb 28 2017 Peng Wu <pwu@redhat.com> - 1.9.91-2
- Fixes crash in Double Pinyin

* Tue Feb 14 2017 Peng Wu <pwu@redhat.com> - 1.9.91-1
- Update to 1.9.91
- multiple sentence candidates

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Wed Nov 30 2016 Peng Wu <pwu@redhat.com> - 1.7.0-1
- Update to 1.7.0
- fixes build on FreeBSD
- update cmake files

* Tue Nov  1 2016 Peng Wu <pwu@redhat.com> - 1.6.91-1
- Update to 1.6.91
- change license to GPLv3+
- import open-gram dictionary and remove pinyin tones
- add some checks when load data from file

* Wed Sep  7 2016 Peng Wu <pwu@redhat.com> - 1.6.0-1
- Update to 1.6.0

* Mon Aug 15 2016 Peng Wu <pwu@redhat.com> - 1.5.92-3
- Fixes crashes again

* Tue Aug  9 2016 Peng Wu <pwu@redhat.com> - 1.5.92-2
- Fixes crashes for Full Pinyin and Bopomofo

* Tue Aug  2 2016 Peng Wu <pwu@redhat.com> - 1.5.92-1
- Update to 1.5.92

* Mon Jul 18 2016 Peng Wu <pwu@redhat.com> - 1.5.91-1
- Update to 1.5.91
- Use Kyoto Cabinet instead of Berkeley DB

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Fri Dec  4 2015 Peng Wu <pwu@redhat.com> - 1.3.0-1
- Update to 1.3.0

* Tue Nov 17 2015 Peng Wu <pwu@redhat.com> - 1.2.91-1
- Update to 1.2.91

* Mon Aug  3 2015 Peng Wu <pwu@redhat.com> - 1.2.0-1
- Update to 1.2.0

* Tue Jul  7 2015 Peng Wu <pwu@redhat.com> - 1.1.91-1
- Update to 1.1.91

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sat May 02 2015 Kalev Lember <kalevlember@gmail.com> - 1.1.0-2
- Rebuilt for GCC 5 C++11 ABI change

* Tue Mar  3 2015 Peng Wu <pwu@redhat.com> - 1.1.0-1
- Update to 1.1.0

* Mon Feb  9 2015 Peng Wu <pwu@redhat.com> - 1.0.99.20150212-1
- Update to 1.0.99.20150212
- Bring back libpinyin-tools

* Tue Feb  3 2015 Peng Wu <pwu@redhat.com> - 1.0.99.20150203-2
- Obsoletes libpinyin-tools

* Tue Feb  3 2015 Peng Wu <pwu@redhat.com> - 1.0.99.20150203-1
- Update to 1.0.99.20150203

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Tue Nov 26 2013 Peng Wu <pwu@redhat.com> - 1.0.0-1
- Update to 1.0.0

* Mon Oct 28 2013 Peng Wu <pwu@redhat.com> - 0.9.94-1
- Update to 0.9.94

* Tue Jul 30 2013 Peng Wu <pwu@redhat.com> - 0.9.93-2
- Fixes load table.conf in German locale

* Thu Jun 27 2013 Peng Wu <pwu@redhat.com> - 0.9.93-1
- Update to 0.9.93

* Sun Jun  9 2013 Peng Wu <pwu@redhat.com> - 0.9.92-1
- Update to 0.9.92

* Sun Apr 28 2013 Peng Wu <pwu@redhat.com> - 0.9.91-1
- Update to 0.9.91

* Sat Mar 23 2013 Peng Wu <pwu@redhat.com> - 0.8.93-2
- Fixes import dictionary

* Mon Mar 18 2013 Peng Wu <pwu@redhat.com> - 0.8.93-1
- Update to 0.8.93

* Fri Mar  8 2013 Peng Wu <pwu@redhat.com> - 0.8.92-1
- Update to 0.8.92

* Mon Mar  4 2013 Peng Wu <pwu@redhat.com> - 0.8.91-1
- Update to 0.8.91

* Thu Feb 28 2013 Peng Wu <pwu@redhat.com> - 0.8.1-1
- Update to 0.8.1
- Fixes pinyin_init crashes

* Mon Jan 28 2013 Peng Wu <pwu@redhat.com> - 0.8.0-3
- Fixes incomplete pinyin

* Wed Dec 12 2012 Peng Wu <pwu@redhat.com> - 0.8.0-2
- Fixes chewing input

* Wed Nov 14 2012  Peng Wu <pwu@redhat.com> - 0.8.0-1
- Update to 0.8.0

* Mon Oct 15 2012  Peng Wu <pwu@redhat.com> - 0.7.92-1
- Update to 0.7.92

* Mon Sep 17 2012  Peng Wu <pwu@redhat.com> - 0.7.91-1
- Update to 0.7.91

* Wed Aug 15 2012  Peng Wu <pwu@redhat.com> - 0.7.1-1
- Update to 0.7.1

* Fri Jul 27 2012  Peng Wu <pwu@redhat.com> - 0.7.0-1
- Update to 0.7.0

* Thu Jul 19 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6.92-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Tue Jul 10 2012  Peng Wu <pwu@redhat.com> - 0.6.92-2
- Update libpinyin-0.7.x-head.patch

* Wed Jul 04 2012  Peng Wu <pwu@redhat.com> - 0.6.92-1
- Update to 0.6.92

* Tue Jun 12 2012  Peng Wu <pwu@redhat.com> - 0.6.0-3
- Removes provides ibus-pinyin-db

* Thu Jun 07 2012  Peng Wu <pwu@redhat.com> - 0.6.0-2
- Fixes "jv" => "ju"

* Mon May 28 2012  Peng Wu <pwu@redhat.com> - 0.6.0-1
- Update to 0.6.0

* Tue Mar 27 2012  Peng Wu <pwu@redhat.com> - 0.5.92-1
- Update to 0.5.92

* Wed Feb 15 2012  Peng Wu <pwu@redhat.com> - 0.5.91-3
- Provides ibus-pinyin-db

* Tue Feb 14 2012  Peng Wu <pwu@redhat.com> - 0.5.91-2
- Improves full pinyin parser2

* Mon Feb 13 2012  Peng Wu <pwu@redhat.com> - 0.5.91-1
- Update to 0.5.91

* Sun Jan 29 2012  Peng Wu <pwu@redhat.com> - 0.5.0-2
- Fixes pinyin parsers

* Wed Jan 18 2012  Peng Wu <pwu@redhat.com> - 0.5.0-1
- Update to 0.5.0

* Fri Jan 13 2012  Peng Wu <pwu@redhat.com> - 0.4.93-1
- Update to 0.4.93

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.4.92-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Thu Dec 29 2011  Peng Wu <pwu@redhat.com> - 0.4.92-1
- Update to 0.4.92

* Tue Dec 27 2011  Peng Wu <pwu@redhat.com> - 0.4.91-1
- Update to 0.4.91

* Fri Nov 25 2011  Peng Wu <pwu@redhat.com> - 0.3.0-2
- Increase train factor

* Fri Nov 18 2011  Peng Wu <pwu@redhat.com> - 0.3.0-1
- Update to 0.3.0

* Thu Nov 03 2011  Peng Wu <pwu@redhat.com> - 0.2.99.3-1
- Update to 0.2.99.3

* Mon Oct 31 2011  Peng Wu <pwu@redhat.com> - 0.2.99.2-5
- Fixes memory leak and save_db

* Thu Oct 27 2011  Peng Wu <pwu@redhat.com> - 0.2.99.2-4
- Update libpinyin-0.3.x-head.patch

* Thu Oct 27 2011  Peng Wu <pwu@redhat.com> - 0.2.99.2-3
- Add requires

* Thu Oct 27 2011  Peng Wu <pwu@redhat.com> - 0.2.99.2-2
- Add patch libpinyin-0.3.x-head.patch

* Tue Oct 11 2011  Peng Wu <pwu@redhat.com> - 0.2.99.2-1
- Update to 0.2.99.2

* Wed Sep 28 2011  Peng Wu <pwu@redhat.com> - 0.2.99.1-1
- Update to 0.2.99.1

* Thu Sep 08 2011  Peng Wu <pwu@redhat.com> - 0.2.99-2
- Split data sub package

* Wed Aug 31 2011  Peng Wu <alexepico@gmail.com> - 0.2.99-1
- Initial version
