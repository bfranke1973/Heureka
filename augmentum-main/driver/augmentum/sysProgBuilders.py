# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import csv
import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Set

from augmentum.function import parse_collected_function_stats, use_relative_src_path
from augmentum.sysUtils import run_command

logger = logging.getLogger(__name__)


class InstrumenterInterface:
    """
    Interface to the instrumenter pass in the compiler which can
    be used to specify extension points ahead of compilation.
    """

    delimiter = ";"
    target_fun_header = ["MODULE", "FUNCTION"]

    def __init__(self, comm_file: Path, src_path: Path):
        self.__comm_file = comm_file
        self.__src_path = src_path

    @property
    def comm_file(self) -> Path:
        return self.__comm_file

    def set_extension_pt_targets(self, extension_pts: Dict[str, Set[str]]):
        """Configure extension points to be added during the next instrumentation run"""

        with open(self.comm_file, "w") as sOut:
            fun_writer = csv.writer(sOut, delimiter=InstrumenterInterface.delimiter)
            fun_writer.writerow(InstrumenterInterface.target_fun_header)

            for module, functions in extension_pts.items():
                for function in functions:
                    absolute_module = self.__src_path / Path(module)
                    fun_writer.writerow([str(absolute_module), function])

    def clear_extension_pt_targets(self):
        """Remove all extension point targets for the next instrumentation run"""
        self.set_extension_pt_targets(dict())


class SysProgBuilder(ABC):
    instr_args_collect_template = (
        "   -mllvm -instrumentation-stats-output={function_stats_output}"
        "   -mllvm -dry-run"
    )

    instr_args_target_template = "   -mllvm -target-functions={target_functions}"

    def __init__(
        self,
        tools: Dict[str, Any],
        sys_prog_src_dir: Path,
        sys_prog_bld_dir: Path,
        cpus: Optional[int] = None,
        verbose: bool = False,
    ):
        self.tools = tools
        self.build_path = sys_prog_bld_dir
        self.src_path = sys_prog_src_dir

        self.statistics_p = self.build_path / "statistics"
        self.instrumented_p = self.build_path / "instrumented"
        self.target_functions_p = self.build_path / "target_functions.csv"

        self.instrument_module = ""

        self.instr_interface = InstrumenterInterface(
            self.target_functions_p, self.src_path
        )
        self.verbose = verbose

        self.cpus = cpus

    def run_cmd(self, cmd: str) -> bool:
        returncode, stdout = run_command(cmd, verbose=self.verbose)

        if returncode != 0 and not self.verbose:
            logger.info(stdout)

        return returncode == 0

    @abstractmethod
    def run_build_cmd(self, instr_args: str, module: str = "", clean_up=False) -> bool:
        """
        Run the build command for this system program with required configuration parameters.
        """
        pass

    def full_build(self) -> bool:
        """
        Run regular build without instrumentation for corresponding system program.

        Return True if successful.
        """

        instr_args = LLVMBuilder.instr_args_target_template.format(
            target_functions=str(self.target_functions_p)
        )

        return self.run_build_cmd(instr_args, clean_up=True)

    def collect_functions(self) -> Optional[Dict[str, str]]:
        """
        Run functions and named structs collection build and return
        paths to target functions and named structs statistic files.

        Calling this might require a full rebuild before instrumentation
        can be done.

        This might be done for a submodule of the code only (see instrument_module).

        Return None if process failed.
        """

        instr_args = LLVMBuilder.instr_args_collect_template.format(
            function_stats_output=str(self.statistics_p)
        )

        if self.run_build_cmd(instr_args, module=self.instrument_module, clean_up=True):
            data_paths = parse_collected_function_stats(
                self.build_path / "statistics", self.build_path
            )
            data_paths = use_relative_src_path(data_paths, self.src_path)
            return data_paths
        else:
            return None

    def instrument(self, extension_pts: Dict[str, Set[str]]) -> bool:
        """
        Run instrumentation for the corresponding system program.

        Return True if successful.
        """

        self.instr_interface.set_extension_pt_targets(extension_pts)

        instr_args = LLVMBuilder.instr_args_target_template.format(
            target_functions=str(self.target_functions_p)
        )

        return self.run_build_cmd(instr_args, clean_up=False)

    def clean(self):
        """
        Clean up generated binaries and statistics files.
        """
        if self.statistics_p.exists():
            shutil.rmtree(str(self.statistics_p))

        if self.instrumented_p.exists():
            shutil.rmtree(str(self.instrumented_p))

        self.target_functions_p.unlink(missing_ok=True)

    def setup(self):
        """
        Setup directories for build.
        """
        self.statistics_p.mkdir(exist_ok=True)
        self.instrumented_p.mkdir(exist_ok=True)
        self.target_functions_p.touch()


