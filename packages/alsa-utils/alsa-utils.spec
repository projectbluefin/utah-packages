%define   baseversion     1.2.16
#define   fixversion      .1
%global   _hardened_build 1

%global   utils_patch     0

Summary: Advanced Linux Sound Architecture (ALSA) utilities
Name:    alsa-utils
Version: %{baseversion}%{?fixversion}
Release: 2%{?dist}
License: GPL-2.0-or-later
URL:     http://www.alsa-project.org/
# The upstream FTP endpoint is still what Fedora records, but this factory
# only accepts source archives over HTTP(S). The project's HTTPS mirror serves
# the same release bytes and is verified by the source lock.
Source:  https://www.alsa-project.org/files/pub/utils/alsa-utils-%{version}.tar.bz2
Source4: alsaunmute
Source5: alsaunmute.1
Source11: alsactl.conf
Source20: alsa-restore.service
Source22: alsa-state.service
%if %{utils_patch}
Patch1:  alsa-git.patch
%endif

BuildRequires: gcc
BuildRequires: autoconf automake libtool
BuildRequires: alsa-lib-devel >= %{baseversion}
BuildRequires: libsamplerate-devel
BuildRequires: ncurses-devel
BuildRequires: gettext-devel
BuildRequires: xmlto
BuildRequires: python3-docutils
BuildRequires: systemd
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
# use latest alsa-lib - the executables in this package requires latest API
Requires: alsa-lib%{?_isa} >= %{baseversion}
Requires: alsa-ucm >= %{baseversion}

%description
This package contains command line utilities for the Advanced Linux Sound
Architecture (ALSA).

%package -n alsa-ucm-utils
Summary: Advanced Linux Sound Architecture (ALSA) - Use Case Manager

%description -n alsa-ucm-utils
This package contains Use Case Manager tools for Advanced Linux Sound
Architecture (ALSA) framework.

%package -n alsa-topology-utils
Summary: Advanced Linux Sound Architecture (ALSA) - Topology
Requires: alsa-topology >= %{baseversion}

%description -n alsa-topology-utils
This package contains topology tools for Advanced Linux Sound
Architecture (ALSA) framework.

%package alsabat
Summary: Advanced Linux Sound Architecture (ALSA) - Basic Audio Tester
BuildRequires: fftw-devel
BuildRequires: make

%description alsabat
This package contains tool for basic audio testing using Advanced Linux Sound
Architecture (ALSA) framework and Fast Fourier Transform library.

%prep
%setup -q -n %{name}-%{version}
%if %{utils_patch}
%patch -P1 -p1 -b .alsa-git
%endif

%build
autoreconf -vif
%configure CFLAGS="$RPM_OPT_FLAGS -D_LARGEFILE_SOURCE -D_FILE_OFFSET_BITS=64" --disable-alsaconf \
   --with-udev-rules-dir=%{_prefix}/lib/udev/rules.d \
   --with-systemdsystemunitdir=%{_unitdir} \
   --with-alsactl-udev-args="-E ALSA_CONFIG_PATH=/etc/alsa/alsactl.conf --initfile=/lib/alsa/init/00main" \
   --with-alsactl-udev-extra-test=""
make %{?_smp_mflags}
cp %{SOURCE4} .

%install
%global alsacfgdir %{_prefix}/lib/alsa

make install DESTDIR=%{buildroot}
%find_lang %{name}

# Install ALSA udev rules and services
mkdir -p %{buildroot}/%{_prefix}/lib/udev/rules.d
mkdir -p %{buildroot}/%{_unitdir}
install -p -m 644 %{SOURCE20} %{buildroot}/%{_unitdir}/alsa-restore.service
install -p -m 644 %{SOURCE22} %{buildroot}/%{_unitdir}/alsa-state.service

# Install support utilities
mkdir -p -m755 %{buildroot}/%{_bindir}
install -p -m 755 %{SOURCE4} %{buildroot}/%{_bindir}
mkdir -p -m755 %{buildroot}/%{_mandir}/man1
install -p -m 644 %{SOURCE5} %{buildroot}/%{_mandir}/man1/alsaunmute.1

