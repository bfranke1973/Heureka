#!/usr/bin/env python3

# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import csv
import logging
import os
from pathlib import Path
from typing import Iterable, Optional, Tuple

from augmentum.__about__ import __version__
from augmentum.augmentumUtils import (
    load_evaluation_config,
    setup_root_directory,
    setup_working_directories,
)
from augmentum.functionfilter import InstrumentDefault, InstrumentFunctionList
from augmentum.mplogging import LogListener, configure_root_logging
from augmentum.objectives import CodeSizeObjective
from augmentum.sysProg import InstrumentationScope, SysProg
from augmentum.sysUtils import KVListAction, check_arg_list
from augmentum.targetfilter import TargetFilter
from mptools import MainContext, default_signal_handler, init_signals

from augmentum.benchmarks import BenchmarkFactory
from augmentum.driver import Driver

logger = logging.getLogger(__name__)


def load_target_functions(
    tfn_file: Iterable[str], chunk_size: Optional[int], chunk_offset: Optional[int]
) -> Optional[Iterable[Tuple[str, str]]]:
    """Load specified chunk of target functions from specified file."""
    if not tfn_file:
        return None

    reader = csv.reader(tfn_file, delimiter=";")
    next(reader, None)  # skip the headers
    tfn_entries = [(row[0], row[1]) for row in reader]

    if (chunk_size and chunk_offset is None) or (chunk_size is None and chunk_offset):
        raise RuntimeError(
            "--fn_chunk_size and --fn_chunk_offset "
            "must both be used or none of them."
        )

    if chunk_size is not None and chunk_offset is not None:
        start = chunk_offset * chunk_size
        end = start + chunk_size
        if start >= len(tfn_entries):
            logger.warning("Target function offset too high, nothing to do!")
            return []
        if end >= len(tfn_entries):  # return rest
            return tfn_entries[start:]
        else:  # return selected chunk
            return tfn_entries[start:end]
    else:
        return tfn_entries


