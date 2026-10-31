%global pkg_description %{expand:
This Python library handles Portable Symmetric Key Container (PSKC)
files as defined in RFC 6030. PSKC files are used to transport and
provision symmetric keys (seed files) to different types of crypto
modules, commonly one-time password tokens or other authentication
devices.
}

%global cgiturl https://arthurdejong.org/
%global cgitname python_pskc

Name:           python-pskc
Version:        1.4
Release:        %autorelease
Summary:        Python library for handling PSKC files
License:        LGPL-2.1-or-later

BuildArch:      noarch

URL:            %{cgiturl}%{name}/
Source0:        %{cgiturl}%{name}/%{cgitname}-%{version}.tar.gz
Source1:        %{cgiturl}%{name}/%{cgitname}-%{version}.tar.gz.asc
Source2:        %{cgiturl}arthur.asc

BuildRequires:  gpgverify
BuildRequires:  %{py3_dist pytest pytest-timeout}

BuildSystem:    pyproject
BuildOption(install): -l pskc

%description
%{pkg_description}

%package -n python3-pskc
Summary:        Python library for handling PSKC files

%description -n python3-pskc
%{pkg_description}

%prep
%{gpgverify} --data=%{SOURCE0} --signature=%{SOURCE1} --keyring=%{SOURCE2}
%autosetup -n %{cgitname}-%{version}

# Fedora does not run coverage tools during %check
sed -i 's/--cov[^ ]*//g' setup.cfg

%check
%pytest \
  --ignore=tests/test_signature.doctest \
  --ignore=tests/test_draft_ietf_keyprov_pskc_02.doctest \
  --ignore=tests/test_draft_keyprov.doctest \
  --ignore=tests/test_feitian.doctest \
  --ignore=tests/test_misc.doctest \
  --ignore=tests/test_rfc6030.doctest \
  --ignore=tests/test_yubico.doctest

%files -n python3-pskc -f %{pyproject_files}
%doc README NEWS
%{_bindir}/csv2pskc
%{_bindir}/pskc2csv
%{_bindir}/pskc2pskc

%changelog
%autochangelog
