# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import gc
import logging
import shutil
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, Optional, Set

import augmentum.sysProgBuilders
from augmentum.function import (
    Function,
    FunctionData,
    NamedStructData,
    function_stats_id,
    load_named_structs,
    load_target_function_stats,
    named_struct_stats_id,
)
from augmentum.functionfilter import FunctionFilter
from augmentum.objectives import ObjectiveMetric
from augmentum.priors import ProbeResult
from augmentum.probes import PROBE_LOG_DELIMITER, ProbeBase
from augmentum.sysUtils import run_command, touch_existing_file
from augmentum.timer import Timer
from augmentum.type_serialisation import DeserialisationContext, TypeDeserialiser

from augmentum.benchmarks import ExecutionResult, TestCase

logger = logging.getLogger(__name__)


class ProbeExtension:
    extension_compile_cmd = (
        "{cxx} -O3 -std=c++17 -fPIC -I{augmentum_inc} -c {extend_path}/{extend_file}.cpp -o {extend_path}/{extend_file}.o && "
        "{cxx} -shared -fPIC -laugmentum -L{augmentum_lib} -Wl,-rpath,{augmentum_lib} {extend_path}/{extend_file}.o -o {extend_path}/lib{extend_file}.so"
    )
    extension_lib_target = "{extend_path}/lib{extend_file}.so"

    """Extension code needed for a specific probe"""

    def __init__(self, code: str):
        self.code = code

    def build_library(self, working_dir: Path, tools: Dict[str, Any]) -> Path:
        """Compile the extension code into a dynamic library and return corresponding path"""

        src_file = working_dir / Path("extension.cpp")
        if src_file.exists():
            raise FileExistsError(src_file)

        with open(src_file, "w") as f:
            f.write(self.code)

        returncode, stdout = run_command(
            ProbeExtension.extension_compile_cmd.format(
                cxx=tools["cxx"],
                augmentum_inc=tools["augmentum_headers"],
                augmentum_lib=tools["augmentum_library"],
                extend_path=str(src_file.parent),
                extend_file=src_file.stem,
            ),
            verbose=True,
        )
        if returncode != 0:
            logger.info(stdout)
            raise RuntimeError("Error building extension library from " + str(src_file))

        return Path(
            ProbeExtension.extension_lib_target.format(
                extend_path=str(src_file.parent), extend_file=src_file.stem
            )
        )