def parse_args():
    """Specification and parsing of command line arguments."""
    parser = argparse.ArgumentParser(
        description="Driver to evaluate priors for target functions in a specified system program."
    )
    parser.add_argument(
        "--run_id",
        metavar="ID",
        type=str,
        required=True,
        help="ID used to identify this evaluation execution.",
    )
    parser.add_argument(
        "--working_dir",
        metavar="DIR",
        type=Path,
        required=True,
        help="Directory for generated data.",
    )
    parser.add_argument(
        "--config",
        metavar="JSON",
        type=argparse.FileType("r"),
        required=True,
        help="Json file with evaluation configuration.",
    )
    parser.add_argument(
        "--heuristicDB",
        metavar="URL",
        type=str,
        help="SQL DB indicating previously collected information about heuristic statistics.",
    )
    parser.add_argument(
        "--function_cache",
        metavar="FILE",
        type=Path,
        help="File path to target function cache. "
        "If file does not exist, a cache will be create after colleting functions.",
    )
    parser.add_argument(
        "--baseline_cache",
        metavar="FILE",
        type=Path,
        help="File path to baseline statistics cache. "
        "If file does not exist, a cache will be create after measuring baselines.",
    )

    parser.add_argument(
        "--bmark_filter",
        metavar="SUITE#B1,B2,B3...",
        nargs="*",
        type=str,
        action=KVListAction,
        help="List of manually specified benchmarks using key value lists "
        "<suite#name1,name2,name3>, e.g. POLYBENCH#correlation,lu",
    )

    parser.add_argument(
        "--target_functions",
        metavar="FILE",
        type=argparse.FileType("r"),
        help="A specific list of target function names to be instrumented.",
    )
    parser.add_argument(
        "--target_filter",
        metavar="FILE",
        type=argparse.FileType("r"),
        help="A specific list with block and allow rules for evaluation targets.",
    )
    parser.add_argument(
        "--fn_chunk_size",
        metavar="SIZE",
        type=int,
        help="Number of functions to be evaluated by this evaluation run. (considered only if --target_functions is used)",
    )
    parser.add_argument(
        "--fn_chunk_offset",
        metavar="OFFSET",
        type=int,
        help="Start offset for functions to be evaluated. (considered only if --target_functions is used)",
    )

    parser.add_argument(
        "--instr_scope",
        metavar="VALUE",
        type=lambda scope: check_arg_list(
            parser,
            scope,
            ["PATH", "FUNCTION", "MODULE", "ALL"],
            "Invalid instrumentation scope!",
        ),
        default="FUNCTION",
        help="Scope of instrumentation to be used [FUNCTION, MODULE, ALL].",
    )
    parser.add_argument(
        "--instr_chunk",
        metavar="VALUE",
        type=int,
        default=1,
        help="Chunk size of for instrumentation scope.",
    )

    parser.add_argument(
        "--keep_probes",
        action="store_true",
        help="Keep probe code and probe folders around. ATTENTION: disk space intensive for long runs.",
    )

    parser.add_argument(
        "--cpus",
        metavar="VALUE",
        type=int,
        help="Number of available CPUs for this run.",
    )
    parser.add_argument(
        "--worker_mul",
        metavar="VALUE",
        type=float,
        default=1.0,
        help="Number of workers is the configured cpus times this multiplier.",
    )
    parser.add_argument(
        "--exact_cpu_map",
        action="store_true",
        help="If this flag is active, workers and main thread are mapped exactly to the number of cpus."
        " worker_mul flag is ignored and cpus has to be larger 1.",
    )
    parser.add_argument(
        "--probe_mem_limit",
        metavar="VALUE",
        type=float,
        default=None,
        help="Memory limit in MB granted to each probe compilation and probe run.",
    )
    parser.add_argument(
        "--loglevel",
        metavar="LEVEL",
        type=str,
        default="INFO",
        help="Configure log level.",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="If this flag is active, the amount of work left to do for the given configuration is evaluated and no analysis is executed.",
    )
    parser.add_argument(
        "--skip_immutables",
        action="store_true",
        help="If this flag is active, immutable function parameter paths are skipped after Null Prior.",
    )
    parser.add_argument(
        "--independent_test_cases",
        action="store_true",
        default=False,
        help="If this flag is active, test cases are considered as independent applications.",
    )
    parser.add_argument(
        "--no_instr",
        action="store_true",
        help="Deactivate instrumentation for debugging purposes.",
    )
    parser.add_argument(
        "--record_exec_log",
        action="store_true",
        help="If active, all probed values are stored in the database.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Activate verbose program output."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    general_cfg, tools_cfg, sysprog_cfg, benchmark_cfgs = load_evaluation_config(
        args.config
    )

    wd_run = setup_root_directory(args.run_id, args.working_dir)

    # setup two main contexts to keep logging running during shutdown of the worker context
    with MainContext() as log_ctx:
        init_signals(
            log_ctx.shutdown_event, default_signal_handler, default_signal_handler
        )

        # configure logging
        log_q = log_ctx.MPQueue()
        log_ctx.Proc(
            "LOG_LISTENER", LogListener, log_q, wd_run / "run.log", args.loglevel
        )
        configure_root_logging(log_q, args.loglevel)

        if "HOSTNAME" in os.environ:
            host = os.environ["HOSTNAME"]
        else:
            host = "localhost"
        logger.info(f"Running function analyser {__version__} on host {host}")
        logger.info("Setting up working directory at: " + str(wd_run) + "...")

        with MainContext() as main_ctx:
            init_signals(
                main_ctx.shutdown_event, default_signal_handler, default_signal_handler
            )

            wd_workers, sys_prog_src_dir, sys_prog_bld_dir = setup_working_directories(
                wd_run, general_cfg, sysprog_cfg
            )

            cpus = args.cpus
            if cpus <= 0:
                raise ValueError(f"Given cpu count must be larger zero but is: {cpus}")
            if args.exact_cpu_map and cpus == 1:
                raise ValueError(
                    "Given cpu count must be larger one if "
                    f"exact_cpu_map is configured but is: {cpus}"
                )

            logger.info(f"Using {cpus} cpus for this run.")

            objective_metric = CodeSizeObjective(Path(tools_cfg["llvm-size"]))
            opt_program = SysProg(
                tools_cfg,
                sysprog_cfg,
                sys_prog_src_dir,
                sys_prog_bld_dir,
                objective_metric,
                cpus,
                verbose=args.verbose,
            )
            benchmark_factory = BenchmarkFactory(
                tools_cfg,
                benchmark_cfgs,
                verbose=args.verbose,
                bfilter=args.bmark_filter,
            )

            # setup function filter
            target_functions = load_target_functions(
                args.target_functions, args.fn_chunk_size, args.fn_chunk_offset
            )
            if target_functions is not None:
                logger.info(
                    "Using target function list from " + args.target_functions.name
                )
                function_filter = InstrumentFunctionList(target_functions)
            else:
                function_filter = InstrumentDefault()

            if args.target_filter:
                target_filter = TargetFilter(args.target_filter)
                logger.info("Using target filter rules from " + args.target_filter.name)
            else:
                target_filter = None

            instr_scope = InstrumentationScope[args.instr_scope]
            instr_chunk = args.instr_chunk

            driver = Driver(
                main_ctx,
                tools_cfg,
                wd_run,
                wd_workers,
                opt_program,
                benchmark_factory,
                objective_metric,
                function_filter,
                target_filter,
                args.heuristicDB,
                cpus,
                instr_scope,
                instr_chunk,
                function_cache=args.function_cache,
                baseline_cache=args.baseline_cache,
                keep_probes=args.keep_probes,
                probe_mem_limit=args.probe_mem_limit,
                worker_mul=args.worker_mul,
                exact_cpu_map=args.exact_cpu_map,
                dry_run=args.dry_run,
                no_instr=args.no_instr,
                record_exec_log=args.record_exec_log,
                skip_immutables=args.skip_immutables,
                independent_test_cases=args.independent_test_cases,
            )

            driver.main_loop()
