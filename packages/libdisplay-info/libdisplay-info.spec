# See https://gitlab.freedesktop.org/emersion/libdisplay-info/-/merge_requests/149
# for library versioning explanation.
%global sover 4

Name:           libdisplay-info
Version:        0.4.0
Release:        1%{?dist}
Summary:        EDID and DisplayID library

# Main license: MIT
# test/data: CC-BY-4.0, MIT (see test/data/README.md).
License:        MIT
URL:            https://gitlab.freedesktop.org/emersion/libdisplay-info
# The source pipeline verifies the release signature (signature_url and
# gpg_key in config/upstream-sources.json) before the tarball is staged:
# the factory can only fetch extra Source files from Fedora's lookaside,
# which carries no signature for a release Fedora has not imported.
Source0:        %{url}/-/releases/%{version}/downloads/%{name}-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  meson >= 0.57
BuildRequires:  pkgconfig(hwdata)

%description
%{summary}.

%package        tools
Summary:        Command-line tools for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    tools
%{summary}.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup


%build
%meson
%meson_build


%install
%meson_install


%check
%meson_test


%files
%license LICENSE
%doc README.md
%{_libdir}/%{name}.so.%{sover}
%{_libdir}/%{name}.so.%{version}

%files tools
%{_bindir}/di-edid-decode

%files devel
%{_includedir}/%{name}
%{_libdir}/%{name}.so
%{_libdir}/pkgconfig/%{name}.pc


%changelog
* Mon Nov 16 2026 Utah package factory <noreply@projectbluefin.io> - 0.4.0-1
- Update to 0.4.0 (Dakota's core-deps/libdisplay-info.bst); soname moves to .so.4
- Verify the release signature in the source pipeline instead of %%prep

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 23 2026 Aleksei Bavshin <alebastr@fedoraproject.org> - 0.3.0-1
- Update to 0.3.0 (#2387864)

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Sat Jun 29 2024 Aleksei Bavshin <alebastr@fedoraproject.org> - 0.2.0-1
- Update to 0.2.0 (#2293555)

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Feb 16 2023 Aleksei Bavshin <alebastr@fedoraproject.org> - 0.1.1-1
- Initial import (#2170328)
