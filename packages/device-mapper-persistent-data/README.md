# Packaging device-mapper-persitent-data (AKA dmpd)

This is rust package using *vendor* file for dependencies. (Vendor file is an archive of dependencies' sources.)

For most of simple fixes, there is nothing special,
to add a patches simply add them to dist-git,
add a corresponding `PatchN: 000N-...` lines,
increase `Release:` or `release_suffix` for Z-stream (or for test build use suffix like `.bzNNNNNN`),
add to `%changelog`,
commit,
push,
and build the package using `fedpkg build`.

Alternatively before committing anything use `fedpkg srpm` and `fedpkg scratch-build --srpm $SRPM [--arches x86_64]` to create a scratch build.

However when building a new version of dmpd or when updating a dependency is
needed (e.g. because of CVE in the dependency) vendor file
has to be regenerated.

## Updating vendor file

To build a new version of the package following tooling is needed:

- `rust >= 1.35`
- `cargo` providing vendor subcommand (now upstream, included in latest Fedora and RHEL8+)

To create the vendor file:

In the upstream directory:

1. Run `cargo vendor` in the directory with upstream sources to create *vendor*
   directory with sources.
    - TODO: There is a *cargo-vendor-filterer* project used by *stratisd* to
      filter out unnecessary dependencies for other operating systems.
2. Run `tar czf device-mapper-persistent-data-vendor-$VERSION.tar.gz ./vendor` to create a tarball.
3. Copy the vendor file to dist git directory.

In the dist-git directory:

1. Get the upstream tarball `wget https://github.com/jthornber/thin-provisioning-tools/archive/v$VERSION.tar.gz`
    - NOTE: Migration to `https://github.com/device-mapper-utils/thin-provisioning-tools` is coming.
2. Update *Source0* and *Source1* to correct values.
3. Add the tarballs to koji/brew lookaside:
    - `fedpkg new-sources v$VERSION.tar.gz device-mapper-persistent-data-vendor-$VERSION.tar.gz`

## TODO/NOTES

Some of the dependencies are already packaged by Fedora. Can we instruct *cargo vendor* to include only those which are not provided by Fedora?
It would be possible to include these as submodules, and the rest could be used from Fedora.
For RHEL and CentOS Stream using vendor file is the recommended way.

*%cargo_install* installs by default in */usr/bin* but the package expects */usr/sbin*. For now I run *make install-rust-tools*.
Now Fedora unified the */usr/sbin* and */usr/bin* directories, to this can be "fixed" in Fedora and later in CentOS Stream.