# Move /usr/share/alsa/init to /usr/lib/alsa/init
mkdir -p -m 755 %{buildroot}%{alsacfgdir}
mv %{buildroot}%{_datadir}/alsa/init %{buildroot}%{alsacfgdir}

# Link /usr/lib/alsa/init to /usr/share/alsa/init back
ln -s ../../lib/alsa/init %{buildroot}%{_datadir}/alsa/init

# Create a place for global configuration
mkdir -p -m 755 %{buildroot}/etc/alsa
install -p -m 644 %{SOURCE11} %{buildroot}/etc/alsa

# Create /var/lib/alsa tree
mkdir -p -m 755 %{buildroot}%{_sharedstatedir}/alsa

find %{buildroot} -name "*.la" -exec rm {} \;

%files -f %{name}.lang
%doc COPYING ChangeLog README.md TODO alsamixer/alsamixer.rc.example
%config /etc/alsa/*
%{_prefix}/lib/udev/rules.d/*
%{_unitdir}/*
#{_unitdir}/sound.target.wants/*
%{alsacfgdir}/init/*
%{_bindir}/aconnect
%{_sbindir}/alsactl
%{_bindir}/alsaloop
%{_bindir}/alsamixer
%{_bindir}/alsaunmute
%{_sbindir}/alsa-info.sh
%{_bindir}/amidi
%{_bindir}/amixer
%{_bindir}/aplay
%{_bindir}/aplaymidi
%{_bindir}/aplaymidi2
%{_bindir}/arecord
%{_bindir}/arecordmidi
%{_bindir}/arecordmidi2
%{_bindir}/aseqdump
%{_bindir}/aseqnet
%{_bindir}/aseqsend
%{_bindir}/axfer
%{_bindir}/iecset
%{_bindir}/nhlt-dmic-info
%{_bindir}/speaker-test
%{_datadir}/alsa/
%{_datadir}/sounds/*
%{_mandir}/man7/*
%{_mandir}/man1/alsactl.1.gz
%{_mandir}/man1/alsaloop.1.gz
%{_mandir}/man1/alsamixer.1.gz
%{_mandir}/man1/alsaunmute.1.gz
%{_mandir}/man1/amidi.1.gz
%{_mandir}/man1/amixer.1.gz
%{_mandir}/man1/aplay.1.gz
%{_mandir}/man1/aplaymidi.1.gz
%{_mandir}/man1/aplaymidi2.1.gz
%{_mandir}/man1/arecord.1.gz
%{_mandir}/man1/arecordmidi.1.gz
%{_mandir}/man1/arecordmidi2.1.gz
%{_mandir}/man1/aseqdump.1.gz
%{_mandir}/man1/aseqnet.1.gz
%{_mandir}/man1/aseqsend.1.gz
%{_mandir}/man1/axfer.1.gz
%{_mandir}/man1/axfer-list.1.gz
%{_mandir}/man1/axfer-transfer.1.gz
%{_mandir}/man1/iecset.1.gz
%{_mandir}/man1/speaker-test.1.gz
%{_mandir}/man1/aconnect.1.gz
%{_mandir}/man8/alsa-info.sh.8.gz
%{_mandir}/man1/nhlt-dmic-info.1.gz

%dir /etc/alsa/
%dir %{alsacfgdir}/
%dir %{alsacfgdir}/init/
%dir %{_sharedstatedir}/alsa/

%files -n alsa-ucm-utils
%{_bindir}/alsaucm
%{_mandir}/man1/alsaucm.1.gz

%files -n alsa-topology-utils
%{_bindir}/alsatplg
%{_mandir}/man1/alsatplg.1.gz
%{_libdir}/alsa-topology/libalsatplg_module_*

%files alsabat
%{_bindir}/alsabat
%{_sbindir}/alsabat-test.sh
%{_mandir}/man1/alsabat.1.gz

%pre
if [ ! -r %{_unitdir}/alsa-state.service ]; then
  [ -d /etc/alsa ] || mkdir -m 0755 /etc/alsa
  echo "# Remove this file to disable the alsactl daemon mode" > \
                                                    /etc/alsa/state-daemon.conf
fi

%post
if [ -s /etc/alsa/asound.state -a ! -s /etc/asound.state ] ; then
  mv /etc/alsa/asound.state /etc/asound.state
fi
if [ -s /etc/asound.state -a ! -s %{_sharedstatedir}/alsa/asound.state ] ; then
  mv /etc/asound.state %{_sharedstatedir}/alsa/asound.state
fi
%systemd_post alsa-state.service

%preun
%systemd_preun alsa-state.service

%postun
%systemd_postun_with_restart alsa-state.service

%changelog
* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.16-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Mon Jun  1 2026 Jaroslav Kysela <perex@perex.cz> - 1.2.16-1
* Updated to 1.2.16

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.15.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.15.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jan  8 2026 Jaroslav Kysela <perex@perex.cz> - 1.2.15.2-1
* Updated to 1.2.15.2

* Thu Jan  1 2026 Jaroslav Kysela <perex@perex.cz> - 1.2.15.1-3
* Apply fix to alsactl (card detection issue)

* Fri Dec 19 2025 Jaroslav Kysela <perex@perex.cz> - 1.2.15.1-1
* Updated to 1.2.15.1

* Mon Dec  8 2025 Jaroslav Kysela <perex@perex.cz> - 1.2.15-2
* Updated to 1.2.15

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.14-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Mon Apr 14 2025 Jaroslav Kysela <perex@perex.cz> - 1.2.14-1
* Updated to 1.2.14

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.13-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Nov 14 2024 Jaroslav Kysela <perex@perex.cz> - 1.2.13-2
* Updated to 1.2.13

* Wed Jul 17 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.12-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Tue Jun 11 2024 Jaroslav Kysela <perex@perex.cz> - 1.2.12-1
* Updated to 1.2.12

* Mon Jan 29 2024 Jaroslav Kysela <perex@perex.cz> - 1.2.11-1
* Updated to 1.2.11

* Mon Jan 22 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.10-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.10-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Sep  1 2023 Jaroslav Kysela <perex@perex.cz> - 1.2.10-1
* Updated to 1.2.10

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.9-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Tue Jun  6 2023 Jaroslav Kysela <perex@perex.cz> - 1.2.9-3
* SPDX license

* Tue May 16 2023 Jaroslav Kysela <perex@perex.cz> - 1.2.9-2
* Add nhlt-dmic-info utility

* Thu May  4 2023 Jaroslav Kysela <perex@perex.cz> - 1.2.9-1
* Updated to 1.2.9

* Wed Jan 18 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.8-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Mon Oct 24 2022 Jaroslav Kysela <perex@perex.cz> - 1.2.8-1
* Updated to 1.2.8

* Wed Jul 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Tue May 31 2022 Jaroslav Kysela <perex@perex.cz> - 1.2.7-1
* Updated to 1.2.7

* Wed Jan 19 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Mon Dec  6 2021 Jaroslav Kysela <perex@perex.cz> - 1.2.6-1
* Updated to 1.2.6

* Wed Jul 21 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.5.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Mon Jun 14 2021 Jaroslav Kysela <perex@perex.cz> - 1.2.5.1-1
* Updated to 1.2.5.1

* Thu Jun  3 2021 Jaroslav Kysela <perex@perex.cz> - 1.2.5-3
* Fixes for 1.2.5 (alsactl)

* Mon May 31 2021 Jaroslav Kysela <perex@perex.cz> - 1.2.5-2
* Updated to 1.2.5

* Tue Mar 02 2021 Zbigniew Jędrzejewski-Szmek <zbyszek@in.waw.pl> - 1.2.4-3
- Rebuilt for updated systemd-rpm-macros
  See https://pagure.io/fesco/issue/2583.

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Thu Oct 15 2020 Jaroslav Kysela <perex@perex.cz> - 1.2.4-1
* Updated to 1.2.4

* Fri Jul 31 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.3-6
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.3-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Fri Jul  3 2020 Jaroslav Kysela <perex@perex.cz> - 1.2.3-4
* Fix the .spec (changelog0)

* Sun Jun  7 2020 Jaroslav Kysela <perex@perex.cz> - 1.2.3-3
* Updated to 1.2.3

* Wed Feb 19 2020 Jaroslav Kysela <perex@perex.cz> - 1.2.2-1
* Updated to 1.2.2

* Sun Feb  9 2020 Jaroslav Kysela <perex@perex.cz> - 1.2.1-6
- UCM and topology fixes

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Fri Nov 15 2019 Jaroslav Kysela <perex@perex.cz> - 1.2.1-4
- Updated to 1.2.1

* Wed Jul 24 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.9-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri May 10 2019 Jaroslav Kysela <perex@perex.cz> - 1.1.9-1
- Updated to 1.1.9

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.8-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Mon Jan  7 2019 Jaroslav Kysela <perex@perex.cz> - 1.1.8-2
- Updated to 1.1.8

* Tue Oct 16 2018 Jaroslav Kysela <perex@perex.cz> - 1.1.7-2
- Moved use case manager utility to alsa-ucm-utils
- Moved topology utility to alsa-topology-utils
- Updated to 1.1.7

* Fri Sep 07 2018 Jaroslav Kysela <perex@perex.cz> - 1.1.6-5
- Added udev rules for PAZ00

* Thu Jul 12 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.6-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Tue Apr 03 2018 Jaroslav Kysela <perex@perex.cz> - 1.1.6-1
- Updated to 1.1.6

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Tue Nov 14 2017 Jaroslav Kysela <perex@perex.cz> - 1.1.5-1
- Updated to 1.1.5

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.4-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Tue May 16 2017 Jaroslav Kysela <perex@perex.cz> - 1.1.4-1
- Updated to 1.1.4

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Tue Sep 20 2016 Jaroslav Kysela <perex@perex.cz> - 1.1.3-1
- Updated to 1.1.3

* Tue Aug  2 2016 Jaroslav Kysela <perex@perex.cz> - 1.1.2-1
- Updated to 1.1.2

* Thu Mar 31 2016 Jaroslav Kysela <perex@perex.cz> - 1.1.1-1
- Updated to 1.1.1
- Renamed bat to alsabat (according 1.1.1)

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Tue Oct 27 2015 Jaroslav Kysela <perex@perex.cz> - 1.1.0-1
- Updated to 1.1.0
- update systemd unit configuration files
- create alsa-utils-bat package

* Tue Jun 16 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.29-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Feb 26 2015 Jaroslav Kysela <perex@perex.cz> - 1.0.29-1
- Updated to 1.0.29

* Fri Aug 15 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.28-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Thu Jul 24 2014 Peter Robinson <pbrobinson@fedoraproject.org> 1.0.28-1
- Update to 1.0.28

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.27.2-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Fri Jan 10 2014 Jaroslav Kysela <jkysela@redhat.com> - 1.0.27.2-5
- Fix hardering build - rhbz#1008385
- Add systemd scripts for alsa-state.service - rhbz#856654

* Sun Dec 29 2013 Jaroslav Kysela <jkysela@redhat.com> - 1.0.27.2-4
- Fix alsactl crash issue - rhbz#994832

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.27.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Fri Jul 19 2013 Jaroslav Kysela <jkysela@redhat.com> - 1.0.27.2-2
- Fix alsa-state.service (rkill -> kill) - rhbz#986141

* Wed Jul 10 2013 Jaroslav Kysela <jkysela@redhat.com> - 1.0.27.2-1
- Updated to 1.0.27.2

* Tue May 21 2013 Jaroslav Kysela <jkysela@redhat.com> - 1.0.27.1-1
- Updated to 1.0.27.1
- Updated alsa-info.sh to 0.4.61
- Remove dependency on the dialog package (it is optional for alsa-info.sh)

* Mon Apr 15 2013 Jaroslav Kysela <jkysela@redhat.com> - 1.0.27-2
- Fix the new udev rules (missing GOTO) - bug#951750
- Fix the string size in alsactl (underflow)

* Fri Apr 12 2013 Jaroslav Kysela <jkysela@redhat.com> - 1.0.27-1
- Updated to 1.0.27, activated the alsactl daemon mode
- Updated alsa-info.sh to 0.4.61

* Wed Feb 13 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.26-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Sep  6 2012 Jaroslav Kysela <jkysela@redhat.com> - 1.0.26-1
- Updated to 1.0.26

* Wed Jul 18 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.25-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Tue Apr  3 2012 Peter Robinson <pbrobinson@fedoraproject.org> - 1.0.25-8
- bump Release to be larger than F-16

* Tue Jan 31 2012 Jaroslav Kysela <perex@perex.cz> 1.0.25-1
- update to 1.0.25 final

* Wed Jan 25 2012 Harald Hoyer <harald@redhat.com> 1.0.24.1-8
- install everything in /usr
  https://fedoraproject.org/wiki/Features/UsrMove

* Thu Jan 12 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.24.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Fri Jan  6 2012 Lennart Poettering <lpoetter@redhat.com> - 1.0.24.1-6
- Always build with systemd support

* Fri Jan  6 2012 Lennart Poettering <lpoetter@redhat.com> - 1.0.24.1-5
- When installing the Fedora service files make sure to override the
  actual service files with them instead of the symlinks to them
- Drop StandardOutput=syslog since that is the default now and we
  don't want to needlessly override the default

* Mon Oct 31 2011 Bastien Nocera <bnocera@redhat.com> 1.0.24.1-4
- Add patch to unmute MacBookAir4,1 speakers

* Mon Feb 07 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.24.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Fri Jan 28 2011 Jaroslav Kysela <jkysela@redhat.com> 1.0.24.1-2
- add missing systemd files, add dependency on systemd-units
- use own udev rule file for /lib/udev/rules.d
- create /var/lib/alsa directory for asound.state

* Fri Jan 28 2011 Jaroslav Kysela <jkysela@redhat.com> 1.0.24.1-1
- updated to 1.0.24.1 final (new automake/autoconf)

* Fri Jan 28 2011 Jaroslav Kysela <jkysela@redhat.com> 1.0.24-1
- updated to 1.0.24 final
- updated alsa-info.sh script to 0.4.60

* Thu Jan 13 2011 Ville Skyttä <ville.skytta@iki.fi> - 1.0.23-4
- Fix alsaunmute man page permissions, let rpmbuild compress it.

* Mon Jun 28 2010 Jaroslav Kysela <jkysela@redhat.com> 1.0.23-3
- add requires line (bug#526492) for specific alsa-lib package
- add requires line for dialog package (bug#561988)
- added man page for alsaunmute (bug#526174)
- updated alsa-info.sh script to 0.4.59

* Mon Jun 28 2010 Jaroslav Kysela <jkysela@redhat.com> 1.0.23-1
- updated to 1.0.23 final

* Sun Apr 18 2010 Thomas Spura <tomspur@fedoraproject.org> 1.0.22-2
- don't own %%{_datadir}/sounds (#569425)

* Fri Jan  1 2010 Jaroslav Kysela <jkysela@redhat.com> 1.0.22-1
- updated to 1.0.22 final

* Thu Sep  3 2009 Jaroslav Kysela <jkysela@redhat.com> 1.0.21-2
- added missing patch file

* Thu Sep  3 2009 Jaroslav Kysela <jkysela@redhat.com> 1.0.21-1
- updated to 1.0.21 final
- updated alsa-info.sh script to 0.4.58

* Fri Jul 24 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.20-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Fri May 15 2009 Jaroslav Kysela <jkysela@redhat.com> 1.0.20-3
- added missing Headphone Volume patch

* Fri May 15 2009 Jaroslav Kysela <jkysela@redhat.com> 1.0.20-2
- fixed Headphone Volume issue (bz#500956)

* Wed May 06 2009 Jaroslav Kysela <jkysela@redhat.com> 1.0.20-1
- updated to 1.0.20 final
- updated alsa-info.sh script to 0.4.56

* Mon Feb 23 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.19-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Mon Feb 09 2009 Jaroslav Kysela <jkysela@redhat.com> 1.0.19-3
- fixed volume initialization for some HDA codecs
- updated alsa-info.sh to 0.4.54

* Wed Feb 04 2009 Jaroslav Kysela <jkysela@redhat.com> 1.0.19-2
- add dir directive for /lib/alsa and /lib/alsa/init directories (bz#483324)

* Tue Jan 20 2009 Jaroslav Kysela <jkysela@redhat.com> 1.0.19-1
- updated to 1.0.19 final

* Tue Nov 04 2008 Jaroslav Kysela <jkysela@redhat.com> 1.0.18-5
- fixed building

* Tue Nov 04 2008 Jaroslav Kysela <jkysela@redhat.com> 1.0.18-4
- updated to 1.0.18 final
- updated alsa-info.sh script

* Thu Sep 18 2008 Jaroslav Kysela <jkysela@redhat.com> 1.0.18-3.rc3
- fixed alsa-info.sh link

* Thu Sep 18 2008 Jaroslav Kysela <jkysela@redhat.com> 1.0.18-2.rc3
- fixed /lib/alsa/init path for x86_64 (was /lib64/alsa/init)
- added /etc/alsa/asound.state -> /etc/asound.state shift to post section
- fix udev rules (ommited /dev/ prefix for the alsactl utility)
- added --ignore option for alsactl (added also to upstream)

* Thu Sep 11 2008 Jaroslav Kysela <jkysela@redhat.com> 1.0.18-1.rc3
- updated to 1.0.18rc3
- updated alsa-info.sh script to 0.4.51
- removed alsacard utility
- removed salsa utility
- changed alsaunmute to use 'alsactl init' now
- updated ALSA udevd rules to use alsactl
- moved /etc/alsa/asound.state back to /etc/asound.state

* Mon Jul 21 2008 Jaroslav Kysela <jkysela@redhat.com> 1.0.17-1
- updated to 1.0.17 final
- updated alsa-info.sh script to 0.4.48

* Mon Apr 28 2008 Martin Stransky <stransky@redhat.com> 1.0.16-3
- Added alsa-info.sh script to /usr/bin/alsa-info

* Tue Feb 19 2008 Fedora Release Engineering <rel-eng@fedoraproject.org> - 1.0.16-2
- Autorebuild for GCC 4.3

* Mon Feb 18 2008 Martin Stransky <stransky@redhat.com> 1.0.16-1
- updated to 1.0.16 final

* Tue Jan 15 2008 Mikel Ward <mikel@mikelward.com>
- add salsa man page

* Mon Oct 29 2007 Martin Stransky <stransky@redhat.com> 1.0.15-1
- updated to 1.0.15 final

* Mon Oct 1 2007 Martin Stransky <stransky@redhat.com> 1.0.15-0.4.rc1
- moved saved volume settings back to /etc/alsa
  (per discussion at #293301)

* Mon Sep 24 2007 Martin Stransky <stransky@redhat.com> 1.0.15-0.3.rc1
- fixed #303151 - wrong salsa dir in /etc/udev/rules.d/90-alsa.rules

* Thu Sep 20 2007 Matthias Saou <http://freshrpms.net/> 1.0.15-0.2.rc1
- Update License field.
- Mark udev rule as config.
- Use find_lang macro again to include translations (why was it removed?).

* Wed Sep 19 2007 Martin Stransky <stransky@redhat.com> 1.0.15-0.1.rc1
- new upstream
- moved saved volume settings to /var/lib (#293301)
- patched alsactl for that (#255421)

* Thu Aug 16 2007 Martin Stransky <stransky@redhat.com> 1.0.14-2
- added an entry to alsaunmute for HP xw4550 (#252171)

* Wed Jul 25 2007 Martin Stransky <stransky@redhat.com> 1.0.14-1
- release bump

* Thu Jun 7 2007 Martin Stransky <stransky@redhat.com> 1.0.14-0.8
- new upstream

* Wed May 30 2007 Martin Stransky <stransky@redhat.com> 1.0.14-0.7.rc2
- updated alsanumute for Siemens Lifebook S7020 (#241639)
- unmute Master Mono for all drivers

* Wed May 2 2007 Martin Stransky <stransky@redhat.com> 1.0.14-0.6.rc2
- added fix for #238442 (unmute Mono channel for w4550,
  xw4600, xw6600, and xw8600)

* Wed Apr 18 2007 Martin Stransky <stransky@redhat.com> 1.0.14-0.5.rc2
- added more funcionality to salsa (save/load sound settings),
  moved volume settings to /etc/alsa/

* Tue Apr 10 2007 Martin Stransky <stransky@redhat.com> 1.0.14-0.4.rc2
- added support for large files
- minor fix in alsaunmute
- fixed #209239 - alsaconf: Stale language-dependent files
- fixed #233765 - alsa-utils : unowned directories

* Fri Jan 19 2007 Martin Stransky <stransky@redhat.com> 1.0.14-0.3.rc2
- new upstream

* Wed Jan 10 2007 Martin Stransky <stransky@redhat.com> 1.0.14-0.2.rc1
- added a config line for hda-intel driver

* Mon Dec 11 2006 Martin Stransky <stransky@redhat.com> 1.0.14-0.1.rc1
- new upstream

* Mon Oct 2 2006 Martin Stransky <stransky@redhat.com> 1.0.12-3
- fix for #207384 - Audio test fails during firstboot

* Fri Aug 25 2006 Martin Stransky <stransky@redhat.com> 1.0.12-2
- new upstream

* Mon Aug 07 2006 Martin Stransky <stransky@redhat.com> 1.0.12-1.rc2
- new upstream

* Thu Jul 20 2006 Martin Stransky <stransky@redhat.com> 1.0.12-1.rc1
- new upstream

* Wed Jul 12 2006 Jesse Keating <jkeating@redhat.com> - sh: line 0: fg: no job control
- rebuild

* Tue May 30 2006 Martin Stransky <stransky@redhat.com> 1.0.11-7
- new upstream

* Wed May 3  2006 Martin Stransky <stransky@redhat.com> 1.0.11-6.rc2
- removed HW specific switch - it should be set by driver

* Thu Apr 6  2006 Martin Stransky <stransky@redhat.com> 1.0.11-5.rc2
- fixed rules file (#186494)
- fixed Audigi mixer switch (#187807)

* Mon Feb 20 2006 Martin Stransky <stransky@redhat.com> 1.0.11-3.rc2
- removed autoreconf

* Fri Feb 10 2006 Jesse Keating <jkeating@redhat.com> - 1.0.11-2.rc2.2
- bump again for double-long bug on ppc(64)

* Tue Feb 07 2006 Jesse Keating <jkeating@redhat.com> - 1.0.11-2.rc2.1
- rebuilt for new gcc4.1 snapshot and glibc changes

* Wed Jan 25 2006 Martin Stransky <stransky@redhat.com> 1.0.11-2.rc2
- added volume option to alsaunmute utility (for s-c-s)

* Thu Jan 12 2006 Martin Stransky <stransky@redhat.com> 1.0.11-1.rc2
- new upstream

* Fri Dec 09 2005 Jesse Keating <jkeating@redhat.com>
- rebuilt

* Thu Nov 24 2005 Martin Stransky <stransky@redhat.com> 1.0.10rf-1
- new upstream version
- added alias for snd-azx

* Wed Nov 9 2005 Martin Stransky <stransky@redhat.com> 1.0.10rc1-2
- fix for #169292 - RHEL4U2 xw4300 IntelHD internal speakers muted by default

* Tue Sep 27 2005 Martin Stransky <stransky@redhat.com> 1.0.10rc1-1
- new upstream version

* Tue Aug 23 2005 Martin Stransky <stransky@redhat.com> 1.0.9-5
- unmute External Amplifier by default (#166153)

* Wed Jul 13 2005 Bill Nottingham <notting@redhat.com> 1.0.9-4
- migrate the alsa restore program to a udev rule, not a dev.d program
- conflict with appropriate udev
- move alsaunmute, alsacard to /bin

* Mon Jul 11 2005 Martin Stransky <stransky@redhat.com> 1.0.9-3
- New alsaunmute utility
- Add autoconf to BuildRequires (#162483)

* Thu Jun 16 2005 Martin Stransky <stransky@redhat.com> 1.0.9-2
- New upstream version

* Mon May 30 2005 Martin Stransky <stransky@redhat.com> 1.0.9-1
- New upstream version.
- moved alsacard utility from alsa-lib to alsa-tools

* Mon May 16 2005 Bill Nottingham <notting@redhat.com> 1.0.9rc2-2
- make sure 'Wave' playback channel isn't muted (#157850)

* Mon Apr 25 2005 Martin Stransky <stransky@redhat.com> 1.0.9rc2-1
- New upstream version
- add %%find_lang macro (#155719)

* Fri Apr 1 2005 Bill Nottingham <notting@redhat.com> 1.0.8-4
- replace the dev.d script with a program that calls alsactl to
  restore the volume if there is a saved config, and just unmutes
  the playback channels if there isn't one (#132575)

* Mon Mar 7 2005 Martin Stransky <stransky@redhat.com>
- rebuilt

* Wed Feb 16 2005 Martin Stransky <stransky@redhat.com> 1.0.8-2
- fix #148011 (add gettext-devel to BuildRequires)
- add $RPM_OPT_FLAGS to CFLAGS

* Wed Jan 26 2005 Martin Stransky <stransky@redhat.com> 1.0.8-1
- update to 1.0.8
- temporarily removed alsa-lauch.patch

* Sat Jan 08 2005 Colin Walters <walters@redhat.com> 1.0.7-2
- New patch alsa-utils-1.0.7-alsa-launch.patch, adds the
  alsa-launch command.
- New source file xinit-alsa-launch.sh, integrates alsa-launch
  into X startup
- BR xorg-x11-devel

* Thu Jan 06 2005 Colin Walters <walters@redhat.com> 1.0.7-1
- New upstream version

* Tue Oct 19 2004 Bill Nottingham <notting@redhat.com> 1.0.6-3
- tweak dev.d sound restore script (#133535, revisited)

* Thu Oct 14 2004 Bill Nottingham <notting@redhat.com> 1.0.6-2
- move alsactl to /sbin
- include a dev.d script for mixer restoring (#133535)

* Mon Aug 30 2004 Bill Nottingham <notting@redhat.com> 1.0.6-1
- update to 1.0.6

* Fri Jul  2 2004 Bill Nottingham <notting@redhat.com> 1.0.5-1
- update to 1.0.5

* Tue Jun 15 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Thu Mar 11 2004 Bill Nottingham <notting@redhat.com> 1.0.3-1
- update to 1.0.3

* Fri Feb 13 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Wed Jan 28 2004 Bill Nottingham <notting@redhat.com> 1.0.2-1
- update to 1.0.2

* Wed Dec 17 2003 Bill Nottingham <notting@redhat.com> 1.0.0-0.rc2
- import fedora.us RPM, take out save-alsamixer & alsaconf for now

* Thu Dec 11 2003 Thorsten Leemhuis <fedora[AT]leemhuis.info> 1.0.0-0.fdr.0.4.rc2
- rename alsamixer-saver save-alsamixer

* Mon Dec  8 2003 Thorsten Leemhuis <fedora[AT]leemhuis.info> 1.0.0-0.fdr.0.3.rc2
- Integrate Michael Schwendt's script alsamixer-saver; Still not quite sure if
  this script is the right way -- but mine didn't work...

* Sat Dec  6 2003 Thorsten Leemhuis <fedora[AT]leemhuis.info> 1.0.0-0.fdr.0.2.rc2
- Update to 1.0.0rc2
- added alsamixer Script -- stores settings on shutdown, does nothing on startup
- some minor corrections in spec-file style

* Wed Dec  3 2003 Thorsten Leemhuis <fedora[AT]leemhuis.info> 1.0.0-0.fdr.0.1.rc1
- Update to 1.0.0rc1

* Wed Aug  6 2003 Dams <anvil[AT]livna.org> 0:utils-0.fdr.1
- Initial build.
