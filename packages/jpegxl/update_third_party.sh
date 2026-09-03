VERSION=0.11.2

git clone https://github.com/libjxl/libjxl
cd libjxl/
git checkout .
git checkout v${VERSION}
./deps.sh
rm -rvf third_party/brotli/
rm -rvf third_party/googletest/
rm -rvf third_party/HEVCSoftware/
rm -rvf third_party/highway/
rm -rvf third_party/lcms/
rm -rvf third_party/libjpeg-turbo
rm -rvf third_party/libpng/
rm -rvf third_party/skcms/profiles/
rm -rvf third_party/zlib
tar -zcf ../third_party-${VERSION}.tar.gz third_party/
tar -zcf ../testdata-${VERSION}.tar.gz testdata/
cd ..
rm -rf libjxl/