class LLVMBuilder(SysProgBuilder):
    cmake_template = (
        "cmake"
        " -DCMAKE_ASM_COMPILER={llvm_as}"
        " -DCMAKE_C_COMPILER={cc}"
        " -DCMAKE_CXX_COMPILER={cxx}"
        " -DLLVM_TEMPORARILY_ALLOW_OLD_TOOLCHAIN=true"
        ' -DCMAKE_CXX_FLAGS="-Xclang -load -Xclang {augmentum_pass} {instrumenter_args} {compiler_flags}"'
        ' -DCMAKE_EXE_LINKER_FLAGS="-laugmentum -L{augmentum_library} -Wl,-rpath,{augmentum_library} {linker_flags}"'
        ' -DCMAKE_SHARED_LINKER_FLAGS="-laugmentum -L{augmentum_library} -Wl,-rpath,{augmentum_library} {linker_flags}"'
        ' -DCMAKE_MODULE_LINKER_FLAGS="-laugmentum -L{augmentum_library} -Wl,-rpath,{augmentum_library} {linker_flags}"'
        " -DLLVM_ENABLE_PROJECTS=clang"
        " -DBUILD_SHARED_LIBS=True"
        " -DCMAKE_BUILD_TYPE=RelWithDebInfo"
        " -DLLVM_ENABLE_RTTI=ON"
        " -DLLVM_ENABLE_EH=ON"
        " {gcc_install_prefix}"
        " -B{instrumented_dir}"
        " -H{src_dir}/llvm"
    )

    # Use VERBOSE=1 at the end of this line to individual compiler commands during llvm build
    build_template = "cd {instrumented_dir} && make {module} -j{cpus}"

    def __init__(
        self,
        tools: Dict[str, Any],
        sys_prog_conf: Dict[str, Any],
        sys_prog_src_dir: Path,
        sys_prog_bld_dir: Path,
        cpus: Optional[int] = None,
        verbose: bool = False,
    ):
        super().__init__(tools, sys_prog_src_dir, sys_prog_bld_dir, cpus, verbose)
        self.instrument_module = sys_prog_conf["instrument_module"]
        self.compiler_flags = sys_prog_conf["compiler_flags"]
        self.linker_flags = sys_prog_conf["linker_flags"]

        self.gcc_install_prefix = ""
        if "gcc_install_prefix" in sys_prog_conf:
            self.gcc_install_prefix = (
                f"-DGCC_INSTALL_PREFIX={sys_prog_conf['gcc_install_prefix']}"
            )

    def run_cmake(self, instr_args: str) -> bool:
        cmake_cmd = LLVMBuilder.cmake_template.format(
            llvm_as=str(Path(self.tools["compiler_bin"]) / "llvm-as"),
            cc=str(Path(self.tools["compiler_bin"]) / "clang"),
            cxx=self.tools["cxx"],
            augmentum_pass=self.tools["augmentum_pass"],
            augmentum_library=self.tools["augmentum_library"],
            instrumenter_args=instr_args,
            src_dir=str(self.src_path),
            instrumented_dir=str(self.instrumented_p),
            compiler_flags=self.compiler_flags,
            linker_flags=self.linker_flags,
            gcc_install_prefix=self.gcc_install_prefix,
        )

        return self.run_cmd(cmake_cmd)

    def run_build_cmd(self, instr_args: str, module: str = "", clean_up=False) -> bool:
        if clean_up:
            self.clean()
            self.setup()

            if not self.run_cmake(instr_args):
                return False

        bld_cmd = LLVMBuilder.build_template.format(
            instrumented_dir=str(self.instrumented_p),
            module=module,
            cpus=str(self.cpus) if self.cpus is not None else "`nproc`",
        )

        return self.run_cmd(bld_cmd)


class HeuristicSynthBuilder(SysProgBuilder):
    bld_cmd_template = (
        "{cxx} -O3 -std=c++17 -fPIE"
        "   -Xclang -load -Xclang {augmentum_pass}"
        "   {instrumenter_args}"
        "   {src_dir}/int_check.cpp"
        "   -I{augmentum_headers}"
        "   -laugmentum -L{augmentum_library} -Wl,-rpath,{augmentum_library}"
        "   -ldl"
        "   -o {instrumented_dir}/int_check.out"
    )

    def run_build_cmd(self, instr_args: str, module: str = "", clean_up=False) -> bool:
        if clean_up:
            self.clean()
            self.setup()

        bld_cmd = HeuristicSynthBuilder.bld_cmd_template.format(
            cxx=self.tools["cxx"],
            augmentum_pass=self.tools["augmentum_pass"],
            augmentum_headers=self.tools["augmentum_headers"],
            augmentum_library=self.tools["augmentum_library"],
            instrumenter_args=instr_args,
            src_dir=str(self.src_path),
            instrumented_dir=str(self.instrumented_p),
        )

        return self.run_cmd(bld_cmd)


def create_builder(
    tools: Dict[str, Any],
    sys_prog_conf: Dict[str, Any],
    sys_prog_src_dir: Path,
    sys_prog_bld_dir: Path,
    cpus: Optional[int] = None,
    verbose: bool = False,
) -> SysProgBuilder:
    if sys_prog_conf["type"] == "llvm":
        return LLVMBuilder(
            tools, sys_prog_conf, sys_prog_src_dir, sys_prog_bld_dir, cpus, verbose
        )
    if sys_prog_conf["type"] == "synth-heuristic":
        return HeuristicSynthBuilder(
            tools, sys_prog_src_dir, sys_prog_bld_dir, cpus, verbose
        )
    else:
        raise RuntimeError(
            "Unsupported system program builder type: " + str(sys_prog_conf["type"])
        )
