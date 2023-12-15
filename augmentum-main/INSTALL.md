## Installation

One-time setup: create a base python environment using:

```sh
conda env create --file environment.yml
conda activate augmentum
```

All dependencies are built together with Augmentum except for LLVM binaries.

Augmentum requires LLVM binaries and was tested against LLVM version 10.0.1 and ubuntu-20.04.
To compile LLVM, do the following:

Download LLVM sources.
```bash
mkdir ${LLVM_DIR}
cd ${LLVM_DIR}
git clone --depth=100 --branch release/10.x https://github.com/llvm/llvm-project
```

Build LLVM with RTTI and EH from inside *LLVM_DIR*.

```bash
mkdir build install

cd build
cmake \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DLLVM_TARGETS_TO_BUILD=X86 \
    '-DLLVM_ENABLE_PROJECTS=clang;clang-tools-extra;libclc;libcxx;libcxxabi;libunwind;lld' \
    -DBUILD_SHARED_LIBS=True \
    -DCMAKE_INSTALL_PREFIX=${LLVM_DIR}/install \
    -DLLVM_ENABLE_RTTI=ON \
    -DLLVM_ENABLE_EH=ON \
    ../llvm-project/llvm

make -j`nproc` install
```

To build Augmentum libraries and the python project, pass the path of the `lib/cmake/llvm` subdirectory in ${LLVM_DIR}/install
to `LLVM_DIR` and call:

```sh
$ make all LLVM_DIR=/path/to/llvm/install/lib/cmake/llvm/
```

You can test if the framework is build correctly and work as expected by running the test set:

```bash
$ make test
```
