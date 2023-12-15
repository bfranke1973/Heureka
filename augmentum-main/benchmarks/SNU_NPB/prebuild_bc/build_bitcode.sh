#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

source env.config

VCLANG=${VAN}/clang
VLINK=${VAN}/llvm-link

HOME=`pwd`/../NPB3.3-SER-C
SYS=$HOME/sys
COMMON=$HOME/common

CFLAGS="-O0 -g0 -Xclang -disable-O0-optnone -fno-crash-diagnostics -Wall -mcmodel=medium"
CFLAGS_OPT="-Oz -fno-crash-diagnostics -Wall -mcmodel=medium"

BLD=`pwd`/build
OUT=`pwd`/bc_out

# copying make.def for base project
cp -v make.def ${HOME}/config/

mkdir -p $BLD $OUT
cd $BLD 

# build param tool
# generate header parameters from make config
# make config is irrelevant for our purposes though
gcc -o $SYS/setparams $SYS/setparams.c

# build common files
$VCLANG $CFLAGS -emit-llvm -c -I$COMMON $COMMON/print_results.c
$VCLANG $CFLAGS -emit-llvm -c -I$COMMON $COMMON/c_print_results.c
$VCLANG $CFLAGS -emit-llvm -c -I$COMMON $COMMON/randdp.c
$VCLANG $CFLAGS -emit-llvm -c -I$COMMON $COMMON/c_timers.c
$VCLANG $CFLAGS -emit-llvm -c -I$COMMON $COMMON/wtime.c
$VCLANG $CFLAGS -emit-llvm -c -I$COMMON $COMMON/wtime.c -o c_wtime.bc


function build_benchmark {
    NAME=$1
    DIR=$2
    SRC=$3
    CMN=$4
    VFY=$5

    echo "Building bitcode for $NAME"

    cd $DIR
    $SYS/setparams $NAME S
    cd $BLD
    
    for file in $SRC; do
        $VCLANG $CFLAGS -emit-llvm -c -I$COMMON -I$DIR $DIR/$file
    done
    
    BC=${SRC//\.c/\.bc}
    
    $VLINK $BC $CMN -o $OUT/$NAME.S.bc

    if [[ ! -z $VFY ]]; then
        TARGET=$OUT/${NAME}_verify.S.o
        echo "Building external verification $TARGET"
        $VCLANG $CFLAGS_OPT -c $DIR/$VFY -o $TARGET
    fi
}

build_benchmark mg \
    $HOME/MG \
    "mg.c" \
    "print_results.bc randdp.bc c_timers.bc wtime.bc" \
    "auto2_verify.c"

build_benchmark cg \
    $HOME/CG \
    "cg.c" \
    "print_results.bc randdp.bc c_timers.bc wtime.bc" \
    "auto2_verify.c"

build_benchmark bt \
    $HOME/BT \
    "bt.c initialize.c exact_solution.c exact_rhs.c
     set_constants.c adi.c  rhs.c
     x_solve.c y_solve.c solve_subs.c
     z_solve.c add.c error.c verify.c" \
    "c_timers.bc wtime.bc print_results.bc" \
    "auto2_verify.c"

build_benchmark ep \
    $HOME/EP \
    "ep.c" \
    "print_results.bc randdp.bc c_timers.bc wtime.bc" \
    "auto2_verify.c"

build_benchmark ft \
    $HOME/FT \
    "appft.c auxfnct.c fft3d.c mainft.c verify.c" \
    "print_results.bc randdp.bc c_timers.bc wtime.bc" \
    "auto2_verify.c"

build_benchmark is \
    $HOME/IS \
    "is.c" \
    "c_print_results.bc c_timers.bc c_wtime.bc" \
    "auto2_verify.c"

build_benchmark lu \
    $HOME/LU \
    "lu.c read_input.c \
    domain.c setcoeff.c setbv.c exact.c setiv.c
    erhs.c ssor.c rhs.c l2norm.c
    jacld.c blts.c jacu.c buts.c error.c
    pintgr.c verify.c" \
    "print_results.bc c_timers.bc wtime.bc" \
    "auto2_verify.c"

build_benchmark sp \
    $HOME/SP \
    "sp.c initialize.c exact_solution.c exact_rhs.c
     set_constants.c adi.c rhs.c
     x_solve.c ninvr.c y_solve.c pinvr.c
     z_solve.c tzetar.c add.c txinvr.c error.c verify.c" \
    "print_results.bc c_timers.bc wtime.bc" \
    "auto2_verify.c"

