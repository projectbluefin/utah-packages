# spectool -gf -d "with_github_source 1" to download original source
%bcond github_source 0

%global make_opts DEBUG_BUILD=1 DISABLE_RAR=1 LOCAL_FLAGS="%{optflags}" -f makefile.gcc
# the last build right now is 16.02-32
%global obs_ver 16.03
 
Name:           7zip
Version:        26.04
Release:        %autorelease
Summary:        A file archiver

# from DOC/License.txt
# CPP/7zip/Compress/Rar* files: the "GNU LGPL" with "unRAR license restriction"
# => we are shipping a source tarball with this stripped
# CPP/7zip/Compress/LzfseDecoder.cpp: the "BSD 3-clause License"
# C/ZstdDec.c: the "BSD 3-clause License"
# C/Xxh64.c: the "BSD 2-clause License"
# Some files are "public domain" files, if "public domain" status is stated in source file.
# the "GNU LGPL" for all other files. If there is no license information in 
# => this is LGPL-2.1-or-later from the text in that file
License:        LGPL-2.1-or-later AND BSD-3-Clause AND BSD-2-Clause AND LicenseRef-Fedora-Public-Domain
URL:            https://7-zip.org
# strip the source with strip-rar-support.sh
%if %{with github_source}
Source:         https://github.com/ip7z/7zip/archive/%{version}/%{name}-%{version}.tar.gz
%endif
# Utah: tools/generated_sources.py makes the same tree strip-rar-support.sh
# makes, from the SHA-512-pinned upstream release, as xz (the standard library
# writes no zstd). The tree is identical to Fedora's .tar.zst lookaside copy.
Source:         %{name}-%{version}.tar.xz
Source:         strip-rar-support.sh
Patch:          https://github.com/ip7z/7zip/pull/33.patch#/7z-dont-echo-password.diff
# patch where 7z.so is loaded from so we don't need to do shenanigans like having the 7z binary
# there and invoking via a wrapper
Patch:          7zip-find-so-in-libexec.diff

BuildRequires:  gcc-c++
BuildRequires:  make

# p7zip-plugins ships 7z
Provides:       p7zip-plugins = %{version}-%{release}
Obsoletes:      p7zip-plugins < %{obs_ver}

%global _description %{expand:
7-Zip is a file archiver with a high compression ratio. The main features
of 7-Zip are:

* High compression ratio in 7z format with LZMA and LZMA2 compression
* Supported formats:
  * Packing / unpacking: 7z, XZ, BZIP2, GZIP, TAR, ZIP and WIM
  * Unpacking only: AR, ARJ, CAB, CHM, CPIO, CramFS, DMG, EXT, FAT,
    GPT, HFS, IHEX, ISO, LZH, LZMA, MBR, MSI, NSIS, NTFS, QCOW2,
    RPM, SquashFS, UDF, UEFI, VDI, VHD, VMDK, WIM, XAR and Z.
* For ZIP and GZIP formats, 7-Zip provides a compression ratio that is
  2-10 % better than the ratio provided by PKZip and WinZip
* Strong AES-256 encryption in 7z and ZIP formats
* Powerful command line version}

%description %{_description}


%package        reduced
Summary:        Standalone version of 7-Zip console that supports only 7z (reduced version)

%description    reduced %{_description}


%package        standalone
Summary:        Standalone version of 7-Zip console that supports only some formats
# p7zip ships 7za
Provides:       p7zip = %{version}-%{release}
Obsoletes:      p7zip < %{obs_ver}

%description    standalone %{_description}

This version supports only 7z/xz/cab/zip/gzip/bzip2/tar.


%package        standalone-all
Summary:        Standalone version of 7-Zip console that supports all formats

%description    standalone-all %{_description}


%prep
%autosetup -p1

# avoid failures due to new warnings in latest GCC
sed -i -e 's|-Werror||' CPP/7zip/7zip_gcc.mak
# from 7zip-find-so-in-libexec.diff
sed -i -e 's|__Z7_PREFIX__|%{_prefix}|g' CPP/7zip/UI/Common/ArchiveCommandLine.cpp


%build
# 7z.so
%make_build %make_opts -C CPP/7zip/Bundles/Format7zF/

# 7z
%make_build %make_opts LOCAL_FLAGS="%{optflags} -DZ7_EXTERNAL_CODECS" -C CPP/7zip/UI/Console/

# 7za
%make_build %make_opts -C CPP/7zip/Bundles/Alone/

# 7z4
%make_build %make_opts -C CPP/7zip/Bundles/Alone7z/

# 7zz
%make_build %make_opts -C CPP/7zip/Bundles/Alone2/


%install
install -Dpm 755 ./CPP/7zip/UI/Console/_o/7z %{buildroot}%{_bindir}/7z
install -Dpm 755 ./CPP/7zip/Bundles/Format7zF/_o/7z.so %{buildroot}%{_libexecdir}/%{name}/7z.so
install -Dpm 755 ./CPP/7zip/Bundles/Alone/_o/7za %{buildroot}%{_bindir}/7za
install -Dpm 755 ./CPP/7zip/Bundles/Alone7z/_o/7zr %{buildroot}%{_bindir}/7zr
install -Dpm 755 ./CPP/7zip/Bundles/Alone2/_o/7zz %{buildroot}%{_bindir}/7zz


%files
%license DOC/License.txt DOC/copying.txt
%doc DOC/readme.txt DOC/7zC.txt DOC/7zFormat.txt DOC/lzma.txt 
%{_bindir}/7z
%{_libexecdir}/%{name}/

%files reduced
%license DOC/License.txt DOC/copying.txt
%{_bindir}/7zr

%files standalone
%license DOC/License.txt DOC/copying.txt
%{_bindir}/7za

%files standalone-all
%license DOC/License.txt DOC/copying.txt
%{_bindir}/7zz


%changelog
%autochangelog
