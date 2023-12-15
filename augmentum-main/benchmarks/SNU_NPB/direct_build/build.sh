#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

NAME=$1 # name of the benchmark
CLASS=$2 # benchmark input class
HOME=$3 # NAS benchmark suite home directory
BIN=$4 # binary file directory
BLD=$5 # build directory
VCLANG=$6 # vanilla compiler
MCLANG=$7 # modified compiler
EXTRA_CFLAGS=$8 # additional compiler flags
EXTRA_LFLAGS=$9 # additional linker flags
EXTENSION=${10} # augmentum compiler extension library

if [ ! -d $HOME ] ; then
    echo "ERROR: Specified benchmark home directory does not exist $HOME"
    exit 1
fi

if [ ! -d $BIN ] ; then
    echo "ERROR: Specified binary directory does not exist $BIN"
    exit 1
fi

if [ ! -d $BLD ] ; then
    echo "ERROR: Specified build directory does not exist $BLD"
    exit 1
fi

if [ ! -f $VCLANG ] ; then
    echo "ERROR: Specified compiler does not exist $VCLANG"
    exit 1
fi

if [ ! -f $MCLANG ] ; then
    echo "ERROR: Specified compiler does not exist $MCLANG"
    exit 1
fi

if [ ! -z "$EXTENSION" ] && [ ! -f $EXTENSION ] ; then
    echo "ERROR: Specified extension file not found $EXTENSION"
    exit 1
fi

SYS=$HOME/sys
COMMON=$HOME/common
DIR=$HOME/${NAME^^} # upper case name for benchmark source directory

CFLAGS="-Wall -mcmodel=medium $EXTRA_CFLAGS"
LFLAGS="-mcmodel=medium -lm $EXTRA_LFLAGS"

if [[ ! -z "$EXTENSION" ]]; then
    EXT_FLAGS="-Xclang -load -Xclang $EXTENSION"
else
    EXT_FLAGS=""
fi

function execute {
    CMD=$1
    echo $CMD
    $CMD
}

function build_benchmark {
    SRC=$1 # list of benchmark source files
    CMN=$2 # list of common source files
    VFY=$3 # list of source files used for verification

    printf "## Building binary for $NAME and Class $CLASS in $BLD\n"

    # build param tool
    # generate header parameters from make config
    # make config is irrelevant for our purposes though
    execute "gcc -o $SYS/setparams $SYS/setparams.c"

    execute "cd $DIR"
    execute "../sys/setparams $NAME $CLASS"
    execute "cd $BLD"

    printf "\nbuilding benchmark objects ...\n"
    for file in $SRC; do
        execute "$MCLANG $CFLAGS $EXT_FLAGS -c -I$COMMON -I$DIR $DIR/$file"
    done

    printf "\nbuilding common objects ...\n"
    for file in $CMN; do
        execute "$MCLANG $CFLAGS $EXT_FLAGS -c -I$COMMON $COMMON/$file"
    done

    # verification files are not build using a modified compiler
    printf "\nbuilding external verification objects ...\n"
    if [[ ! -z $VFY ]]; then
        for file in $VFY; do
            execute "$VCLANG $CFLAGS -c -I$DIR $DIR/$file"
        done
    fi

    TARGET=$BIN/$NAME.$CLASS.x
    printf "\nlinking final binary to $TARGET\n"
    execute "$VCLANG $LFLAGS -o $TARGET ${SRC//.c/.o} ${CMN//.c/.o} ${VFY//.c/.o}"
}

# class must be upper case
CLASS=${CLASS^^}
# name must be lower case
NAME=${NAME,,}

case "$NAME" in

"bt") build_benchmark \
    "bt.c initialize.c exact_solution.c exact_rhs.c
     set_constants.c adi.c  rhs.c
     x_solve.c y_solve.c solve_subs.c
     z_solve.c add.c error.c verify.c" \
    "c_timers.c wtime.c print_results.c" \
    "auto2_verify.c"
    ;;
"mg") build_benchmark \
    "mg.c" \
    "print_results.c randdp.c c_timers.c wtime.c" \
    "auto2_verify.c"
    ;;
"cg") build_benchmark \
    "cg.c" \
    "print_results.c randdp.c c_timers.c wtime.c" \
    "auto2_verify.c"
    ;;
"ep") build_benchmark \
    "ep.c" \
    "print_results.c randdp.c c_timers.c wtime.c" \
    "auto2_verify.c"
    ;;
"ft") build_benchmark \
    "appft.c auxfnct.c fft3d.c mainft.c verify.c" \
    "print_results.c randdp.c c_timers.c wtime.c" \
    "auto2_verify.c"
    ;;
"is") build_benchmark \
    "is.c" \
    "c_print_results.c c_timers.c wtime.c" \
    "auto2_verify.c"
    ;;
"lu") build_benchmark \
    "lu.c read_input.c \
    domain.c setcoeff.c setbv.c exact.c setiv.c
    erhs.c ssor.c rhs.c l2norm.c
    jacld.c blts.c jacu.c buts.c error.c
    pintgr.c verify.c" \
    "print_results.c c_timers.c wtime.c" \
    "auto2_verify.c"
    ;;
"sp") build_benchmark \
    "sp.c initialize.c exact_solution.c exact_rhs.c
     set_constants.c adi.c rhs.c
     x_solve.c ninvr.c y_solve.c pinvr.c
     z_solve.c tzetar.c add.c txinvr.c error.c verify.c" \
    "print_results.c c_timers.c wtime.c" \
    "auto2_verify.c"
    ;;
*) echo "ERROR Unknown benchmark name $NAME"
   exit 1
   ;;

esac
