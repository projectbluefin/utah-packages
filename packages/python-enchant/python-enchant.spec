%global srcname enchant

Name:           python-enchant
Version:        3.3.0
Release:        %autorelease
Summary:        Python bindings for Enchant spellchecking library

License:        LGPL-2.1-or-later
URL:            https://pyenchant.github.io/pyenchant/
Source:         %{pypi_source pyenchant}

BuildArch:      noarch

BuildRequires:  enchant2
BuildRequires:  python3-devel
%if %{undefined rhel}
# For importing the wxSpellCheckerDialog module
BuildRequires:  python3-wxpython4
%endif

%description
PyEnchant is a spellchecking library for Python, based on the Enchant
library by Dom Lachowicz.


%package -n python3-%{srcname}
Summary:        Python 3 bindings for Enchant spellchecking library

Requires:       enchant2

%description -n python3-%{srcname}
PyEnchant is a spellchecking library for Python 3, based on the Enchant
library by Dom Lachowicz.

%prep
%autosetup -p1 -n py%{srcname}-%{version}
# Workaround for https://github.com/pyenchant/pyenchant/issues/326
sed -i "/size=wxSpellCheckerDialog\.sz/s/wxSpellCheckerDialog\.//" enchant/checker/wxSpellCheckerDialog.py

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -L %{srcname}

# Tests are not included in the upstream tarball
%check
# We exclude testing of the import for the GtkSpellCheckerDialog
# as it utilizes the legacy PyGTK bindings.
# On RHEL, we also exclude wx to avoid it as a dependency.
%pyproject_check_import -e '*.GtkSpellCheckerDialog' %{?rhel:-e '*.wxSpellCheckerDialog'}

%files -n python3-%{srcname} -f %{pyproject_files}
%doc README.rst
%license LICENSE.txt


%changelog
%autochangelog
