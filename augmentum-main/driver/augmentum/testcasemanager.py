# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Collection of methods to manage test cases"""

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, Optional, Set

from augmentum.objectives import ObjectiveMetric
from augmentum.priors import ProbeResult
from augmentum.probes import BaselineProbe, TracerProbe
from augmentum.sysProg import BoundProbe, SysProg
from augmentum.sysUtils import try_create_dir

from augmentum.benchmarks import TestCase

logger = logging.getLogger(__name__)


class TestCaseManager:
    def __init__(
        self, tools: Dict[str, Any], wd_workers: Path, keep_probes: bool = False
    ):
        self.tools = tools
        self.wd_workers = wd_workers
        self.keep_probes = keep_probes

    def measure_baseline(
        self,
        test_cases: Dict[str, TestCase],
        objective_metric: ObjectiveMetric,
        baseline_cache: Optional[Path] = None,
    ) -> Optional[Dict[str, ProbeResult]]:
        """
        compile, run and verify each benchmark test case once,
        record required results and save as baseline for that benchmark

        Baseline results is loaded from cache if baseline_cache exists, otherwise
        it is saved at the specified location. If no baseline_cache is specified,
        caching is skipped.

        returns a association of test case names to baseline ProbeResults or None if failure
        """

        if baseline_cache is not None and baseline_cache.exists():
            logger.info("Loading cached baseline from " + str(baseline_cache) + " ...")
            with baseline_cache.open("rb") as infile:
                return pickle.load(infile)

        logger.info(
            f"Measuring baseline for {len(test_cases)} available test cases ..."
        )

        probe_wd = try_create_dir(self.wd_workers / "baseline", use_time=True)
        if not probe_wd:
            raise RuntimeError(
                f"Creating probe working directory failed for {probe_wd}."
            )

        test_baseline = dict()

        # create BoundProbe directly without binding it to a system program
        # so you can pass in the unmodified vanilla compiler for all compilations
        vanilla_compiler_bins = Path(self.tools["compiler_bin"])

        bound_probe = BoundProbe(
            self.tools,
            probe_wd,
            vanilla_compiler_bins,
            None,
            objective_metric,
            BaselineProbe(),
            self.keep_probes,
            build_extension=False,
        )

        for tc_name, test_case in test_cases.items():
            # compile, execute, verify and measure for each test case
            logger.info("Processing test case " + tc_name + " ...")
            probe_result = bound_probe.process(test_case)

            logger.info(f"Probe Result for test case baseline: {probe_result}")

            if not probe_result.is_exec_success():
                logger.error(
                    f"Test failed during baseline execution for test {tc_name}"
                    + "\n"
                    + str(probe_result)
                )
                return None

            probe_result.rel_objective = 1.0  # baseline
            test_baseline[tc_name] = probe_result

            if probe_result.objective.score == 0:
                logger.error(
                    f"Objective baseline is zero for test {tc_name}. "
                    "Zero baseline is not valid for future processing."
                )
                return None

        # cache baseline to file
        if baseline_cache is not None:
            logger.info("Caching baseline to " + str(baseline_cache) + " ...")
            with baseline_cache.open("wb") as outfile:
                pickle.dump(test_baseline, outfile)

        return test_baseline

    def select_tests(
        self,
        target_modules: Set[str],
        sys_prog: SysProg,
        test_cases: Dict[str, TestCase],
    ) -> Dict[str, Dict[str, Set[str]]]:
        """
        Select tests cases for target functions in a set of given modules
        that actually execute corresponding functions.

        To successfully execute this function, all relevant functions for
        test case selection should have been instrumented beforehand.
        """
        logger.info(
            "Selecting test cases for target functions in instrumented module ..."
        )

        probe_wd = try_create_dir(self.wd_workers / "test_select", use_time=True)
        if not probe_wd:
            raise RuntimeError(
                f"Creating probe working directory failed for {probe_wd}."
            )

        with sys_prog.bind(
            TracerProbe("test selection"), probe_wd, self.keep_probes
        ) as bound_probe:
            selected_tests = dict()
            for tc_name, test_case in test_cases.items():
                # compile, execute, verify and measure for each test case
                logger.info("Processing test case " + tc_name + " ...")
                probe_result = bound_probe.process(test_case)

                logger.info(f"Probe Result for test case selection: {probe_result}")

                if not probe_result.is_exec_success():
                    raise RuntimeError(
                        f"Test failed during selection for test {tc_name}"
                        + "\n"
                        + str(probe_result)
                    )

                count = 0
                for log_entry in probe_result.exec_log:
                    if len(log_entry) != 2:
                        raise RuntimeError("Unexpected probe log entry format!")

                    exec_mod = sys_prog.absolute_module_to_relative(log_entry[0])
                    if exec_mod in target_modules:
                        exec_fn = log_entry[1]

                        if exec_mod not in selected_tests:
                            selected_tests[exec_mod] = dict()

                        if exec_fn not in selected_tests[exec_mod]:
                            selected_tests[exec_mod][exec_fn] = set()

                        if tc_name not in selected_tests[exec_mod][exec_fn]:
                            selected_tests[exec_mod][exec_fn].add(tc_name)
                            count += 1
                    else:
                        logger.warning(
                            "Instrumentation fragments from different module found: "
                            + exec_mod
                            + " Consider clean build!"
                        )

                logger.info(f"{count} functions executed by {tc_name} test case.")

        return selected_tests
