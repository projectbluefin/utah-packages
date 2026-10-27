%bcond tests 1

Name:           bash-color-prompt
Version:        0.96.2
Release:        %autorelease
Summary:        Bash Color Prompt with customization

License:        GPL-3.0-or-later
URL:            https://github.com/juhp/bash-color-prompt
Source0:        https://github.com/juhp/bash-color-prompt/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  perl
%if %{with tests}
BuildRequires:  bats
#BuildRequires:  hostname
%endif

%description
A flexible customizable Bash prompt framework.


%prep
%setup -q


%build
sed -i -e "s/@BASHCOLORVERSION@/%{version}/" bash-color-prompt.sh

%global profilesh profile.d/bcp-fedora.sh
%global bcp_datadir %{_datadir}/bash-color-prompt

sed -i -e 's!@BCP_LIBRARY@!%{bcp_datadir}/bcp.sh!' %{profilesh}

source ./bash-color-prompt.sh
bcp_static _bcp_compat_layout
export PS1
perl -i -pe 's/\@BCP_STATIC_PS1\@/$ENV{PS1}/' %{profilesh}
bcp_static _bcp_compat_layout 1
perl -i -pe 's/\@BCP_STATIC_PS1_BOLD\@/$ENV{PS1}/' %{profilesh}


%install
%global profiledir %{_sysconfdir}/profile.d
mkdir -p %{buildroot}%{profiledir}
install -m 644 %{profilesh} %{buildroot}%{profiledir}/bash-color-prompt.sh
mkdir -p %{buildroot}%{bcp_datadir}
install -m 644 bash-color-prompt.sh %{buildroot}%{bcp_datadir}/bcp.sh


%check
%if %{with tests}
bats --timing --gather-test-outputs-in logs tests
%endif


%files
%license COPYING
%doc ChangeLog.md README.md
%doc examples
%{profiledir}/bash-color-prompt.sh
%dir %{bcp_datadir}
%{bcp_datadir}/bcp.sh


%changelog
%autochangelog
