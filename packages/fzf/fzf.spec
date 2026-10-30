%bcond_without check

# https://github.com/junegunn/fzf
%global goipath         github.com/junegunn/fzf
Version:                0.74.5

%gometa

Name:           fzf
Release:        %autorelease
Summary:        A command-line fuzzy finder written in Go

License:        MIT
URL:            %{gourl}
Source0:        %{gosource}
Source1:        README.Fedora

BuildRequires:  golang(github.com/charlievieth/fastwalk) >= 1.0.9
BuildRequires:  golang(github.com/gdamore/tcell/v2) >= 2.7.4
BuildRequires:  golang(github.com/junegunn/go-shellwords)
BuildRequires:  golang(github.com/mattn/go-isatty) >= 0.0.20
BuildRequires:  golang(github.com/rivo/uniseg) >= 0.4.7
BuildRequires:  golang(golang.org/x/sys/unix) >= 0.28
BuildRequires:  golang(golang.org/x/term) >= 0.25


%description
fzf is a general-purpose command-line fuzzy finder.

It's an interactive Unix filter for command-line that can be used with any
list; files, command history, processes, hostnames, bookmarks, git commits,
etc.


%prep
%goprep
cp %{SOURCE1} .
%autopatch -p1


%build
export LDFLAGS='-X main.version=%{version} -X main.revision=Fedora '
%gobuild -o %{gobuilddir}/bin/fzf %{goipath}


%install
install -Dpm0755 -t %{buildroot}%{_bindir} %{gobuilddir}/bin/fzf bin/fzf-tmux
install -Dpm0644 -t %{buildroot}%{_mandir}/man1 man/man1/*.1

# Install vim plugin
install -Dpm0644 -t %{buildroot}%{_datadir}/vim/vimfiles/plugin plugin/fzf.vim
install -Dpm0644 -t %{buildroot}%{_datadir}/nvim/site/plugin plugin/fzf.vim

# Install shell completion
# fzf is special, bash completion must be in /etc/bash_completion.d
# https://bugzilla.redhat.com/show_bug.cgi?id=1789958#c7
install -Dpm0644 shell/completion.bash %{buildroot}%{_sysconfdir}/bash_completion.d/fzf
install -Dpm0644 shell/completion.zsh %{buildroot}%{zsh_completions_dir}/_fzf

# Install shell key bindings (not enabled)
install -Dpm0644 -t %{buildroot}%{_datadir}/fzf/shell shell/key-bindings.*


%if %{with check}
%check
%gocheck
%endif


%files
%license LICENSE
%doc README.md README-VIM.md CHANGELOG.md README.Fedora
%{_bindir}/fzf
%{_bindir}/fzf-tmux
%{_mandir}/man1/fzf.1*
%{_mandir}/man1/fzf-tmux.1*
%{_datadir}/fzf
%dir %{_datadir}/vim/vimfiles/plugin
%{_datadir}/vim/vimfiles/plugin/fzf.vim
%dir %{_datadir}/nvim/site/plugin
%{_datadir}/nvim/site/plugin/fzf.vim
%{_sysconfdir}/bash_completion.d/fzf
%{zsh_completions_dir}/_fzf


%changelog
%autochangelog
