%global commit d79eacf77abe3b799387bb8a4e07a18f1f1031e8
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global date 20250123

Name: compsize
Version: 1.5^git%{date}.%{shortcommit}
Release: 16%{?dist}
Summary: Utility for measuring compression ratio of files on btrfs
# Automatically converted from old format: GPLv2+ - review is highly recommended.
License: GPL-2.0-or-later
URL: https://github.com/kilobyte/compsize
Source: https://github.com/kilobyte/%{name}/archive/%{commit}/%{name}-%{shortcommit}.tar.gz   
# https://github.com/kilobyte/compsize/pull/54
Patch: %{name}-1.5_fix_includes.patch
BuildRequires: gcc
BuildRequires: btrfs-progs-devel
BuildRequires: make

%description
compsize takes a list of files (given as arguments) on a btrfs filesystem and
measures used compression types and effective compression ratio, producing
a report.

%prep
%autosetup -n %{name}-%{commit}

%build
%set_build_flags
%make_build

%install
install -D -m 0755 %{name} %{buildroot}%{_bindir}/%{name}
install -D -m 0644 %{name}.8 %{buildroot}%{_mandir}/man8/%{name}.8

%files
%doc README.md
%license LICENSE
%{_bindir}/%{name}
%{_mandir}/man8/%{name}.8*

%changelog
* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.5^git20250123.d79eacf-16
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.5^git20250123.d79eacf-15
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.5^git20250123.d79eacf-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.5^git20250123.d79eacf-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Thu Jan 23 2025 Juan Orti Alcaine <jortialc@redhat.com> - 1.5^git20250123.d79eacf-12
- Update to the latest git snapshot
- Add patch to fix build errors

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 25 2024 Miroslav Suchý <msuchy@redhat.com> - 1.5-10
- convert license to SPDX

* Wed Jul 17 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Jul 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Wed Jan 19 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Wed Jul 21 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Wed Feb 10 2021 Juan Orti Alcaine <jortialc@redhat.com> - 1.5-1
- Version 1.5 (#1918100)

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Wed Jan 20 2021 Juan Orti Alcaine <jortialc@redhat.com> - 1.4-1
- Version 1.4 (#1918100)

* Thu Aug 06 2020 Juan Orti Alcaine <jortialc@redhat.com> - 1.3-4
- Use set_build_flags macro

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Aug 29 2019 Juan Orti Alcaine <jortialc@redhat.com> - 1.3-1
- Version 1.3

* Wed Jul 24 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Thu Jul 12 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Fri Mar 23 2018 Juan Orti Alcaine <jorti@fedoraproject.org> - 1.1-1
- Initial release
