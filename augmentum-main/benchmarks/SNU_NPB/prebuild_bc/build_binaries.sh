#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

source env.config

VCLANG=${VAN}/clang
VOPT=${VAN}/opt
VDISS=${VAN}/llvm-dis
MOPT=${MOD}/opt

BCS=`pwd`/bc_out

TARGETS="bt cg ep ft is lu mg sp"

LFLAGS="-mcmodel=medium -lm"

# build binary versions using modified optimiser and extension
BIN=`pwd`/augmentum_bins
mkdir -p $BIN
#OPT_FLAGS="-load /path/to/libextension.so"
OPT_FLAGS=""

for t in $TARGETS; do
    VFY="$BCS/${t}_verify.S.o"
    if [[ ! -f "$VFY" ]]; then VFY="" ;fi

    echo "Building augmentum binaries for $t"

    $MOPT $OPT_FLAGS $BCS/$t.S.bc -o $BCS/${t}_opt.S.bc -Oz
    $VCLANG $LFLAGS -o $BIN/$t.S.x $BCS/${t}_opt.S.bc $VFY
    $VDISS $BCS/$t.S.bc -o $BIN/$t.S.ll
    $VDISS $BCS/${t}_opt.S.bc -o $BIN/${t}_opt.S.ll
done

# build binary versions using vanilla optimiser
BIN=`pwd`/vanilla_bins
mkdir -p $BIN
OPT_FLAGS=""

for t in $TARGETS; do
    VFY="$BCS/${t}_verify.S.o"
    if [[ ! -f "$VFY" ]]; then VFY="" ;fi

    echo "Building vanilla binaries for $t"

    $VOPT $OPT_FLAGS $BCS/$t.S.bc -o $BCS/${t}_opt.S.bc -Oz
    $VCLANG $LFLAGS -o $BIN/$t.S.x $BCS/${t}_opt.S.bc $VFY
    $VDISS $BCS/$t.S.bc -o $BIN/$t.S.ll
    $VDISS $BCS/${t}_opt.S.bc -o $BIN/${t}_opt.S.ll
done

