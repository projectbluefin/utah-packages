Name:           b43-fwcutter
Version:        021
Release:        %autorelease
Summary:        Firmware extraction tool for Broadcom wireless driver
License:        BSD-2-Clause
URL:            https://bues.ch/b43/fwcutter/
Source0:        https://bues.ch/b43/fwcutter/%{name}-%{version}.tar.xz
Source1:        https://bues.ch/b43/fwcutter/%{name}-%{version}.tar.xz.asc
# gpg --no-default-keyring --keyring ./keyring.gpg --keyserver keyserver.ubuntu.com --recv-key 757FAB7CED1814AE15B4836E5FB027474203454C
# gpg --no-default-keyring --keyring ./keyring.gpg  --output 757FAB7CED1814AE15B4836E5FB027474203454C.gpg --export --armor
Source2:        757FAB7CED1814AE15B4836E5FB027474203454C.gpg
Source100:      README.too
BuildRequires:  gcc
BuildRequires:  gnupg2
BuildRequires:  make

%description
This package contains the 'b43-fwcutter' tool which is used to
extract firmware for the Broadcom network devices.

See the README.too file shipped in the package's documentation for
instructions on using this tool.

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -p2

cp %{SOURCE100} .

%build
CFLAGS="$RPM_OPT_FLAGS" make

%install
mkdir -p $RPM_BUILD_ROOT%{_bindir}
install -m0755 b43-fwcutter $RPM_BUILD_ROOT%{_bindir}/b43-fwcutter
mkdir -p $RPM_BUILD_ROOT%{_mandir}/man1
install -m0644 b43-fwcutter.1 $RPM_BUILD_ROOT%{_mandir}/man1

%files
%{_bindir}/b43-fwcutter
%{_mandir}/man1/*
%license COPYING
%doc README README.too

%changelog
%autochangelog
