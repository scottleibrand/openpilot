#!/bin/bash
VALGRIND_VERSION=3.20.0

wget https://sourceware.org/pub/valgrind/valgrind-$VALGRIND_VERSION.tar.bz2
bunzip2 valgrind-$VALGRIND_VERSION.tar.bz2
tar -xvf valgrind-$VALGRIND_VERSION.tar

cd valgrind-$VALGRIND_VERSION
./autogen.sh
mkdir build
./configure --prefix=$(pwd)/build
make -j8 && make install

export VALGRIND_LIB=$(pwd)/build/libexec/valgrind/
