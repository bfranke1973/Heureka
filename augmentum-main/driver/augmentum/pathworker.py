# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import shutil
from dataclasses import dataclass
from typing import Dict, Optional, Set, Union

import augmentum.paths as a2p
from augmentum.function import Function
from augmentum.priors import Prior, build_priors
from augmentum.probes import NullProbe
from augmentum.sysUtils import try_create_dir
from augmentum.timer import Timer
from mptools import EventMessage, QueueProcWorker

from augmentum.benchmarks import TestCase

logger = logging.getLogger(__name__)


@dataclass
class WorkerResult:
    prior_model: Prior
    obj_improvement: bool


class Task:
    def __init__(self, fn: Function, p: a2p.Path):
        self.function = fn
        self.path = p
        self.fn_test_cases = set()

        self.result: Optional[Union[WorkerResult, Dict[str, WorkerResult]]] = None

    def set_test_cases(self, selected_tests: Dict[str, Dict[str, Set[str]]]):
        if selected_tests.get(self.function.module) and selected_tests[
            self.function.module
        ].get(self.function.name):
            self.fn_test_cases = selected_tests[self.function.module][
                self.function.name
            ]

    def set_result(self, result: Union[WorkerResult, Dict[str, WorkerResult]]):
        self.result = result

    def __str__(self):
        return f"{self.function.module} {self.function} -- {self.path}"


@dataclass
class TaskCounter:
    counter: int


class PathWorker(QueueProcWorker):
    def init_args(self, args):
        logger.debug(f"Entering PathWorker.init_args : {args}")
        (
            self.work_q,
            self.sys_prog,
            self.benchmark_factory,
            self.test_baseline,
            self.objective_metric,
            self.working_dir,
            self.keep_probes,
            self.mem_limit,
            self.skip_immutables,
            self.independent_test_cases,
        ) = args

        # skip_immutables: skip paths that are not modified by the original code when executing null priors
        # independent_test_cases: if true, individual test cases are evaluated independently of each other
        #                         with a prior model for each

    def startup(self):
        logger.info(f"Path Worker started {self.name}")
        self.test_cases: Dict[
            str, TestCase
        ] = self.benchmark_factory.setup_benchmark_instance(self.working_dir)

        if self.mem_limit is not None:
            logger.info(
                f"Using probe compilation and run memory limit of {round(self.mem_limit, 2)} MB"
            )

    def shutdown(self):
        logger.info(f"Path Worker shutting down {self.name}")

        # clean up working dir
        if self.working_dir.exists() and not self.keep_probes:
            try:
                shutil.rmtree(self.working_dir)
            except OSError as e:
                logger.error("%s - %s." % (e.filename, e.strerror))

    def main_func(self, task: Task):
        logger.info(f"Evaluating {task}")

        if len(task.fn_test_cases) == 0:
            logger.info(f"No tests available for function {task.function}")
            self.event_q.put(EventMessage(self.name, "PATH_DONE", task))
            return

        if self.independent_test_cases:
            logger.info(
                f"Evaluating {len(task.fn_test_cases)} test cases individually ..."
            )

            worker_results: Dict[str, WorkerResult] = dict()
            for tc_id, tc_name in enumerate(task.fn_test_cases):
                logger.info(
                    f"Evaluating test case {tc_name} {tc_id + 1} / {len(task.fn_test_cases)} ..."
                )
                worker_results[tc_name] = self.evaluate_prior_model_for_tests(
                    task, {tc_name}
                )
            task.set_result(worker_results)

        else:
            logger.info(f"Evaluating {len(task.fn_test_cases)} test cases together ...")
            wres = self.evaluate_prior_model_for_tests(task, task.fn_test_cases)
            task.set_result(wres)

        self.event_q.put(EventMessage(self.name, "PATH_DONE", task))

    def evaluate_prior_model_for_tests(
        self, task: Task, fn_test_cases: Set[str]
    ) -> WorkerResult:
        # create a prior model based on a selected path
        prior_model = build_priors(task.function, task.path, self.skip_immutables)
        obj_improvement = False
        while not prior_model.is_done():
            probe = prior_model.select_next_probe()

            probe_wd = try_create_dir(self.working_dir / "probe_out", use_time=True)
            if not probe_wd:
                raise RuntimeError(
                    f"Creating probe working directory failed for {probe_wd}."
                )

            # extension library is generated depending on the type of the given probe
            with self.sys_prog.bind(probe, probe_wd, self.keep_probes) as bound_probe:
                for tc_name in fn_test_cases:
                    test_case = self.test_cases[tc_name]

                    # compile, execute, verify and measure for each test case
                    logger.info(f"Processing test case {tc_name} ...")

                    with Timer():
                        probe_result = bound_probe.process(
                            test_case, memory_limit=self.mem_limit
                        )

                    # update prior
                    prior_model.update(probe_result)

                    # update objective
                    if (
                        probe_result.is_exec_success()
                        and probe_result.objective is not None
                    ):
                        probe_score = probe_result.objective.score
                        baseline_score = self.test_baseline[tc_name].objective.score
                        probe_result.rel_objective = probe_score / baseline_score

                        if isinstance(
                            probe, NullProbe
                        ) and not self.objective_metric.equals(
                            probe_result.objective,
                            self.test_baseline[tc_name].objective,
                        ):
                            logger.warning(
                                f"Null Prior does not have same objective as baseline for test {tc_name}."
                            )

                        # check if we have seen an improvement so far
                        obj_improvement = (
                            obj_improvement
                            or self.objective_metric.is_improved(
                                probe_result.objective,
                                self.test_baseline[tc_name].objective,
                            )
                        )

                    logger.info(f"Probe Result: {probe_result}")

        return WorkerResult(prior_model, obj_improvement)
