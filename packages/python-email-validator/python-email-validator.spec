Name:           python-email-validator
Version:        2.3.0
Release:        %autorelease
Summary:        A robust email syntax and deliverability validation library

License:        Unlicense
URL:            https://github.com/JoshData/python-email-validator
Source0:        %{url}/archive/v%{version}/python-email-validator-%{version}.tar.gz
# Man page hand-written for Fedora in groff_man(7) format, based closely on the
# comments in email_validator/__main__.py, email_validator/__init__.py, and
# README.md.
#
# Interest in a man page?
# https://github.com/JoshData/python-email-validator/issues/146
Source1:        email_validator.1

BuildSystem:    pyproject
BuildOption(install): --assert-license email_validator

BuildArch:      noarch

# test_requirements.txt pins exact versions and includes unwanted coverage and
# linting dependencies, so we fall back to manual BuildRequires:
BuildRequires:  %{py3_dist pytest}

%global _description %{expand:
This library validates that a string is of the form name@example.com and
optionally checks that the domain name is set up to receive email. This is the
sort of validation you would want when you are identifying users by their email
address like on a registration/login form (but not necessarily for composing an
email message).

Key features:

  • Checks that an email address has the correct syntax – great for
    email-based registration/login forms or validating data.
  • Gives friendly English error messages when validation fails that you can
    display to end-users.
  • Checks deliverability (optional): Does the domain name resolve? (You can
    override the default DNS resolver to add query caching.)
  • Supports internationalized domain names and internationalized local parts.
  • Rejects addresses with unsafe Unicode characters, obsolete email address
    syntax that you’d find unexpected, special use domain names like
    @localhost, and domains without a dot by default. This is an opinionated
    library!
  • Normalizes email addresses (important for internationalized and
    quoted-string addresses!)
  • Python type annotations are used.}

%description %{_description}


%package -n     python3-email-validator
Summary:        %{summary}

%description -n python3-email-validator %{_description}


%install -a
install -D --preserve-timestamps --mode=0644 \
    --target='%{buildroot}%{_mandir}/man1' '%{SOURCE1}'


%check -a
%pytest --verbose tests -m 'not network'


%files -n python3-email-validator -f %{pyproject_files}
%doc CHANGELOG.md
%doc README.md

%{_bindir}/email_validator
%{_mandir}/man1/email_validator.1*


%changelog
%autochangelog
