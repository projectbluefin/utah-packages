Name:           davfs2
Version:        1.7.3
Release:        2%{?dist}
Summary:        A filesystem driver for WebDAV
# Automatically converted from old format: GPLv3+ - review is highly recommended.
License:        GPL-3.0-or-later
URL:            https://savannah.nongnu.org/projects/davfs2
Source0:        https://download.savannah.gnu.org/releases/davfs2/%{name}-%{version}.tar.gz
Source1:        https://download.savannah.gnu.org/releases/davfs2/%{name}-%{version}.tar.gz.sig
# key retrieved via
#  wget -O davfs2-memberlist-gpgkeys.asc 'https://savannah.nongnu.org/project/memberlist-gpgkeys.php?group=davfs2&download=1'
# Using the URL above directly as "Source2" does not work as spectool/mock do
# no not like the query string.
Source2:        davfs2-memberlist-gpgkeys.asc

Conflicts:      filesystem < 3
BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  gnupg2
BuildRequires:  neon-devel
BuildRequires:  make

%define cachedir /var/cache/davfs2
%define piddir /var/run/mount.davfs
%define username davfs2
%define groupname %{username}

%description
davfs2 is a Linux file system driver that allows you to mount a WebDAV server
as a disk drive.

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%setup -q

# Create a sysusers.d config file
cat >davfs2.sysusers.conf <<EOF
g davfs2 -
u davfs2 - 'User account for %{name}' %{cachedir} -
EOF

%build
export CFLAGS="%{optflags} -fno-strict-aliasing"
%configure ssbindir=%{_sbindir}
%make_build


%install
%make_install
%find_lang %{name}
# Create directories used by mount.davfs
install -d $RPM_BUILD_ROOT%{cachedir} $RPM_BUILD_ROOT%{piddir}
# Don't need this - we'll do our own doc install, thanks
rm -rf $RPM_BUILD_ROOT/usr/share/doc/davfs2
# Remove suid bit, to work around a problem with brp-strip on suid binaries
chmod 0755 $RPM_BUILD_ROOT/%{_sbindir}/mount.davfs
# UTF8ify translated man pages
find $RPM_BUILD_ROOT/%{_mandir}/{de,es} -name "*.[58].gz" | while read m; do 
  gzip -dc $m | iconv -f "ISO8859-15" -t "UTF-8" - -o - | gzip -c9 > $m.utf8
  mv -f $m.utf8 $m
done

install -m0644 -D davfs2.sysusers.conf %{buildroot}%{_sysusersdir}/davfs2.conf




