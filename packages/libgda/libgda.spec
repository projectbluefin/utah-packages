%global apiver  6.0

Name:           libgda
Epoch:          1
Version:        6.0.0
Release:        %autorelease
Summary:        Library for writing gnome database programs

License:        LGPL-2.0-or-later
URL:            http://www.gnome-db.org/
Source:         https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

Patch0:         mariadb.patch
Patch1:         signed-int.patch
Patch2:         libgda-fix-build-order.patch

BuildRequires:    gcc
BuildRequires:    gcc-c++
BuildRequires:    pkgconfig >= 0.8
BuildRequires:    glade-devel
BuildRequires:    glib2-devel >= 2.38.0
BuildRequires:    gtk3-devel >= 3.0.0
BuildRequires:    gtksourceview3-devel
BuildRequires:    goocanvas2-devel
BuildRequires:    graphviz-devel >= 2.26.0
BuildRequires:    iso-codes-devel
BuildRequires:    itstool
BuildRequires:    libxslt-devel >= 1.0.9
BuildRequires:    sqlite-devel >= 3.22.0
BuildRequires:    libgcrypt-devel
BuildRequires:    libgee-devel
BuildRequires:    gobject-introspection-devel >= 0.6.5
BuildRequires:    libxml2-devel readline-devel json-glib-devel
BuildRequires:    gtk-doc intltool gettext flex bison perl(XML::Parser)
BuildRequires:    libsecret-devel
BuildRequires:    libsoup-devel
BuildRequires:    openssl-devel
BuildRequires:    yelp-tools
BuildRequires:    vala
BuildRequires:    make
BuildRequires:    gnome-common
BuildRequires:    meson
BuildRequires:    openldap-devel
BuildRequires:    mariadb-connector-c-devel
BuildRequires:    libpq-devel
BuildRequires:    sqlcipher-devel

Provides: %{name}-bdb%{?_isa} = 1:%{version}-%{release}
Obsoletes: %{name}-bdb <= 1:5.2.10-4

Provides: %{name}-ldap%{?_isa} = 1:%{version}-%{release}
Obsoletes: %{name}-ldap <= 1:5.2.10-4

Provides: %{name}-sqlcipher%{?_isa} = 1:%{version}-%{release}
Obsoletes: %{name}-sqlcipher <= 1:5.2.10-4

Provides: %{name}-mdb%{?_isa} = 1:%{version}-%{release}
Obsoletes: %{name}-mdb <= 1:5.2.10-4

Provides: %{name}-java%{?_isa} = 1:%{version}-%{release}
Obsoletes: %{name}-java <= 1:5.2.10-4

Provides: %{name}-web%{?_isa} = 1:%{version}-%{release}
Obsoletes: %{name}-web <= 1:5.2.10-4

