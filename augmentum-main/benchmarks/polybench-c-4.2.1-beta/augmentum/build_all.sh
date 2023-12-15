#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

source env.config

VCLANG=${VAN}/clang
MCLANG=${MOD}/clang

AUGMENTUM_HOME=`git rev-parse --show-toplevel`

HOME="${AUGMENTUM_HOME}/benchmarks/polybench-c-4.2.1-beta/"

VBIN="${HOME}/augmentum/vanilla_bins"
MBIN="${HOME}/augmentum/augmentum_bins"

BLD="${HOME}/augmentum/build"

mkdir -p $VBIN $MBIN $BLD

CFLAGS="-Oz -fno-crash-diagnostics"
LFLAGS=

TARGETS="
medley/floyd-warshall
medley/deriche
medley/nussinov
linear-algebra/solvers/ludcmp
linear-algebra/solvers/trisolv
linear-algebra/solvers/durbin
linear-algebra/solvers/lu
linear-algebra/solvers/cholesky
linear-algebra/solvers/gramschmidt
linear-algebra/blas/gesummv
linear-algebra/blas/trmm
linear-algebra/blas/gemm
linear-algebra/blas/syr2k
linear-algebra/blas/syrk
linear-algebra/blas/symm
linear-algebra/blas/gemver
linear-algebra/kernels/atax
linear-algebra/kernels/doitgen
linear-algebra/kernels/mvt
linear-algebra/kernels/bicg
linear-algebra/kernels/2mm
linear-algebra/kernels/3mm
stencils/jacobi-1d
stencils/jacobi-2d
stencils/fdtd-2d
stencils/adi
stencils/heat-3d
stencils/seidel-2d
datamining/covariance
datamining/correlation
"
CLASS="SMALL"

printf "========= BUILDING AUGMENTUM TARGETS ==========================================\n"
for t in $TARGETS; do
    NAME=`basename $t`
    SRC=${HOME}/$t
    printf "\n\nBuilding augmentum binaries for $NAME and problem size $CLASS\n"
    ./build.sh $NAME $CLASS $HOME $SRC $MBIN $BLD $VCLANG $MCLANG "$CFLAGS" "$LFLAGS" "$EXTENSION"
done


printf "\n\n========= BUILDING VANILLA TARGETS ============================================\n"
# extension from config file unset to allow vanilla builds
EXTENSION=""

for t in $TARGETS; do
    NAME=`basename $t`
    SRC=${HOME}/$t
    printf "\n\nBuilding vanilla binaries for $NAME and problem size $CLASS\n"
    ./build.sh $NAME $CLASS $HOME $SRC $VBIN $BLD $VCLANG $VCLANG "$CFLAGS" "$LFLAGS" "$EXTENSION"
done
