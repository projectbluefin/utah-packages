%bcond check 1

%global gomodulesmode GO111MODULE=on

Name:           glow
Version:        3.0.0
Release:        %autorelease
ExclusiveArch:  %{golang_arches_future}
Summary:        Terminal based markdown reader
License:        Apache-2.0 AND BSD-3-Clause AND MIT AND OFL-1.1
URL:            https://github.com/charmbracelet/glow
Source0:        %{url}/archive/v%{version}/glow-%{version}.tar.gz
Source1:        glow-%{version}-vendor.tar.bz2
Source2:        go-vendor-tools.toml

BuildRequires:  go-rpm-macros
BuildRequires:  go-vendor-tools
BuildRequires:  askalono-cli


%description
Glow is a terminal based markdown reader designed from the ground up to bring
out the beauty—and power—of the CLI.  Use it to discover markdown files, read
documentation directly on the command line.  Glow will find local markdown
files in subdirectories or a local Git repository.


%prep
%autosetup -p 1 -a 1


%build
export GO_LDFLAGS="-X main.Version=v%{version}"
%gobuild -o bin/glow .


%install
# licenses
%go_vendor_license_install -c %{S:2}

# command
install -D -p -m 0755 -t %{buildroot}%{_bindir} bin/glow

# man page
install -d -m 0755 %{buildroot}%{_mandir}/man1
./bin/glow man > %{buildroot}%{_mandir}/man1/glow.1

# shell completions
install -d -m 0755 %{buildroot}%{bash_completions_dir}
./bin/glow completion bash > %{buildroot}%{bash_completions_dir}/glow
install -d -m 0755 %{buildroot}%{zsh_completions_dir}
./bin/glow completion zsh > %{buildroot}%{zsh_completions_dir}/_glow
install -d -m 0755 %{buildroot}%{fish_completions_dir}
./bin/glow completion fish > %{buildroot}%{fish_completions_dir}/glow.fish


%check
# ensure that the version was embedded correctly
[[ "$(./bin/glow --version)" == "glow version v%{version}" ]] || exit 1

# Utah: exercise the noninteractive changelog rendering path as well as --version.
printf "# Utah changelog\n\nRelease notes render here.\n" | ./bin/glow -s ascii -w 80 - > rendered.txt
grep -F "Release notes render here." rendered.txt

# license validation
%go_vendor_license_check -c %{S:2}

# upstream tests
%if %{with check}
%gocheck2
%endif


%files -f %{go_vendor_license_filelist}
%{_bindir}/glow
%{_mandir}/man1/glow.1*
%{bash_completions_dir}/glow
%{zsh_completions_dir}/_glow
%{fish_completions_dir}/glow.fish


%changelog
%autochangelog