%description
%{name} is a library that eases the task of writing Gtk3-based database
programs.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{epoch}:%{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package ui
Summary:         UI extensions for %{name}
Requires:        %{name}%{?_isa} = %{epoch}:%{version}-%{release}

%description ui
%{name}-ui extends %{name} providing graphical widgets (Gtk+).

%package        ui-devel
Summary:        Development files for %{name}-ui
Requires:       %{name}%{?_isa} = %{epoch}:%{version}-%{release}
Requires:       %{name}-ui%{?_isa} = %{epoch}:%{version}-%{release}
Requires:       %{name}-devel%{?_isa} = %{epoch}:%{version}-%{release}
Requires:       gtk3-devel%{?_isa} >= 3.0.0

%description    ui-devel
The %{name}-ui-devel package contains libraries and header files for
developing applications that use %{name}-ui.

%package tools
Summary:         Graphical tools for %{name}
Requires:        %{name}-ui%{?_isa} = %{epoch}:%{version}-%{release}

%description tools
This %{name}-tools package provides graphical tools for %{name}.

%package sqlite
Summary:        SQLite provider for %{name}
Requires:       %{name}%{?isa} = %{epoch}:%{version}-%{release}
Requires:       sqlite-libs%{?isa} >= 3.22.0

%description sqlite
This %{name}-sqlite includes the %{name} SQLite provider.

%package sqlcipher
Summary:        SQLiteCipher provider for %{name}
Requires:       %{name}%{?isa} = %{epoch}:%{version}-%{release}

%description sqlcipher
This %{name}-sqlcipher includes the %{name} SQLiteCipher provider.

%package mysql
Summary:        Mysql provider for %{name}
Requires:       %{name}%{?isa} = %{epoch}:%{version}-%{release}

%description mysql
This %{name}-mysql includes the %{name} Mysql provider.

%package postgres
Summary:        Postgres provider for %{name}
Requires:       %{name}%{?isa} = %{epoch}:%{version}-%{release}

%description postgres
This %{name}-postgres includes the %{name} PostgreSQL provider.

%prep
%autosetup -p1

# AUTHORS not in UTF-8
iconv --from=ISO-8859-1 --to=UTF-8 AUTHORS > AUTHORS.new && \
touch -r AUTHORS AUTHORS.new && mv AUTHORS.new AUTHORS

%build
%meson -Djson=true -Dldap=true -Ddoc=false -Dexperimental=true -Dhelp=true -Dui=true -Dlibsoup=true -Dlibsecret=true -Dflatpak=false -Dsqlcipher=true -Dgraphviz=true
#-Dtools=true
#        -Dexamples=false \

%meson_build


%install
%meson_install
mkdir -p %{buildroot}%{_sysconfdir}/%{name}-%{apiver}/
install data/config %{buildroot}%{_sysconfdir}/%{name}-%{apiver}/config
install libgda-ui/data/import_encodings.xml %{buildroot}%{_datadir}/%{name}-%{apiver}/import_encodings.xml

%find_lang libgda-6.0

%files -f libgda-6.0.lang
%license COPYING
%doc AUTHORS ChangeLog README NEWS
%dir %{_sysconfdir}/%{name}-%{apiver}/
%config(noreplace) %{_sysconfdir}/%{name}-%{apiver}/config
%{_libdir}/%{name}-%{apiver}.so.*
%{_libdir}/%{name}-report-%{apiver}.so.*
%{_libdir}/%{name}-xslt-%{apiver}.so.*
%dir %{_libdir}/%{name}-%{apiver}/
%dir %{_libdir}/%{name}-%{apiver}/providers/
%{_libdir}/libgda-%{apiver}/providers/libgda-ldap-%{apiver}.so
%{_libdir}/girepository-1.0/Gda-%{apiver}.typelib
%dir %{_datadir}/%{name}-%{apiver}/
%dir %{_datadir}/%{name}-%{apiver}/dtd/
%{_datadir}/%{name}-%{apiver}/dtd/libgda-*.dtd
%{_datadir}/%{name}-%{apiver}/import_encodings.xml
%{_datadir}/%{name}-%{apiver}/information_schema.xml

%files devel
%{_datadir}/gir-1.0/Gda-%{apiver}.gir
%dir %{_includedir}/%{name}-%{apiver}/
%{_includedir}/%{name}-%{apiver}/%{name}
%{_includedir}/%{name}-%{apiver}/%{name}-report
%{_libdir}/%{name}-%{apiver}.so
%{_libdir}/%{name}-report-%{apiver}.so
%{_libdir}/%{name}-xslt-%{apiver}.so
%{_libdir}/pkgconfig/%{name}-%{apiver}.pc
%{_libdir}/pkgconfig/%{name}-*-%{apiver}.pc
%exclude %{_libdir}/pkgconfig/%{name}-ui-%{apiver}.pc
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/libgda-%{apiver}.vapi
%{_datadir}/vala/vapi/libgda-%{apiver}.deps
%{_includedir}/%{name}-%{apiver}/providers/


%files ui
%{_libdir}/%{name}-ui-%{apiver}.so.*
%{_libdir}/%{name}-%{apiver}/plugins/%{name}-ui-plugins-%{name}-%{apiver}.so
%{_libdir}/girepository-1.0/Gdaui-%{apiver}.typelib
%{_datadir}/%{name}-%{apiver}/ui/

%files ui-devel
%{_includedir}/%{name}-%{apiver}/%{name}-ui
%{_libdir}/%{name}-ui-%{apiver}.so
%{_libdir}/pkgconfig/%{name}-ui-%{apiver}.pc
%{_datadir}/%{name}-%{apiver}/demo/
%{_datadir}/gir-1.0/Gdaui-%{apiver}.gir
%{_datadir}/glade/
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/libgdaui-%{apiver}.vapi

%files tools
%{_bindir}/gda-*
%{_bindir}/org.gnome.gda.*
%{_bindir}/trml2html.py
%{_bindir}/trml2pdf.py
%{_datadir}/%{name}-%{apiver}/gda_trml2html
%{_datadir}/%{name}-%{apiver}/gda_trml2pdf

%files sqlite
%{_libdir}/%{name}-%{apiver}/providers/%{name}-sqlite-%{apiver}.so

%files mysql
%{_libdir}/libgda-%{apiver}/providers/libgda-mysql-%{apiver}.so

%files postgres
%{_libdir}/libgda-%{apiver}/providers/libgda-postgres-%{apiver}.so

%files sqlcipher
%{_libdir}/libgda-%{apiver}/providers/libgda-sqlcipher-%{apiver}.so

%changelog
%autochangelog
