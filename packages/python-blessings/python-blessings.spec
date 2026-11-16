%bcond tests 1

Name:           python-blessings
Version:        1.7
Release:        35%{?dist}
Summary:        Thin, practical wrapper around terminal coloring, styling, and positioning
License:        MIT
URL:            https://github.com/erikrose/blessings
Source:         %{pypi_source blessings}
# https://github.com/erikrose/blessings/issues/25
Patch:          0001-fix-tests-when-run-without-a-tty-fixes-25.patch
Patch:          0002-more-fixes-for-tests-without-a-tty.patch
# https://github.com/erikrose/blessings/pull/167
Patch:          0003-chore-replace-nose-with-pytest.patch
BuildArch:      noarch

%global _description %{expand:
Blessings lifts several of curses' limiting assumptions, and it makes your code
pretty, too:

* Use styles, color, and maybe a little positioning without necessarily
  clearing the whole screen first.
* Leave more than one screenful of scrollback in the buffer after your program
  exits, like a well-behaved command-line app should.
* Get rid of all those noisy, C-like calls to tigetstr and tparm, so your code
  does not get crowded out by terminal bookkeeping.
* Act intelligently when somebody redirects your output to a file, omitting the
  terminal control codes the user does not want to see (optional).}

%description %{_description}

%package -n python3-blessings
Summary:        %{summary}
BuildRequires:  python3-devel

%description -n python3-blessings %{_description}

%prep
%autosetup -p 1 -n blessings-%{version}

%generate_buildrequires
%pyproject_buildrequires %{?with_tests:-t}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files blessings

%check
%if %{with tests}
%tox
%else
%pyproject_check_import -e blessings.tests
%endif

%files -n python3-blessings -f %{pyproject_files}
%doc README.rst

%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-35
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Wed Jun 03 2026 Python Maint <python-maint@redhat.com> - 1.7-34
- Rebuilt for Python 3.15

* Sat Jan 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-33
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Sep 19 2025 Python Maint <python-maint@redhat.com> - 1.7-32
- Rebuilt for Python 3.14.0rc3 bytecode

* Fri Aug 29 2025 Carl George <carlwgeorge@fedoraproject.org> - 1.7-31
- Re-enable tests via upstream patch

* Fri Aug 15 2025 Python Maint <python-maint@redhat.com> - 1.7-30
- Rebuilt for Python 3.14.0rc2 bytecode

* Fri Jul 25 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-29
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Mon Jun 02 2025 Python Maint <python-maint@redhat.com> - 1.7-28
- Rebuilt for Python 3.14

* Wed Mar 19 2025 Michel Lind <salimma@fedoraproject.org> - 1.7-27
- Disable nose tests on Fedora >= 43
- Resolves: RHBZ#2349839

* Sat Jan 18 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-26
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Fri Jul 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-25
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Fri Jun 07 2024 Python Maint <python-maint@redhat.com> - 1.7-24
- Rebuilt for Python 3.13

* Fri Jan 26 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-23
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-22
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jul 21 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-21
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Wed Jun 14 2023 Python Maint <python-maint@redhat.com> - 1.7-20
- Rebuilt for Python 3.12

* Fri Jan 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-19
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Fri Aug 26 2022 Carl George <carl@george.computer> - 1.7-18
- Convert to pyproject macros

* Fri Jul 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-17
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Mon Jun 13 2022 Python Maint <python-maint@redhat.com> - 1.7-16
- Rebuilt for Python 3.11

* Fri Jan 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-15
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Fri Jul 23 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Fri Jun 04 2021 Python Maint <python-maint@redhat.com> - 1.7-13
- Rebuilt for Python 3.10

* Wed Jan 27 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue May 26 2020 Miro Hrončok <mhroncok@redhat.com> - 1.7-10
- Rebuilt for Python 3.9

* Thu Jan 30 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Oct 03 2019 Miro Hrončok <mhroncok@redhat.com> - 1.7-8
- Rebuilt for Python 3.8.0rc1 (#1748018)

* Mon Aug 19 2019 Miro Hrončok <mhroncok@redhat.com> - 1.7-7
- Rebuilt for Python 3.8

* Fri Jul 26 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu May 09 2019 Miro Hrončok <mhroncok@redhat.com> - 1.7-5
- Subpackage python2-blessings has been removed
  See https://fedoraproject.org/wiki/Changes/Mass_Python_2_Package_Removal

* Sat Feb 02 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.7-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Mon Jul 02 2018 Miro Hrončok <mhroncok@redhat.com> - 1.7-2
- Rebuilt for Python 3.7

* Tue Jun 26 2018 Dan Callaghan <dcallagh@redhat.com> - 1.7-1
- Upstream release 1.7 (RHBZ#1594040)

* Tue Jun 19 2018 Miro Hrončok <mhroncok@redhat.com> - 1.5-16
- Rebuilt for Python 3.7

* Fri Feb 09 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-15
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Jun 23 2017 Dan Callaghan <dcallagh@redhat.com> - 1.5-13
- forgot to add %%python_provide macro

* Fri Jun 23 2017 Dan Callaghan <dcallagh@redhat.com> - 1.5-12
- renamed python-blessings to python2-blessings

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Mon Dec 19 2016 Miro Hrončok <mhroncok@redhat.com> - 1.5-10
- Rebuild for Python 3.6

* Tue Jul 19 2016 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.5-9
- https://fedoraproject.org/wiki/Changes/Automatic_Provides_for_Python_RPM_Packages

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.5-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Tue Nov 10 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.5-7
- Rebuilt for https://fedoraproject.org/wiki/Changes/python3.5

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.5-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.5-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Wed May 14 2014 Bohuslav Kabrda <bkabrda@redhat.com> - 1.5-4
- Rebuilt for https://fedoraproject.org/wiki/Changes/Python_3.4

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Fri Nov 30 2012 Dan Callaghan <dcallagh@redhat.com> - 1.5-1
- initial version
