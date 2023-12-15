# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import csv
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple, Union

import augmentum.paths as a2p
from augmentum.function import Function, Module, build_modules
from augmentum.functionfilter import FunctionFilter
from augmentum.heuristicDB import HeuristicDB
from augmentum.objectives import ObjectiveMetric
from augmentum.pathworker import PathWorker, Task, TaskCounter, WorkerResult
from augmentum.sysProg import InstrumentationScope, SysProg
from augmentum.targetfilter import TargetFilter
from augmentum.testcasemanager import TestCaseManager
from augmentum.timer import Timer
from mptools import EventMessage, MainContext, MPQueue

from augmentum.benchmarks import BenchmarkFactory, TestCase

logger = logging.getLogger(__name__)


class Driver:
    def __init__(
        self,
        main_ctx: MainContext,
        tools: Dict[str, Any],
        wd_run: Path,
        wd_workers: Path,
        sys_prog: SysProg,
        benchmark_factory: BenchmarkFactory,
        objective_metric: ObjectiveMetric,
        function_filter: FunctionFilter,
        target_filter: Optional[TargetFilter],
        heuristicURL: Optional[str],
        cpus: int,
        instr_scope: InstrumentationScope,
        instr_chunk: int,
        function_cache: Optional[Path] = None,
        baseline_cache: Optional[Path] = None,
        keep_probes: bool = False,
        probe_mem_limit: Optional[int] = None,
        worker_mul: float = 1.0,
        exact_cpu_map: bool = False,
        dry_run: bool = False,
        no_instr: bool = False,
        record_exec_log: bool = False,
        skip_immutables: bool = False,
        independent_test_cases: bool = False,
    ):
        self.main_ctx = main_ctx
        self.tools = tools
        self.wd_workers = wd_workers
        self.sys_prog = sys_prog
        self.benchmark_factory = benchmark_factory
        self.function_filter = function_filter
        self.target_filter = target_filter

        self.cpus = cpus

        self.instr_scope = instr_scope
        self.instr_chunk = instr_chunk
        self.function_cache = function_cache
        self.baseline_cache = baseline_cache

        self.keep_probes = keep_probes
        self.probe_mem_limit = probe_mem_limit

        self.test_cases: Dict[
            str, TestCase
        ] = self.benchmark_factory.setup_benchmark_instance(self.wd_workers)
        self.tc_manager = TestCaseManager(
            self.tools, self.wd_workers, keep_probes=self.keep_probes
        )
        self.objective_metric = objective_metric

        self.worker_mul = worker_mul
        self.exact_cpu_map = exact_cpu_map

        self.dry_run = dry_run
        self.active_instrumentation = (
            not no_instr
        )  # deactivate instrumentation for debugging purposes
        self.record_exec_log = record_exec_log  # store all recorded probe values in db

        self.skip_immutables = skip_immutables
        self.independent_test_cases = independent_test_cases

        self.heuristicDB = self.setup_heuristic_dbs(heuristicURL, wd_run)

    def setup_heuristic_dbs(
        self, dbURL: Optional[str], wd_run: Path
    ) -> Union[Dict[str, HeuristicDB], HeuristicDB]:
        """Returns either a single database or a dictionary with a database for each available test case."""

        if self.independent_test_cases:
            # TODO come up with a better system
            # expecting either None or a template of the form sqlite:///some/path/some_name_#TEST#.sqlite
            # with #TEST# being a placeholder for testcase names

            PLACE_HOLDER = "#TEST#"

            if not dbURL:
                dbURL = f"sqlite:///{wd_run}/heuristic_data_{PLACE_HOLDER}.sqlite"

            assert (
                PLACE_HOLDER in dbURL
            ), f"Test case place holder {PLACE_HOLDER} expected in given URL {dbURL}"
            dbs = dict()
            for tc_name in self.test_cases.keys():
                tc_dbURL = dbURL.replace(PLACE_HOLDER, tc_name.replace(" ", "_"))
                dbs[tc_name] = HeuristicDB(tc_dbURL)
                logger.info(f"Loading heuristic database from {tc_dbURL} ...")
            return dbs

        else:
            if not dbURL:
                dbURL = f"sqlite:///{wd_run}/heuristic_data.sqlite"
            logger.info(f"Loading heuristic database from {dbURL} ...")
            return HeuristicDB(dbURL)

    def clean_up(self):
        """Clean up left over resources"""
        self.sys_prog.clear_existing_extension_pts()

    def send_event(self, source: str, type: str):
        if type in ["END", "DISPATCH"]:
            logger.debug(f"Queued {type} event")
            self.main_ctx.event_queue.safe_put(EventMessage(source, type, type))
        else:
            logger.warning(f"Unknown message type {type}")

    def load_functions(self) -> Iterable[Function]:
        """
        Collect target functions, deserialise and filter them.

        Use cached version if available.
        """

        if self.function_cache is not None and self.function_cache.exists():
            logger.info(
                "Loading cached target functions from "
                + str(self.function_cache)
                + " ..."
            )
            with self.function_cache.open("rb") as infile:
                target_functions = pickle.load(infile)
        else:
            # deserialises them and builds corresponding functions.
            target_functions = self.sys_prog.get_functions(self.function_filter)

            if self.function_cache is not None:
                logger.info(
                    "Caching target functions to " + str(self.function_cache) + " ..."
                )
                with self.function_cache.open("wb") as outfile:
                    pickle.dump(target_functions, outfile)

        return target_functions

    def build_evaluation_targets(
        self, modules: Dict[str, Module], db: HeuristicDB
    ) -> Dict[str, Dict[str, Dict[str, a2p.Path]]]:
        """Screen modules for functions with paths that have not yet been evaluated, accumulate and return."""
        INDICATOR_THRESHOLD = 50
        evaluation_targets = dict()

        # count functions for progress indicator
        total_functions = 0
        for mod in modules.values():
            total_functions += len(mod.functions)

        functions_processed = 0
        for m_name, mod in modules.items():
            functions_to_skip = []

            finished_path_lookup = db.get_evaluated_paths()

            for fn_name, fn in mod.functions.items():
                if (
                    total_functions > INDICATOR_THRESHOLD
                    and (functions_processed % INDICATOR_THRESHOLD) == 0
                ):
                    logger.info(
                        f"Functions processed {functions_processed}/{total_functions}"
                    )

                fn_paths = fn.get_paths()
                if self.target_filter is not None:
                    # generate possible function paths and apply target filter
                    fn_paths = [
                        p
                        for p in fn_paths
                        if self.target_filter.should_evaluate(m_name, fn_name, str(p))
                    ]

                # if the function has no paths to be evaluated, mark it and move on to the next function
                if len(fn_paths) == 0:
                    functions_to_skip.append(fn_name)
                    functions_processed += 1
                    continue

                target_paths = {}

                for p in fn_paths:
                    # add path as target if not yet evaluated
                    if (
                        not db.get_lookup_string(m_name, fn_name, p)
                        in finished_path_lookup
                    ):
                        target_paths[f"{p}"] = p

                if len(target_paths) > 0:
                    if m_name not in evaluation_targets:
                        evaluation_targets[m_name] = dict()
                    evaluation_targets[m_name][fn_name] = target_paths
                else:
                    functions_to_skip.append(fn_name)

                functions_processed += 1

            # remove unnecessary functions from module to reduce instrumentation overhead
            for fn_name in functions_to_skip:
                del mod.functions[fn_name]

        logger.info(f"Functions processed {functions_processed}/{total_functions}")
        return evaluation_targets

    def count_evaluation_targets(
        self, evaluation_targets: Dict[str, Dict[str, Dict[str, a2p.Path]]]
    ) -> Tuple[int, int, int]:
        m_count = len(evaluation_targets)
        fn_count = 0
        p_count = 0
        for _, fns in evaluation_targets.items():
            fn_count += len(fns)
            for _, paths in fns.items():
                p_count += len(paths)

        return m_count, fn_count, p_count

    def select_tasks(
        self,
        modules: Dict[str, Module],
        evaluation_targets: Dict[str, Dict[str, Dict[str, a2p.Path]]],
    ) -> Iterable[Task]:
        logger.debug(f"Selecting tasks from {self.instr_chunk} {self.instr_scope}...")

        tasks = []
        counter = self.instr_chunk

        for m_name, fns in evaluation_targets.items():
            if counter == 0:
                break
            for fn_name, paths in fns.items():
                if counter == 0:
                    break
                for _, path in paths.items():
                    if counter == 0:
                        break
                    tasks.append(Task(modules[m_name].functions[fn_name], path))
                    if self.instr_scope == InstrumentationScope.PATH:
                        counter -= 1
                if self.instr_scope == InstrumentationScope.FUNCTION:
                    counter -= 1
            if self.instr_scope == InstrumentationScope.MODULE:
                counter -= 1

        return tasks

    def dispatch_path_tasks(
        self,
        modules: Dict[str, Module],
        evaluation_targets: Dict[str, Dict[str, Dict[str, a2p.Path]]],
        task_q: MPQueue,
    ) -> TaskCounter:
        """
        Dispatch the next batch of tasks depending on the driver's instr_scope setting and instr_chunk size.
        PATH : select the next chunk of paths accross modules and functions
        FUNCTION : select all paths from the next chunk of functions accross modules
        MODULE : select all paths from all functions from the next chunk of modules
        ALL : select all paths from all functions in all modules (chunk size ignored)

        Instrument the system program for all functions corresponding to selected paths
        and select executed test cases.
        """
        tasks = self.select_tasks(modules, evaluation_targets)
        if len(tasks) == 0:
            logger.warning("No futher tasks available for dispatch. Shutting down ...")
            self.send_event("dispatch_path_tasks", "END")
            return TaskCounter(0)

        target_fns = {}
        for t in tasks:
            if t.function.module not in target_fns:
                target_fns[t.function.module] = set()
            target_fns[t.function.module].add(t.function.name)

        if self.active_instrumentation:
            self.sys_prog.instrument(target_fns)
        selected_tests = self.tc_manager.select_tests(
            target_fns.keys(), self.sys_prog, self.test_cases
        )

        logger.debug("Dispatching tasks ...")
        for t in tasks:
            t.set_test_cases(selected_tests)
            task_q.safe_put(t)

        counts = self.count_evaluation_targets(evaluation_targets)
        logger.info(
            f"Remaining work left {counts[0]} modules / {counts[1]} functions / {counts[2]} paths to be evaluated."
        )

        return TaskCounter(len(tasks))

    def record_results_to_db(
        self,
        m_name: str,
        fn_name: str,
        task: Task,
        wresult: Optional[WorkerResult],
        db: HeuristicDB,
        test_case_num: int,
    ):
        if wresult is not None:
            model_result = wresult.prior_model.prior_result()
            logger.info(f"Prior result for task '{task}'\n{model_result}")

            assert (
                model_result is not None
            ), "Result not expected to be None for return value from CompositePrior."

            # write results to data base
            db.add_path_heuristic(
                m_name,
                fn_name,
                task.path,
                model_result,
                wresult.obj_improvement,
                test_case_num,
            )
            db.add_probelog(
                m_name,
                fn_name,
                task.path,
                wresult.prior_model.get_probe_log(),
                record_exec_log=self.record_exec_log,
            )
            db.add_prior_results(m_name, fn_name, task.path, model_result.result_data)
        else:
            logger.warning(f"Task finished without results {task}")
            db.add_path_heuristic(
                m_name, fn_name, task.path, None, False, test_case_num
            )

    def process_task_results(
        self,
        eval_targets: Dict[str, Dict[str, Dict[str, a2p.Path]]],
        active_tasks: TaskCounter,
        event: EventMessage,
    ):
        # remove completed tasks from evaluation targets
        task: Task = event.msg
        m_name = task.function.module
        fn_name = task.function.name
        p_name = str(task.path)

        logger.info(f"Task processed for - '{task}'")

        if (
            m_name in eval_targets
            and fn_name in eval_targets[m_name]
            and p_name in eval_targets[m_name][fn_name]
        ):
            del eval_targets[m_name][fn_name][p_name]

            if len(eval_targets[m_name][fn_name]) == 0:
                logger.info(f"Function finished {fn_name}")
                del eval_targets[m_name][fn_name]

                if len(eval_targets[m_name]) == 0:
                    logger.info(f"Module finished {m_name}")
                    del eval_targets[m_name]

            active_tasks.counter -= 1
        else:
            logger.warning(f"Task finished which is no longer in task list {task}")

        if self.independent_test_cases:
            for tc_name, db in self.heuristicDB.items():
                # no test covers the target or the current task does not cover it
                if task.result is None or tc_name not in task.result:
                    self.record_results_to_db(m_name, fn_name, task, None, db, 0)
                else:
                    self.record_results_to_db(
                        m_name, fn_name, task, task.result[tc_name], db, 1
                    )
        else:
            self.record_results_to_db(
                m_name,
                fn_name,
                task,
                task.result,
                self.heuristicDB,
                len(task.fn_test_cases),
            )

        if len(eval_targets) == 0:
            self.send_event("process_task_results", "END")
        elif active_tasks.counter == 0:
            self.send_event("process_task_results", "DISPATCH")

    def emit_targets(
        self, evaluation_targets: Dict[str, Dict[str, Dict[str, a2p.Path]]]
    ):
        HEADER_FN = ["module", "function"]
        HEADER_FI = ["type", "module", "function", "path", "description"]

        target_fn_out = self.wd_workers / "target_functions.csv"
        target_fi_out = self.wd_workers / "target_filter.csv"
        logger.info(f"Emitting target functions to {target_fn_out} ...")
        logger.info(f"Emitting target filter to {target_fi_out} ...")

        with target_fn_out.open("w") as fn_out, target_fi_out.open("w") as fi_out:
            fn_writer = csv.writer(fn_out, delimiter=";")
            fi_writer = csv.writer(fi_out, delimiter=";")

            fn_writer.writerow(HEADER_FN)
            fi_writer.writerow(HEADER_FI)

            for mname, fns in evaluation_targets.items():
                for fname, paths in fns.items():
                    fn_writer.writerow([mname, fname])

                    for pname, _ in paths.items():
                        fi_writer.writerow(["ALLOW", mname, fname, pname, ""])

    def main_loop(self):
        functions = self.load_functions()

        modules = build_modules(functions)

        with Timer():
            logger.info(
                f"Building evaluation targets for {str(len(functions))} functions in {str(len(modules))} modules ..."
            )

            evaluation_targets: Dict[str, Dict[str, Dict[str, a2p.Path]]] = dict()
            if self.independent_test_cases:
                # TODO find a better way than simply using the first in the list
                db = self.heuristicDB[next(iter(self.heuristicDB))]
                evaluation_targets = self.build_evaluation_targets(modules, db)
            else:
                evaluation_targets = self.build_evaluation_targets(
                    modules, self.heuristicDB
                )

            counts = self.count_evaluation_targets(evaluation_targets)
            logger.info(
                f"Found total of {counts[0]} modules / {counts[1]} functions / {counts[2]} paths to be evaluated."
            )

        if self.dry_run:
            self.emit_targets(evaluation_targets)
            logger.info("Dry Run mode active. Shutting down.")
            return

        if len(evaluation_targets) == 0:
            logger.info("No tasks to be processed. Shutting down.")
            return

        test_baseline = self.tc_manager.measure_baseline(
            self.test_cases, self.objective_metric, self.baseline_cache
        )
        if test_baseline is None:
            logger.error(
                "Baseline could not be measured for tests as expected. Shutting down."
            )
            return

        # task queue used to list path tasks for workers
        task_q = self.main_ctx.MPQueue()

        # initialise path workers (a bit more than cpus available if mul is set)
        if self.exact_cpu_map:
            # reserve one for main thread and the rest for workers
            assert (
                self.cpus > 1
            ), "More than one cpus have to be configured if mapping exactly."
            worker_count = self.cpus - 1
            logger.info(
                "Exact core match: Reserving one core for Main Thread and remainder for Workers."
            )
        else:
            worker_count = int(self.cpus * self.worker_mul)

        logger.info(f"Starting {worker_count} path worker processes ...")
        for i in range(worker_count):
            worker_name = f"PATH_WORKER_{i}"
            working_dir = self.wd_workers / worker_name
            working_dir.mkdir(exist_ok=False)
            self.main_ctx.Proc(
                worker_name,
                PathWorker,
                task_q,
                self.sys_prog,
                self.benchmark_factory,
                test_baseline,
                self.objective_metric,
                working_dir,
                self.keep_probes,
                self.probe_mem_limit,
                self.skip_immutables,
                self.independent_test_cases,
            )

        self.send_event("evaluate_program", "DISPATCH")

        active_tasks = TaskCounter(0)
        while not self.main_ctx.shutdown_event.is_set():
            event = self.main_ctx.event_queue.safe_get()
            if not event:
                continue
            elif event.msg_type == "DISPATCH":
                active_tasks = self.dispatch_path_tasks(
                    modules, evaluation_targets, task_q
                )
                logger.info(f"Dispatched {active_tasks} tasks")
            elif event.msg_type == "PATH_DONE":
                self.process_task_results(evaluation_targets, active_tasks, event)
            elif event.msg_type == "FATAL":
                logger.info(f"Fatal Event received: {event.msg}")
                break
            elif event.msg_type == "END":
                logger.info(f"Shutdown Event received: {event.msg}")
                break
            else:
                logger.error(f"Unknown Event: {event}")

        counts = self.count_evaluation_targets(evaluation_targets)
        logger.info(
            f"Work left after finishing {counts[0]} modules / {counts[1]} functions / {counts[2]} paths to be evaluated."
        )
        self.clean_up()