%files -f %{name}.lang
# Docs
%license AUTHORS COPYING
%doc BUGS ChangeLog FAQ INSTALL NEWS README.md README.translators THANKS TODO
%{_mandir}/man5/*.gz
%{_mandir}/man8/*.gz
# localized man pages
%{_mandir}/*/man5/*.gz
%{_mandir}/*/man8/*.gz

# Configfiles etc.
%config(noreplace) %{_sysconfdir}/davfs2/davfs2.conf
%config(noreplace) %{_sysconfdir}/davfs2/secrets
%dir %{_sysconfdir}/davfs2/certs/private/
%dir %{_sysconfdir}/davfs2/certs/
%dir %{_sysconfdir}/davfs2/
%dir %{_datarootdir}/davfs2/
%{_datarootdir}/davfs2/*

# Binaries
%{_sbindir}/umount.davfs
# re-apply suid bit to mount.davfs
%attr (4755,root,root) %{_sbindir}/mount.davfs

# Extra dirs needed by mount.davfs
%ghost %dir %attr(00775,root,%{groupname}) %{cachedir}
%ghost %dir %attr(01775,root,%{groupname}) %{piddir}
%{_sysusersdir}/davfs2.conf

%changelog
* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Mar 13 2026 Paul Howarth <paul@city-fan.org> - 1.7.3-1
- Update to 1.7.3 (rhbz#2447065)
  - Add musl support
  - Fix macro-substitution in manual pages
  - Remove hardcoded neon versions from configure.ac
- Consider AUTHORS as a license file rather than just documentation

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Tue Aug 26 2025 Paul Howarth <paul@city-fan.org> - 1.7.2-1
- Update to 1.7.2 (rhbz#2391098)
  - Add support for libneon 34, 35
  - Increase buf read size to 64 (fixes read issue on linux 6.16)
  - Allow setting a mount password via DAVFS_PASSWORD
  - Introduce sync_on_lookup option (off by default)
  - Don't compress man pages

* Thu Jul 31 2025 Paul Howarth <paul@city-fan.org> - 1.7.1-5
- Add support for building with neon version 0.35 (rhbz#2384528)

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Tue Feb 11 2025 Zbigniew Jędrzejewski-Szmek <zbyszek@in.waw.pl> - 1.7.1-3
- Add sysusers.d config file to allow rpm to create users/groups automatically

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Fri Dec 06 2024 Felix Schwarz <fschwarz@fedoraproject.org> - 1.7.1-1
- update to 1.7.1

* Thu Jul 25 2024 Miroslav Suchý <msuchy@redhat.com> - 1.7.0-7
- convert license to SPDX

* Wed Jul 17 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.7.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Sat Nov 05 2022 Felix Schwarz <fschwarz@fedoraproject.org> - 1.7.0-1
- update to 1.7.0

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.6.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Sat Jan 22 2022 Felix Schwarz <fschwarz@fedoraproject.org> - 1.6.1-1
- update to 1.6.1

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.6.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Wed Jul 21 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.6.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.6.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Fri Aug 07 2020 Felix Schwarz <fschwarz@fedoraproject.org> - 1.6.0-1
- update to 1.6.0

* Sat Aug 01 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.6-4
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.6-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jan 29 2020 Felix Schwarz <fschwarz@fedoraproject.org> - 1.5.6-3
- fix build with GCC 10

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Sat Dec 28 2019 Felix Schwarz <fschwarz@fedoraproject.org> - 1.5.6-1
- Update to 1.5.6

* Thu Nov 28 2019 Felix Schwarz <fschwarz@fedoraproject.org> - 1.5.5-2
- enable GPG source file verification
- fix license declaration (GPLv3+)

* Mon Aug 05 2019 Filipe Rosset <rosset.filipe@gmail.com> - 1.5.5-1
- Update to 1.5.5

* Mon Aug 05 2019 Filipe Rosset <rosset.filipe@gmail.com> - 1.5.4-11
- spec cleanup and modernization

* Wed Jul 24 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.4-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.4-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Thu Jul 12 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.4-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.4-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.4-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.4-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.5.4-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Fri May 27 2016 moez.roy@gmail.com - 1.5.4-3
- update to latest upstream 

* Fri May 27 2016 moez.roy@gmail.com - 1.5.4-2
- rebuilt

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.7-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.7-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sat Aug 16 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.7-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.7-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Thu Sep 19 2013 Will Woods <wwoods@redhat.com> - 1.4.7-3
- CVE-2013-4362: Fix possibly insecure use of system()

* Fri Sep 13 2013 Paul Howarth <paul@city-fan.org> - 1.4.7-2
- Add support for building with neon 0.30.0 (#992110)
- Use -fno-strict-aliasing

* Tue Feb 26 2013 Erik Logtenberg <erik@logtenberg.eu> - 1.4.7-1
- New upstream release
- The check for somebody else's home directory is gone. So you should
  be able to mount in /media/foo even if / is the home of some daemon.

* Wed Feb 13 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.6-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Wed Jul 18 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.6-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Sat Jun 2 2012 Will Woods <wwoods@redhat.com> 1.4.6-4
- Mark /var/cache/davfs2 and /var/run/mount.davfs %%ghost (#656570)
- Fix 'cannot stat `/usr/share/davfs2/davfs2.conf'' warning (#783788)

* Wed Jan 25 2012 Harald Hoyer <harald@redhat.com> 1.4.6-3
- install everything in /usr
  https://fedoraproject.org/wiki/Features/UsrMove

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Wed Nov 09 2011 Will Woods <wwoods@redhat.com> - 1.4.6-1
- New upstream release. From the upstream changelog:
- Fix assignment of password from pam_mount (bug #28706)
- Fix log messages in dav_create

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Mon Feb 15 2010 Will Woods <wwoods@redhat.com> - 1.4.5-2
- Add davfs2-1.4.5-sys_stat_h.patch to fix building on F13

* Wed Jan 13 2010 Will Woods <wwoods@redhat.com> - 1.4.5-1
- New upstream release (fixes rebuild failure, see bug 538913)
- NOTE: 1.4.x has different config file syntax. Read the NEWS file!

* Thu Sep 17 2009 Peter Lemenkov <lemenkov@gmail.com> - 1.3.3-5
- bump

* Thu Sep 17 2009 Peter Lemenkov <lemenkov@gmail.com> - 1.3.3-4
- Rebuilt with new fuse

* Fri Jul 24 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.3.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Wed Mar 11 2009 Will Woods <wwoods@redhat.com> - 1.3.3-2
- Passed package review (#488858)
- Ensure that package owns /etc/davfs2 and /etc/davfs2/certs

* Mon Mar 02 2009 Will Woods <wwoods@redhat.com> - 1.3.3-1
- Initial packaging
- Fix open() with O_CREAT and no mode
