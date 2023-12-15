#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

AUGMENTUM_HOME=`git rev-parse --show-toplevel`

WORKING_DIR=/path/to/working_dir
CFG_DIR=${AUGMENTUM_HOME}/driver/config

CONFIG=${CFG_DIR}/evaluation_config.json

VERBOSE="--verbose --loglevel DEBUG"

RUN_ID=profiler_run_$(date +"%Y-%m-%d_%H-%M-%S")


CMD="${AUGMENTUM_HOME}/driver/benchmark_profiler.py
        --run_id ${RUN_ID}
        --working_dir ${WORKING_DIR}
        --config ${CONFIG}
        ${VERBOSE}"

echo ${CMD}
${CMD}