class BoundProbe:
    """
    Bind a probe to an instrumentation and corresponding extension. It can then be
    processed for different test cases and their outcome recorded.
    """

    NEXT_PROBE_OUTPUT_PATH_ID = 0

    def __init__(
        self,
        tools: Dict[str, Any],
        working_dir: Path,
        sys_prog_bins: Path,
        sys_prog_src: Optional[Path],
        objective_metric: Optional[ObjectiveMetric],
        probe: ProbeBase,
        keep_probes: bool = False,
        build_extension: bool = True,
    ):
        self.tools = tools
        self.sys_prog_bins = sys_prog_bins
        self.sys_prog_src = sys_prog_src
        self.objective_metric = objective_metric
        self.probe = probe
        self.keep_probes = keep_probes
        self.wd_path = working_dir
        self.log_file = self.wd_path / "probe.log"

        self.write_path_description()

        self.extension_lib = self.build_extension() if build_extension else None

    def __enter__(self) -> "BoundProbe":
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up probe folder"""
        if self.wd_path.exists() and not self.keep_probes:
            try:
                shutil.rmtree(self.wd_path)
            except OSError as e:
                logger.error(
                    "Cleaning up bound probe failed: %s - %s."
                    % (e.filename, e.strerror)
                )

    def build_extension(self) -> Path:
        extension = ProbeExtension(
            self.probe.extension_code(self.log_file, self.sys_prog_src)
        )
        return extension.build_library(self.wd_path, self.tools)

    def write_path_description(self):
        description_file = self.wd_path / "description.info"
        with description_file.open("w") as f:
            f.write(self.probe.get_description())

    def process(
        self, test_case: TestCase, memory_limit: Optional[int] = None
    ) -> ProbeResult:
        # if all went well, return measured objective and logged probe results
        result = ProbeResult(self.probe, test_case)

        exec_timer = Timer()
        # compile test case with extensions
        exec_timer.start()
        result.compile_ok = test_case.compile(
            self.sys_prog_bins, self.extension_lib, memory_limit=memory_limit
        )
        result.compile_time = exec_timer.stop()

        if result.compile_ok == ExecutionResult.SUCCESS:
            # run given test case and measure objective if objective specified
            exec_timer.start()
            if self.objective_metric:
                # TODO find a better way to capture the objective without having it call test_case.run
                result.run_ok, result.objective = self.objective_metric.measure(
                    test_case, memory_limit=memory_limit
                )
            else:
                result.run_ok, result.objective = (
                    test_case.run(memory_limit=memory_limit),
                    None,
                )
            result.run_time = exec_timer.stop()

            if result.run_ok == ExecutionResult.SUCCESS:
                # check semantics
                result.verify_ok = test_case.verify()

            if (
                result.run_ok != ExecutionResult.SUCCESS
                or result.verify_ok != ExecutionResult.SUCCESS
            ):
                result.objective = (
                    None  # don't record objective for faulty run or verification
                )

            # save path to extension file if probes are kept around
            if self.keep_probes:
                result.ext_path = self.extension_lib

            self.consume_probe_log(result.exec_log, self.log_file)

        # clean up probe execution log before returning
        self.log_file.unlink(missing_ok=True)

        return result

    def consume_probe_log(self, exec_log: Iterable[Iterable[str]], log_file: Path):
        """
        Probe log is a line of delimited values depending on the executed extension.
        This functions splits all lines found in the log file and adds them to the result
        entry.
        """
        if log_file.exists():
            with log_file.open(mode="r") as f:
                for line in f:
                    if line.strip() != "":
                        entry = line.strip().split(PROBE_LOG_DELIMITER)
                        exec_log.append(entry)


class InstrumentationScope(Enum):
    PATH = (
        0  # instrument a given chunk of paths at a time accross functions and modules
    )
    FUNCTION = 1  # instrument target function only in specified module
    MODULE = 2  # instrument all target functions in a module going one module at a time
    ALL = 3  # instrument all selected target functions in all modules at once


class SysProg:
    """An instrumentable system program"""

    def __init__(
        self,
        tools: Dict[str, Any],
        sys_prog_config: Dict[str, Any],
        sys_prog_src_dir: Path,
        sys_prog_bld_dir: Path,
        objective_metric: ObjectiveMetric,
        cpus: Optional[int] = None,
        verbose: bool = False,
    ):
        """
        Collect available functions and named structs if not provided and
        perform an initial full build of the system program if required.
        """

        self.tools = tools
        self.sys_prog_src_dir = sys_prog_src_dir
        self.sys_prog_builder = augmentum.sysProgBuilders.create_builder(
            tools, sys_prog_config, sys_prog_src_dir, sys_prog_bld_dir, cpus, verbose
        )
        self.prog_bins = self.sys_prog_builder.instrumented_p / "bin"

        full_build = sys_prog_config["initial_full_build"]
        if "available_functions_and_types" in sys_prog_config:
            self.target_function_data_path = Path(
                sys_prog_config["available_functions_and_types"][function_stats_id]
            )
            self.named_structs_path = Path(
                sys_prog_config["available_functions_and_types"][named_struct_stats_id]
            )
        else:
            data_paths = self.collect_available_functions()
            self.target_function_data_path = Path(data_paths[function_stats_id])
            self.named_structs_path = Path(data_paths[named_struct_stats_id])
            full_build = True  # function collection build requires follow up full build

        if full_build:
            logger.info("Building system program ...")
            with Timer():
                if not self.sys_prog_builder.full_build():
                    raise RuntimeError("Building system program failed.")

        self.objective_metric = objective_metric
        # module_name -> {function_nameA, function_nameB, ...}
        self.existing_extensions: Dict[str, Set[str]] = dict()
        # indicate if changes to extension points have been applied and a rebuild is required
        self.needs_rebuild = False

    def absolute_module_to_relative(self, abs_module: str) -> str:
        return abs_module.replace(str(self.sys_prog_src_dir) + "/", "")

    def relative_module_to_absolute(self, rel_module: str) -> str:
        return str(self.sys_prog_src_dir / Path(rel_module))

    def collect_available_functions(self) -> Dict[str, str]:
        logger.info("Collecting available functions and named structs ...")
        with Timer():
            data_paths = self.sys_prog_builder.collect_functions()

        if not data_paths:
            raise RuntimeError(
                "Collecting available functions and named structs failed for system program."
            )
        return data_paths

    def get_functions(self, function_filter: FunctionFilter) -> Iterable[Function]:
        """Get the list of instrumentable functions"""

        with Timer():
            logger.info(
                "Loading function and type data from:\n"
                + str(self.target_function_data_path)
                + "\n"
                + str(self.named_structs_path)
                + " ..."
            )
            target_function_data = load_target_function_stats(
                self.target_function_data_path
            )
            named_structs = load_named_structs(self.named_structs_path)

        logger.info("Deserialising and filtering available target functions ...")
        with Timer():
            target_fns = self.deserialise_functions(
                function_filter, target_function_data, named_structs
            )

        # clean up residuals
        del target_function_data
        del named_structs
        gc.collect()

        return target_fns

    def deserialise_functions(
        self,
        function_filter: FunctionFilter,
        target_function_data: Generator[FunctionData, None, None],
        named_structs: Dict[str, NamedStructData],
    ) -> Iterable[Function]:
        serialiser = TypeDeserialiser(named_structs)
        target_functions = []

        for fstats in target_function_data:
            function_type_desc = serialiser.deserialise_type(
                DeserialisationContext(fstats.module_name), fstats.serialised_type
            )
            fn = Function(
                fstats.module_name, fstats.function_name, function_type_desc, fstats
            )

            if function_filter.should_instrument(fn):
                target_functions.append(fn)

        return target_functions

    def instrument(self, target_fns: Dict[str, Set[str]]):
        diff = len(target_fns) != len(self.existing_extensions)
        if not diff:
            for m_name, functions in target_fns.items():
                if (
                    m_name not in self.existing_extensions
                    or len(functions.difference(self.existing_extensions[m_name])) > 0
                ):
                    diff = True
                    break

        if diff:
            logger.info(
                f"Instrumenting {sum([len(f) for (_,f) in target_fns.items()])} target functions in {len(target_fns)} modules."
            )
            self.clear_existing_extension_pts()

            for m_name, functions in target_fns.items():
                for fn_name in functions:
                    self.add_extension_pts(m_name, fn_name)

            self.apply_extension_pt_changes()
        else:
            logger.info(
                f"{len(target_fns)} modules already instrumented for target functions."
            )

    def has_extension_pts(self, function: Function) -> bool:
        return (
            function.module in self.existing_extensions
            and function.name in self.existing_extensions[function.module]
        )

    def clear_existing_extension_pts(self):
        for module in self.existing_extensions.keys():
            touch_existing_file(Path(self.relative_module_to_absolute(module)))

        self.existing_extensions.clear()
        self.needs_rebuild = True

    def add_extension_pts(self, module_name: str, function_name: str):
        """
        Add extension point for the function.
        """
        if module_name not in self.existing_extensions:
            self.existing_extensions[module_name] = set()

        self.existing_extensions[module_name].add(function_name)

        touch_existing_file(Path(self.relative_module_to_absolute(module_name)))

        self.needs_rebuild = True

    def apply_extension_pt_changes(self):
        if self.needs_rebuild:
            logger.info(
                "Instrumenting system program for specified extension points ..."
            )
            with Timer():
                success = self.sys_prog_builder.instrument(self.existing_extensions)

            if not success:
                raise RuntimeError("Instrumenting system program failed.")

            self.needs_rebuild = False

    def bind(
        self, probe: ProbeBase, working_dir: Path, keep_probes: bool = False
    ) -> BoundProbe:
        """bind a probe to an existing instrumentation so it can be executed
        multiple times without compiling it again
        """
        return BoundProbe(
            self.tools,
            working_dir,
            self.prog_bins,
            self.sys_prog_src_dir,
            self.objective_metric,
            probe,
            keep_probes,
        )
