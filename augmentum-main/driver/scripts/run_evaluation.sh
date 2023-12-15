#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# run single job or multiple parallel jobs
# use pkill driver to cancel all jobs

AUGMENTUM_HOME=`git rev-parse --show-toplevel`

# configure number of jobs
JOBS=1
CPUS=$(nproc --all)
CPU_PER_JOB=$(expr ${CPUS} / ${JOBS})

run_driver() {
        JOB_ID=$1
        CPUS=$2
        WORKING_DIR=/path/to/working_dir
        CFG_DIR=${AUGMENTUM_HOME}/driver/config
        CONFIG=${AUGMENTUM_HOME}/evaluation_config.json

        VERBOSE="--verbose --loglevel DEBUG"
        KEEP_PROBES="--keep_probes"
        SKIP_IMM="--skip_immutables"
#        INDY_TESTS="--independent_test_cases"
#        RECORD_EXEC_LOG="--record_exec_log"
#        DRY_RUN="--dry_run"
#        NO_INSTR="--no_instr"
#        SQL_DB="--heuristicDB sqlite:///${WORKING_DIR}/heuristic_data.sqlite"

#        BFILTER="--bmark_filter SNU_NPB#bt"

        FUN_CACHE="--function_cache ${CFG_DIR}/function_cache.pickle"
        BASE_CACHE="--baseline_cache ${CFG_DIR}/baseline_cache.pickle"
        TARGET_FUNS="--target_function ${CFG_DIR}/target_functions.csv"
#        TARGET_FILTER="--target_filter ${CFG_DIR}/target_filter.csv"

        CHUNK_SIZE="--fn_chunk_size 5000000"
        CHUNK_OFFSET="--fn_chunk_offset ${JOB_ID}"

        CPU_COUNT="--cpus ${CPUS}"
#        EXACT_MAP="--exact_cpu_map"
        MEM_LIMIT="--probe_mem_limit 2048"

        RUN_ID=eval_run_${JOB_ID}_$(date +"%Y-%m-%d_%H-%M-%S")

        CMD="${AUGMENTUM_HOME}/driver/function_analyser.py
                --run_id ${RUN_ID}
                --working_dir ${WORKING_DIR}
                --config ${CONFIG}
                --instr_scope ALL
                --instr_chunk 1
                ${SKIP_IMM}
                ${MEM_LIMIT}
                ${SQL_DB}
                ${TARGET_FUNS}
                ${TARGET_FILTER}
                ${CHUNK_SIZE}
                ${CHUNK_OFFSET}
                ${FUN_CACHE}
                ${BASE_CACHE}
                ${CPU_COUNT}
                ${EXACT_MAP}
                ${DRY_RUN}
                ${NO_INSTR}
                ${RECORD_EXEC_LOG}
                ${VERBOSE}
                ${KEEP_PROBES}
                ${INDY_TESTS}
                ${BFILTER}"

        echo ${CMD}
        ${CMD}
}
export -f run_driver

# if we have more than one job, run in parallel on the local machine
if [[ ${JOBS} -gt 1 ]]; then
        echo "Running ${JOBS} jobs in parallel ..."
        parallel run_driver ::: $(seq 0 $(expr ${JOBS} - 1)) ::: ${CPU_PER_JOB}
else
        echo "Running single job ..."
        run_driver 0 ${CPU_PER_JOB}
fi
