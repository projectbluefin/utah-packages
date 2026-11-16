# The offline Bluefin documentation, as Project Bluefin Dakota ships it.
#
# Written from Dakota's bluefin/bluefin-docs.bst (projectbluefin/dakota
# bf271777): projectbluefin/documentation publishes every build as an
# immutable YY.MM.N release whose bluefin.pdf asset the element installs,
# unchanged, at /usr/share/doc/bluefin/bluefin.pdf. Dakota's logo-menu
# Documentation entry opens that path with Papers.

Name:           bluefin-docs
Version:        26.11.3
Release:        1%{?dist}
Summary:        Offline Bluefin documentation

License:        Apache-2.0
URL:            https://github.com/projectbluefin/documentation
Source0:        %{url}/releases/download/%{version}/bluefin.pdf#/%{name}-%{version}.pdf

BuildArch:      noarch

%description
The Bluefin user documentation as a single PDF, for reading offline.

%prep
%setup -q -c -T

%build
# A prebuilt PDF; nothing to build.

%install
install -Dpm 0644 %{SOURCE0} %{buildroot}%{_datadir}/doc/bluefin/bluefin.pdf

%check
test "$(head -c 5 %{buildroot}%{_datadir}/doc/bluefin/bluefin.pdf)" = "%%PDF-"

%files
%dir %{_datadir}/doc/bluefin
%{_datadir}/doc/bluefin/bluefin.pdf

%changelog
* Mon Nov 16 2026 github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com> - 26.11.3-1
- Update to 26.11.3

* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 26.11.1-1
- Initial recipe from Dakota bluefin/bluefin-docs.bst
