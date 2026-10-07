# doesn't make sense to install a polkit configuration inside a Flatpak
%if 0%{?flatpak}
%global with_polkit 0
%else
%global with_polkit 1
%endif

Name:           pcsc-lite
Version:        2.5.2
Release:        %autorelease
Summary:        PC/SC Lite smart card framework and applications

License:        BSD-3-Clause AND BSD-2-Clause AND GPL-3.0-or-later
URL:            https://pcsclite.apdu.fr/
Source0:        https://pcsclite.apdu.fr/files/%{name}-%{version}.tar.xz
Source1:        https://pcsclite.apdu.fr/files/%{name}-%{version}.tar.xz.asc
Source2:        gpgkey-F5E11B9FFE911146F41D953D78A1B4DFE8F9C57E.gpg

BuildRequires:  doxygen
BuildRequires:  graphviz
BuildRequires:  systemd
BuildRequires:  systemd-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  perl-podlators
%if %{with_polkit}
BuildRequires:  polkit-devel
%endif
BuildRequires:  gettext-devel
BuildRequires:  gnupg2
BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  python3-devel
BuildRequires:  flex
BuildRequires: libappstream-glib

Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
Requires:       pcsc-ifd-handler
Requires:       %{name}-libs = %{version}-%{release}
%if %{with_polkit}
Requires:       polkit
%endif
Requires:       python3
Recommends:     pcsc-lite-ccid
# This is bundled in upstream without simple way to remove
Provides:       bundled(simclist) = 1.6


%description
The purpose of PC/SC Lite is to provide a Windows(R) SCard interface
in a very small form factor for communicating to smartcards and
readers.  PC/SC Lite uses the same winscard API as used under
Windows(R).  This package includes the PC/SC Lite daemon, a resource
manager that coordinates communications with smart card readers and
smart cards that are connected to the system, as well as other command
line tools.

%package        libs
Summary:        PC/SC Lite libraries

%description    libs
PC/SC Lite libraries.

%package        devel
Summary:        PC/SC Lite development files
Requires:       %{name}-libs = %{version}-%{release}

%description    devel
PC/SC Lite development files.

%package        doc
Summary:        PC/SC Lite developer documentation
BuildArch:      noarch
Requires:       %{name}-libs = %{version}-%{release}

%description    doc
%{summary}.


%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'

%autosetup

# Convert to utf-8
for file in ChangeLog; do
    iconv -f ISO-8859-1 -t UTF-8 -o $file.new $file && \
    touch -r $file $file.new && \
    mv $file.new $file
done


%build
%meson -Dlibsystemd=true \
    -Dsystemdunit=system \
    -Dserial=true \
    -Dusbdropdir=%{_libdir}/pcsc/drivers \
%if ! %{with_polkit}
   -Dpolkit=false
%else
   -Dpolkit=true
%endif
%meson_build
%meson_build doc


%install
%meson_install

# Create empty directories
mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/reader.conf.d
mkdir -p $RPM_BUILD_ROOT%{_libdir}/pcsc/drivers
mkdir -p $RPM_BUILD_ROOT%{_localstatedir}/run/pcscd

appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/*.metainfo.xml

%post
%systemd_post pcscd.socket pcscd.service
# If install, test if pcscd socket is enabled.
# If enabled, then attempt to start it. This will silently fail
# in chroots or other environments where services aren't expected
# to be started.
if [ $1 -eq 1 ] ; then
   if systemctl -q is-enabled pcscd.socket > /dev/null 2>&1 ; then
      systemctl start pcscd.socket > /dev/null 2>&1 || :
   fi
fi

%preun
%systemd_preun pcscd.socket pcscd.service

%postun
%systemd_postun_with_restart pcscd.socket pcscd.service

%ldconfig_scriptlets libs


%files
%doc AUTHORS ChangeLog HELP README SECURITY
%doc doc/README.polkit
%doc src/spy/setup_spy.sh
%dir %{_sysconfdir}/reader.conf.d/
%{_unitdir}/pcscd.service
%{_unitdir}/pcscd.socket
%{_sbindir}/pcscd
%dir %{_libdir}/pcsc/
%dir %{_libdir}/pcsc/drivers/
%{_mandir}/man5/reader.conf.5*
%{_mandir}/man8/pcscd.8*
%ghost %dir %{_localstatedir}/run/pcscd/
%if %{with_polkit}
%dir %{_datadir}/polkit-1/
%dir %{_datadir}/polkit-1/actions/
%{_datadir}/polkit-1/actions/org.debian.pcsc-lite.policy
%endif
%{_metainfodir}/fr.apdu.pcsclite.metainfo.xml
%{_sysconfdir}/default/pcscd

%files libs
%license COPYING
%{_libdir}/libpcsclite.so.*
%{_libdir}/libpcsclite_real.so.*
%{_sysusersdir}/pcscd-sysusers.conf

%files devel
%{_bindir}/pcsc-spy
%{_includedir}/PCSC/
%{_libdir}/libpcsclite.so
%{_libdir}/libpcsclite_real.so
%{_libdir}/libpcscspy.so*
%dir %{_libdir}/pkgconfig/
%{_libdir}/pkgconfig/libpcsclite.pc
%{_mandir}/man1/pcsc-spy.1*

%files doc
%doc %{_vpath_builddir}/doc/api/ doc/example/pcsc_demo.c


%changelog
%autochangelog
