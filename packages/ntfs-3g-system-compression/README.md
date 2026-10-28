# ntfs-3g-system-compression

System compression, also known as "Compact OS", is a Windows feature that
allows rarely modified files to be compressed using the XPRESS or LZX
compression formats. It is not built directly into NTFS but rather is
implemented using reparse points. This feature appeared in Windows 10 and it
appears that many Windows 10 systems have been using it by default.

This RPM contains a plugin which enables the NTFS-3G FUSE driver to
transparently read from system-compressed files. Currently, only reading is
supported. Compressing an existing file may be done by using the "compact"
utility on Windows.

Upstream: https://github.com/ebiggers/ntfs-3g-system-compression
