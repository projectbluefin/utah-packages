Name:           pyscard
Version:        2.2.2
Release:        %autorelease
Summary:        A framework for building smart card aware applications in Python


# The entire source code is LGPLv2+ except for ClassLoader.py (Python),
# and Synchronization.py, Observer.py (CC-BY-SA 3.0), according to
# http://sourceforge.net/p/pyscard/code/619/

# Automatically converted from old format: LGPLv2+ - review is highly recommended.
License:        LicenseRef-Callaway-LGPLv2+
URL:            https://github.com/LudovicRousseau/pyscard
Source0:        https://github.com/LudovicRousseau/pyscard/archive/%{version}/%{name}-%{version}.tar.gz
# Upstream commit for SWIG 4.4 support
Patch:          https://github.com/LudovicRousseau/pyscard/commit/54ef7f2ca636b83657506030e6bfbdc335f65bb5.patch

BuildRequires:  gcc
BuildRequires:  pcsc-lite-devel
BuildRequires:  swig >= 1.3.31
ExcludeArch:    %{ix86}

%description
The pyscard smartcard library is a framework for building smart card aware
applications in Python. The smartcard module is built on top of the PCSC API
Python wrapper module.

%package -n python%{python3_pkgversion}-%{name}
Summary:        A framework for building smart card aware applications in Python
BuildRequires:  python%{python3_pkgversion}-devel
Requires:       pcsc-lite

%description -n python%{python3_pkgversion}-%{name}
The pyscard smartcard library is a framework for building smart card aware
applications in Python. The smartcard module is built on top of the PCSC API
Python wrapper module.

This is the python3 package.

%prep
%autosetup -p1
sed -i 's/,"swig"//' pyproject.toml

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l smartcard
ls -l %{buildroot}%{python3_sitearch}/smartcard/scard/*.so
chmod 755 %{buildroot}%{python3_sitearch}/smartcard/scard/*.so


%files -n python%{python3_pkgversion}-%{name} -f %{pyproject_files}
%doc ACKS README.md
%doc src/smartcard/doc/*

%changelog
%autochangelog
