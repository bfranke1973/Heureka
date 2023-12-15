#!/usr/bin/env python3

# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
The benchmark profiler compiles given benchmarks with a specified
compiler which is already instrumented.

It then traces all instrumented functions that were executed during
compilation for individual benchmarks and emits the result.
"""

import argparse
import csv
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from augmentum.__about__ import __version__
from augmentum.mplogging import LogListener, configure_root_logging
from augmentum.priors import ProbeResult
from augmentum.probes import TracerProbe
from augmentum.sysProg import BoundProbe
from augmentum.sysUtils import build_path_or_fail, try_create_dir
from augmentum.timer import Timer
from mptools import MainContext, default_signal_handler, init_signals

from augmentum.benchmarks import BenchmarkFactory, TestCase

logger = logging.getLogger(__name__)


class FnTracePoint:
    def __init__(self, module_name: str, function_name: str):
        self.mname = module_name
        self.fname = function_name
        # check if we are looking at a module from the transforms directory (LLVM SPECIFIC!)
        self.transforms = module_name.startswith("llvm/lib/Transforms/")
        self.count = 0

    def to_csv_row(self) -> Iterable[Any]:
        return [self.mname, self.fname, self.count, self.transforms]


class Profiler:
    def __init__(
        self,
        tools: Dict[str, Any],
        llvm_src_dir: Path,
        target_compiler_bld: Path,
        benchmark_factory: BenchmarkFactory,
        working_dir: Path,
        verbose: bool,
    ):
        self.tools = tools
        self.llvm_src_dir = llvm_src_dir
        self.target_compiler_bins = target_compiler_bld / "instrumented" / "bin"
        self.working_dir = working_dir
        self.verbose = verbose

        self.test_cases: Dict[
            str, TestCase
        ] = benchmark_factory.setup_benchmark_instance(working_dir)

        self.test_trace_out = None

    def absolute_module_to_relative(self, abs_module: str) -> str:
        return abs_module.replace(str(self.llvm_src_dir) + "/", "")

    def profile_test_cases(self):
        """Execute configured benchmarks with tracer probe and record executed functions."""

        probe_wd = try_create_dir(self.working_dir / "test_profiler", use_time=True)
        profiler_probe = BoundProbe(
            self.tools,
            probe_wd,
            self.target_compiler_bins,
            None,
            None,
            TracerProbe("benchmark_profiler"),
            True,
        )

        target_functions: Dict[str, FnTracePoint] = dict()
        for tc_name, test_case in self.test_cases.items():
            with Timer():
                # compile, execute and verify for each test case
                logger.info(f"\n\n####### Processing test case {tc_name} ...")
                probe_result = profiler_probe.process(test_case)

                logger.info(f"{len(probe_result.exec_log)} functions logged.")

                if probe_result.is_exec_success():
                    logger.info(f"Test case {tc_name} processing successful.")

                    # merge function traces to deduplicated list
                    for entry in probe_result.exec_log:
                        if len(entry) != 2:
                            raise RuntimeError("Unexpected probe log entry format!")

                        # absolute module to relative
                        module = self.absolute_module_to_relative(entry[0])
                        function = entry[1]

                        key = f"{module}::{function}"
                        if key not in target_functions:
                            target_functions[key] = FnTracePoint(module, function)
                        target_functions[key].count += 1

                else:
                    logger.warning(
                        f"Test case {tc_name} processing failed!\n{probe_result}"
                    )
                    probe_result = None

                self.emit_test_trace(test_case, probe_result)

        logger.info("\n-----------------\n")
        logger.info(f"{len(target_functions)} target functions identified.")

        self.emit_target_function_trace(target_functions)

    def emit_test_trace(self, test: TestCase, presult: Optional[ProbeResult]):
        """Emit function trace for given test to output file."""

        if not self.test_trace_out:
            TEST_TRACE_HEADER = ["test_case", "module", "function"]

            self.test_trace_out = self.working_dir / "test_trace.csv"

            with self.test_trace_out.open("w") as trace_out:
                trace_writer = csv.writer(trace_out, delimiter=";")
                trace_writer.writerow(TEST_TRACE_HEADER)

        logger.info(f"Emitting test trace to {self.test_trace_out} for case {test} ...")

        with self.test_trace_out.open("a") as trace_out:
            trace_writer = csv.writer(trace_out, delimiter=";")

            if presult:
                for mname_abs, fname in presult.exec_log:
                    mname_rel = self.absolute_module_to_relative(mname_abs)
                    trace_writer.writerow([str(test), mname_rel, fname])
            else:
                trace_writer.writerow([str(test), "NA", "NA"])

    def emit_target_function_trace(self, target_functions: Dict[str, FnTracePoint]):
        """Emit deduplicated function trace for all processed tests to output file."""

        FN_TRACE_HEADER = ["module", "function", "count", "transforms"]

        fn_trace_out = self.working_dir / "function_trace.csv"
        logger.info(f"Emitting function trace to {fn_trace_out} ...")

        with fn_trace_out.open("w") as fn_out:
            fn_writer = csv.writer(fn_out, delimiter=";")
            fn_writer.writerow(FN_TRACE_HEADER)

            for _, trace_point in target_functions.items():
                fn_writer.writerow(trace_point.to_csv_row())


def load_config(
    raw_config: Iterable[str],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Iterable[Dict[str, Any]]]:
    """Read configuration data from specified configuration file."""
    config = json.load(raw_config)

    g_cfg = config["general"]
    t_cfg = config["tools"]
    s_cfg = config["sys_prog"]["available"][config["sys_prog"]["active"]]
    b_cfgs = [
        config["benchmark"]["available"][b] for b in config["benchmark"]["active"]
    ]

    return g_cfg, t_cfg, s_cfg, b_cfgs


def setup_root_directory(run_id: str, wd: Path) -> Path:
    if not wd.exists():
        raise RuntimeError("Given working directory path invalid: " + str(wd))

    wd_run = wd / run_id
    wd_run.mkdir(exist_ok=False)
    return wd_run


def get_target_directories(sysprog_cfg: Dict[str, Any]) -> Tuple[Path, Path]:
    """
    return path to llvm source directory and directory with instrumented compiler binaries
    """
    sys_prog_src_dir = build_path_or_fail(sysprog_cfg["src_dir"])
    sys_prog_bld_dir = build_path_or_fail(sysprog_cfg["build_dir"])

    return sys_prog_src_dir, sys_prog_bld_dir


def parse_args():
    parser = argparse.ArgumentParser(
        description="Profile specified benchmark with instrumented compiler "
        "and record functions executed during compilation."
    )
    parser.add_argument(
        "--run_id",
        metavar="ID",
        type=str,
        required=True,
        help="ID used to identify this profiler execution.",
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
        help="Json file with environment and instrumented compiler configuration.",
    )
    parser.add_argument(
        "--loglevel",
        metavar="LEVEL",
        type=str,
        default="INFO",
        help="Configure log level.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Activate verbose program output."
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.working_dir.exists():
        raise RuntimeError("Given output path invalid: " + str(args.output))

    _, tools_cfg, sysprog_cfg, benchmark_cfgs = load_config(args.config)

    wd_run = setup_root_directory(args.run_id, args.working_dir)
    llvm_src_dir, target_compiler_bld = get_target_directories(sysprog_cfg)

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
        logger.info(f"Setting up working directory at: {wd_run} ...")

        benchmark_factory = BenchmarkFactory(
            tools_cfg, benchmark_cfgs, verbose=args.verbose
        )

        bench_profiler = Profiler(
            tools_cfg,
            llvm_src_dir,
            target_compiler_bld,
            benchmark_factory,
            wd_run,
            args.verbose,
        )
        bench_profiler.profile_test_cases()


if __name__ == "__main__":
    main()
