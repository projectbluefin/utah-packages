Name:		b43-openfwwf
Version:	5.2
Release:	%autorelease
Summary:	Open firmware for some Broadcom 43xx series WLAN chips
License:	GPL-2.0-only
URL:		http://netweb.ing.unibs.it/openfwwf/
Source0:	http://netweb.ing.unibs.it/openfwwf/firmware/openfwwf-%{version}.tar.gz
Source1:	README.openfwwf
Source2:	openfwwf.conf
BuildArch:	noarch
BuildRequires:	b43-tools
BuildRequires:	gcc-c++
BuildRequires:	make
Requires:	module-init-tools
Requires:	udev


%description
Open firmware for some Broadcom 43xx series WLAN chips.
Currently supported models are 4306, 4311(rev1), 4318 and 4320.


%prep
%autosetup -p1 -n openfwwf-%{version}
sed -i s/"-o 0 -g 0"// Makefile
install -p -m 0644 %{SOURCE1} .
install -p -m 0644 %{SOURCE2} .

%build
%make_build


%install
make install PREFIX=%{buildroot}/lib/firmware/b43-open
install -p -D -m 0644 openfwwf.conf %{buildroot}%{_prefix}/lib/modprobe.d/openfwwf.conf


%files
%license COPYING LICENSE
%doc README.openfwwf
%dir /lib/firmware/b43-open
/lib/firmware/b43-open/b0g0bsinitvals5.fw
/lib/firmware/b43-open/b0g0initvals5.fw
/lib/firmware/b43-open/ucode5.fw
%{_prefix}/lib/modprobe.d/openfwwf.conf


%changelog
%autochangelog
