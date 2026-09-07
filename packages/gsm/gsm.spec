# on update also change soname in the gsm-makefile.patch
%global ver_major 1
%global ver_minor 0
%global ver_patch 24

Name:           gsm
Version:        1.0.24
Release:        %autorelease
Summary:        Shared libraries for GSM speech compressor

License:        tu-berlin-2.0
URL:            https://www.quut.com/gsm/
Source:         https://www.quut.com/gsm/%{name}-%{version}.tar.gz
Patch0:         %{name}-makefile.patch
Patch1:         %{name}-warnings.patch
BuildRequires:  gcc
BuildRequires:  make

%global srcver %{ver_major}.%{ver_minor}-pl%{ver_patch}

%description
Contains runtime shared libraries for libgsm, an implementation of
the European GSM 06.10 provisional standard for full-rate speech
transcoding, prI-ETS 300 036, which uses RPE/LTP (residual pulse
excitation/long term prediction) coding at 13 kbit/s.

GSM 06.10 compresses frames of 162 13-bit samples (8 kHz sampling
rate, i.e. a frame rate of 50 Hz) into 260 bits; for compatibility
with typical UNIX applications, our implementation turns frames of 160
16-bit linear samples into 33-byte frames (1650 Bytes/s).
The quality of the algorithm is good enough for reliable speaker
recognition; even music often survives transcoding in recognizable
form (given the bandwidth limitations of 8 kHz sampling rate).

The interfaces offered are a front end modelled after compress(1), and
a library API.  Compression and decompression run faster than realtime
on most SPARCstations.  The implementation has been verified against the
ETSI standard test patterns.

%package        tools
Summary:        GSM speech compressor tools
Requires:       %{name}%{_isa} = %{version}-%{release}

%description    tools
Contains command line utilities for libgsm, an implementation of
the European GSM 06.10 provisional standard for full-rate speech
transcoding, prI-ETS 300 036, which uses RPE/LTP (residual pulse
excitation/long term prediction) coding at 13 kbit/s.

%package        devel
Summary:        Header files and development libraries for libgsm
Requires:       %{name}%{_isa} = %{version}-%{release}

%description    devel
Contains header files and development libraries for libgsm, an
implementation of the European GSM 06.10 provisional standard for
full-rate speech transcoding, prI-ETS 300 036, which uses RPE/LTP
(residual pulse excitation/long term prediction) coding at 13 kbit/s.

%prep
%setup -n gsm-%{srcver} -q
%patch -P0 -p1 -b .mk
%patch -P1 -p1 -b .warn

%build
export LDFLAGS="%{?__global_ldflags}"
%make_build all SO_MAJOR=%{ver_major} SO_MINOR=%{ver_minor} SO_PATCH=%{ver_patch}

%install
export LDFLAGS="%{?__global_ldflags}"
mkdir -p %{buildroot}{%{_bindir},%{_includedir}/gsm,%{_libdir},%{_mandir}/{man1,man3}}

%make_install \
	INSTALL_ROOT=%{buildroot}%{_prefix} \
	GSM_INSTALL_INC=%{buildroot}%{_includedir}/gsm \
	GSM_INSTALL_LIB=%{buildroot}%{_libdir} \
	SO_MAJOR=%{ver_major} SO_MINOR=%{ver_minor} SO_PATCH=%{ver_patch}

# some apps look for this in /usr/include
ln -s gsm/gsm.h %{buildroot}%{_includedir}

echo ".so toast.1" > %{buildroot}%{_mandir}/man1/tcat.1
echo ".so toast.1" > %{buildroot}%{_mandir}/man1/untoast.1

%check
# This is to ensure that the patch creates the proper library version.
[ -f %{buildroot}%{_libdir}/libgsm.so.%{version} ]
export LDFLAGS="%{?__global_ldflags}"
%{__make} addtst

%files
%license COPYRIGHT
%doc ChangeLog MACHINES README
%{_libdir}/libgsm.so.%{ver_major}{,.*}

%files tools
%{_bindir}/tcat
%{_bindir}/toast
%{_bindir}/untoast
%{_mandir}/man1/tcat.1*
%{_mandir}/man1/toast.1*
%{_mandir}/man1/untoast.1*

%files devel
%dir %{_includedir}/gsm
%{_includedir}/gsm/gsm.h
%{_includedir}/gsm.h
%{_libdir}/libgsm.so
%{_mandir}/man3/gsm.3*
%{_mandir}/man3/gsm_explode.3*
%{_mandir}/man3/gsm_option.3*
%{_mandir}/man3/gsm_print.3*

%changelog
%autochangelog
