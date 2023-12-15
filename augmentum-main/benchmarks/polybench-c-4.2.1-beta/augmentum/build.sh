#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

NAME=$1 # name of the benchmark
CLASS=$2 # benchmark input problem size
HOME=$3 # benchmark suite home directory
SRC=$4 # benchmark source directory
BIN=$5 # binary file directory
BLD=$6 # build directory
VCLANG=$7 # vanilla compiler
MCLANG=$8 # modified compiler
EXTRA_CFLAGS=$9 # additional compiler flags
EXTRA_LFLAGS=${10} # additional linker flags
EXTENSION=${11} # augmentum compiler extension library

if [ ! -d $HOME ] ; then
    echo "ERROR: Specified benchmark home directory does not exist $HOME"
    exit 1
fi

if [ ! -d $SRC ] ; then
    echo "ERROR: Specified source directory does not exist $SRC"
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

UTILITY_DIR="${HOME}/utilities"

POLYBENCH_FLAGS="-DPOLYBENCH_DUMP_ARRAYS -DPOLYBENCH_USE_C99_PROTO"

CFLAGS="${POLYBENCH_FLAGS} -D${CLASS}_DATASET $EXTRA_CFLAGS"
LFLAGS="$EXTRA_LFLAGS"

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

# extra flags for polybench benchmark linking
declare -A EXTRA_FLAGS=( \
["cholesky"]="-lm" \
["gramschmidt"]="-lm" \
["correlation"]="-lm" \
)

printf "## Building binary for $NAME and Problem Size ${CLASS} in $BLD\n"

execute "cd $BLD"

printf "\nbuilding benchmark objects ...\n"
execute "${MCLANG} -c ${SRC}/${NAME}.c ${CFLAGS} ${EXT_FLAGS} -I${SRC} -I${UTILITY_DIR}" 
execute "${MCLANG} -c ${UTILITY_DIR}/polybench.c ${CFLAGS} ${EXT_FLAGS} -I. -I${UTILITY_DIR}" 

TARGET=$BIN/$NAME.$CLASS.x
printf "\nlinking final binary to ${TARGET}\n"
execute "${VCLANG} ${LFLAGS} -o ${TARGET} ${NAME}.o polybench.o ${EXTRA_FLAGS[$NAME]}"