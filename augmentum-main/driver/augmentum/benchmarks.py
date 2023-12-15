# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import shutil
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Any, Dict, Iterable, Optional, Type

from augmentum.benchmark_LLVM_verification import LLVMOutputVerifier
from augmentum.benchmark_polybench_verification import Polybench_Verifier
from augmentum.benchmark_SNU_make_conf import get_SNU_make_conf
from augmentum.benchmark_SNU_verification import build_nas_verifier
from augmentum.sysUtils import build_path_or_fail, run_command
from augmentum.timer import Timer

logger = logging.getLogger(__name__)


class ExecutionResult(Enum):
    SUCCESS = 0

    COMPILE_FAIL = 1
    RUN_FAIL = 2
    VERIFY_FAIL = 3

    COMPILE_TIMEOUT = 4
    RUN_TIMEOUT = 5
    VERIFY_TIMEOUT = 6

    NA = 7


class TestCase(ABC):
    def __init__(
        self, benchmark_config: Dict[str, Any], benchmark_src_dir: Path, verbose=False
    ):
        self._benchmark_dir = benchmark_src_dir
        self._compile_timeout_secs = float(benchmark_config["compile_timeout_secs"])
        self._run_timeout_secs = float(benchmark_config["run_timeout_secs"])
        self.verbose = verbose

    @property
    def benchmark_dir(self) -> Path:
        """
        Root directory of the benchmark.
        """
        return self._benchmark_dir

    @property
    def compile_timeout_secs(self) -> float:
        """
        Return a compilation timeout in seconds.
        """
        return self._compile_timeout_secs

    @property
    def run_timeout_secs(self) -> float:
        """
        Return a runtime timeout in seconds.
        """
        return self._run_timeout_secs

    @property
    def test_binary(self) -> Path:
        """
        A system path to the location of the binary corresponding to this test case.
        """
        raise NotImplementedError

    @abstractmethod
    def compile(
        self,
        sysprog_bins: Path,
        extension_lib: Optional[Path],
        memory_limit: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Compile the test case
        with the given compiler binaries
        and extension library.

        The extension library is optional. If none is given, the compilation should run without
        loading an extension library.

        memory_limit specifies a memory limit handed to the shell process and its children in MB.
        NOTE: memory limits are inherited by child processes as a whole and stack up.
        """

    @abstractmethod
    def run(self, memory_limit: Optional[int] = None) -> ExecutionResult:
        """
        Run the test case.

        memory_limit specifies a memory limit handed to the shell process and its children in MB.
        NOTE: memory limits are inherited by child processes as a whole and stack up.
        """

    @abstractmethod
    def verify(self) -> ExecutionResult:
        """
        Verify a previous execution result for correctness.
        """

    @abstractmethod
    def __str__(self) -> str:
        """Return string representation of this benchmark test case"""

    @classmethod
    @abstractmethod
    def generate_test_case_from_config(
        cls,
        b_cfg: Dict[str, Any],
        tools: Dict[str, Any],
        benchmark_src_dir: Path,
        verbose: bool,
        bfilter: Optional[Dict[str, Iterable[str]]] = None,
    ) -> Dict[str, "TestCase"]:
        """Factory method to generate test cases of this type from the given configuration."""


_BENCHMARK_TEST_CASE_REGISTRY: Dict[str, Type[TestCase]] = {}


def register(name):
    """Register a benchmark test case."""

    def wrapper(cls):
        _BENCHMARK_TEST_CASE_REGISTRY[name] = cls
        return cls

    return wrapper


################################################################################
# Benchmark Test Cases.
################################################################################


@register("SNU_NPB")
class SNUNPBTestCase(TestCase):
    compile_cmd_template = (
        "cd {benchmark_dir}/{benchmark_prog} && make CLASS={wl_class}"
    )
    clean_cmd_template = (
        "cd {benchmark_dir}/{benchmark_prog} && make clean && rm -f {test_bin}"
    )

    verification_success = " Verification    =               SUCCESSFUL"
    bad_alloc_error = "what():  std::bad_alloc"

    def __init__(
        self,
        benchmark_config: Dict[str, Any],
        benchmark_src_dir: Path,
        program: str,
        program_config: Optional[Dict[str, Any]],
        wl_class: str,
        verbose=False,
    ):
        super().__init__(benchmark_config, benchmark_src_dir, verbose)

        # the program from the NAS suite
        self.__program = program
        # the workload class to be used for the nas suite
        self.__wl_class = wl_class

        output_dir = self._benchmark_dir / "bin"
        self.prepare_output(output_dir)

        # the benchmark binary to be executed
        self.__test_binary = (
            output_dir / f"{self.__program.lower()}.{self.__wl_class.upper()}.x"
        )

        self.__last_returncode = None
        self.__last_stdout = None

        # custom timeouts specified for this test case
        if program_config:
            if "compile_timeout_secs" in program_config:
                self._compile_timeout_secs = program_config["compile_timeout_secs"]
            if "run_timeout_secs" in program_config:
                self._run_timeout_secs = program_config["run_timeout_secs"]

        if "compiler_flags" in benchmark_config:
            self.compiler_flags = benchmark_config["compiler_flags"]
        if "linker_flags" in benchmark_config:
            self.linker_flags = benchmark_config["linker_flags"]

    def prepare_output(self, outdir: Path):
        outdir.mkdir(exist_ok=True)

    @property
    def test_binary(self) -> Path:
        return self.__test_binary

    def clean(self) -> bool:
        clean_cmd = SNUNPBTestCase.clean_cmd_template.format(
            benchmark_dir=self._benchmark_dir,
            benchmark_prog=self.__program,
            test_bin=self.test_binary,
        )

        try:
            returncode, _ = run_command(
                clean_cmd, timeout=self.compile_timeout_secs, verbose=self.verbose
            )
        except TimeoutExpired:
            return False

        return returncode == 0

    def compile(
        self,
        sysprog_bins: Path,
        extension_lib: Optional[Path],
        memory_limit: Optional[int] = None,
    ) -> ExecutionResult:
        # write configuration options to make.def
        extension_flags = (
            f"-Xclang -load -Xclang {extension_lib}"
            if extension_lib is not None
            else ""
        )
        flags = f"{extension_flags} {self.compiler_flags}"
        make_def_content = get_SNU_make_conf(
            sysprog_bins / "clang", flags, self.linker_flags
        )
        with (self._benchmark_dir / "config" / "make.def").open("w") as md_file:
            md_file.write(make_def_content)

        if not self.clean():
            return ExecutionResult.COMPILE_FAIL

        compile_cmd = SNUNPBTestCase.compile_cmd_template.format(
            benchmark_dir=self._benchmark_dir,
            benchmark_prog=self.__program,
            wl_class=self.__wl_class,
        )

        try:
            returncode, stdout = run_command(
                compile_cmd,
                timeout=self.compile_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
        except TimeoutExpired:
            return ExecutionResult.COMPILE_TIMEOUT

        if returncode != 0 and SNUNPBTestCase.bad_alloc_error in stdout:
            logger.info("Bad alloc detected. Possible memory overflow.")
        return (
            ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.COMPILE_FAIL
        )

    def run(self, memory_limit: Optional[int] = None) -> ExecutionResult:
        try:
            returncode, stdout = run_command(
                f"{self.test_binary}",
                timeout=self.run_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
            self.__last_returncode = returncode
            self.__last_stdout = stdout

        except TimeoutExpired:
            return ExecutionResult.RUN_TIMEOUT

        return ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.RUN_FAIL

    def verify(self) -> ExecutionResult:
        if self.__last_returncode is None or self.__last_stdout is None:
            return ExecutionResult.VERIFY_FAIL
        else:
            verify_ok = (
                self.__last_returncode == 0
                and self.__last_stdout.find(SNUNPBTestCase.verification_success) >= 0
            )

            return ExecutionResult.SUCCESS if verify_ok else ExecutionResult.VERIFY_FAIL

    def __str__(self) -> str:
        return f"SNU_NPB {self.__program} {self.__wl_class}"

    @classmethod
    def generate_test_case_from_config(
        cls,
        b_cfg: Dict[str, Any],
        tools: Dict[str, Any],
        benchmark_src_dir: Path,
        verbose: bool,
        bfilter: Optional[Dict[str, Iterable[str]]] = None,
    ) -> Dict[str, TestCase]:
        test_cases = dict()

        for b in b_cfg["benchmarks"]:
            classes = b_cfg["default_classes"]
            b_conf = b_cfg["benchmark_config"]
            prog_conf = None
            if b in b_conf:
                prog_conf = b_conf[b]
                if "classes" in prog_conf:
                    classes = prog_conf["classes"]
            for c in classes:
                case = cls(b_cfg, benchmark_src_dir, b, prog_conf, c, verbose)
                assert (
                    str(case) not in test_cases
                ), "Test case must have unique representation"
                test_cases[str(case)] = case

        return test_cases


@register("SNU_NPB_BC")
class SNUNPB_BC_TestCase(TestCase):
    """
    Nas benchmark suite test case using bit code files only.
    """

    opt_and_link_cmd_template = """
{sysprog_bins}/opt {extension_flags} {opt_flags} {benchmark_dir}/{benchmark_bc} -o {benchmark_dir}/opt_{benchmark_bc} &&
{compiler_bins}/clang {link_flags} {benchmark_dir}/opt_{benchmark_bc} {verify_module} -o {test_bin}
    """
    clean_cmd_template = """
rm -f {benchmark_dir}/opt_{benchmark_bc} {test_bin}
    """

    verification_success = " Verification    =               SUCCESSFUL"
    bad_alloc_error = "what():  std::bad_alloc"

    def __init__(
        self,
        benchmark_config: Dict[str, Any],
        vanilla_compiler_bins: Path,
        benchmark_src_dir: Path,
        program: str,
        program_config: Optional[Dict[str, Any]],
        wl_class: str,
        verbose=False,
    ):
        super().__init__(benchmark_config, benchmark_src_dir, verbose)

        # the program from the NAS suite
        self.__program = program
        # the workload class to be used for the nas suite
        self.__wl_class = wl_class

        self.__verifier = build_nas_verifier(self.__program, self.__wl_class)

        output_dir = self._benchmark_dir / "bin"
        self.prepare_output(output_dir)

        # the benchmark binary to be executed
        test_stem = f"{self.__program.lower()}.{self.__wl_class.upper()}"
        self.__test_binary = output_dir / f"{test_stem}.x"
        self.__test_bitcode = self._benchmark_dir / f"{test_stem}.bc"
        self.__test_verify = (
            self._benchmark_dir
            / f"{self.__program.lower()}_verify.{self.__wl_class.upper()}.o"
        )

        if not self.__test_verify.exists():
            logger.warning(f"No external verification used for test {self}.")
            self.__test_verify = ""

        self.__last_returncode = None
        self.__last_stdout = None

        self.__vanilla_compiler_bins = vanilla_compiler_bins

        # custom timeouts specified for this test case
        if program_config:
            if "compile_timeout_secs" in program_config:
                self._compile_timeout_secs = program_config["compile_timeout_secs"]
            if "run_timeout_secs" in program_config:
                self._run_timeout_secs = program_config["run_timeout_secs"]

        if "compiler_flags" in benchmark_config:
            self.compiler_flags = benchmark_config["compiler_flags"]
        if "linker_flags" in benchmark_config:
            self.linker_flags = benchmark_config["linker_flags"]

    def prepare_output(self, outdir: Path):
        outdir.mkdir(exist_ok=True)

    @property
    def test_binary(self) -> Path:
        return self.__test_binary

    def clean(self) -> bool:
        clean_cmd = SNUNPB_BC_TestCase.clean_cmd_template.format(
            benchmark_dir=self._benchmark_dir,
            benchmark_bc=self.__test_bitcode.name,
            test_bin=self.test_binary,
        )

        try:
            returncode, _ = run_command(
                clean_cmd, timeout=self.compile_timeout_secs, verbose=self.verbose
            )
        except TimeoutExpired:
            return False

        return returncode == 0

    def compile(
        self,
        sysprog_bins: Path,
        extension_lib: Optional[Path],
        memory_limit: Optional[int] = None,
    ) -> ExecutionResult:
        opt_flags = f"{self.compiler_flags}"
        link_flags = "-mcmodel=medium -lm"

        if not self.clean():
            return ExecutionResult.COMPILE_FAIL

        extension_flags = f"-load {extension_lib}" if extension_lib is not None else ""

        opt_and_link_cmd = SNUNPB_BC_TestCase.opt_and_link_cmd_template.format(
            sysprog_bins=sysprog_bins,
            compiler_bins=self.__vanilla_compiler_bins,
            extension_flags=extension_flags,
            opt_flags=opt_flags,
            benchmark_dir=self._benchmark_dir,
            benchmark_bc=self.__test_bitcode.name,
            verify_module=self.__test_verify,
            link_flags=link_flags,
            test_bin=self.test_binary,
        )

        try:
            returncode, stdout = run_command(
                opt_and_link_cmd,
                timeout=self.compile_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
        except TimeoutExpired:
            return ExecutionResult.COMPILE_TIMEOUT

        if returncode != 0 and SNUNPB_BC_TestCase.bad_alloc_error in stdout:
            logger.info("Bad alloc detected. Possible memory overflow.")
        return (
            ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.COMPILE_FAIL
        )

    def run(self, memory_limit: Optional[int] = None) -> ExecutionResult:
        try:
            returncode, stdout = run_command(
                f"{self.test_binary}",
                timeout=self.run_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
            self.__last_returncode = returncode
            self.__last_stdout = stdout

        except TimeoutExpired:
            return ExecutionResult.RUN_TIMEOUT

        return ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.RUN_FAIL

    def verify(self) -> ExecutionResult:
        if self.__last_returncode is None or self.__last_stdout is None:
            return ExecutionResult.VERIFY_FAIL
        else:
            verified = False
            if self.__verifier:
                verified = self.__verifier.verify(self.__last_stdout)
            else:
                logger.warning("Verification not uncoupled for test case " + str(self))
                verified = (
                    self.__last_stdout.find(SNUNPB_BC_TestCase.verification_success)
                    >= 0
                )

            verify_ok = self.__last_returncode == 0 and verified

            return ExecutionResult.SUCCESS if verify_ok else ExecutionResult.VERIFY_FAIL

    def __str__(self) -> str:
        return f"SNU_NPB_BC {self.__program} {self.__wl_class}"

    @classmethod
    def generate_test_case_from_config(
        cls,
        b_cfg: Dict[str, Any],
        tools: Dict[str, Any],
        benchmark_src_dir: Path,
        verbose: bool,
        bfilter: Optional[Dict[str, Iterable[str]]] = None,
    ) -> Dict[str, TestCase]:
        test_cases = dict()

        vanilla_compiler_bins = Path(tools["compiler_bin"])

        for b in b_cfg["benchmarks"]:
            classes = b_cfg["default_classes"]
            b_conf = b_cfg["benchmark_config"]
            prog_conf = None
            if b in b_conf:
                prog_conf = b_conf[b]
                if "classes" in prog_conf:
                    classes = prog_conf["classes"]
            for c in classes:
                case = cls(
                    b_cfg,
                    vanilla_compiler_bins,
                    benchmark_src_dir,
                    b,
                    prog_conf,
                    c,
                    verbose,
                )
                assert (
                    str(case) not in test_cases
                ), "Test case must have unique representation"
                test_cases[str(case)] = case

        return test_cases


@register("SNU_NPB_DIRECT")
class SNUNPB_DIRECT_TestCase(TestCase):
    """
    Nas benchmark suite test case using modified clang to
    build object files and vanilla clang to link them together.
    """

    compile_cmd_template = """
{benchmark_dir}/direct_build/build.sh {benchmark_name} {benchmark_class} {benchmark_dir}/NPB3.3-SER-C {binary_dir} {build_dir} {compiler_bins}/clang {sysprog_bins}/clang {compile_flags} {link_flags} {extension_lib}
    """

    clean_cmd_template = """
rm -rf {binary_dir}/*.x {build_dir}/*.o
    """

    verification_success = " Verification    =               SUCCESSFUL"
    bad_alloc_error = "what():  std::bad_alloc"

    def __init__(
        self,
        benchmark_config: Dict[str, Any],
        vanilla_compiler_bins: Path,
        benchmark_src_dir: Path,
        program: str,
        program_config: Optional[Dict[str, Any]],
        wl_class: str,
        verbose=False,
    ):
        super().__init__(benchmark_config, benchmark_src_dir, verbose)

        # the program from the NAS suite
        self.__program = program
        # the workload class to be used for the nas suite
        self.__wl_class = wl_class

        self.__verifier = build_nas_verifier(self.__program, self.__wl_class)

        self.prepare_output()

        # the benchmark binary to be executed
        test_stem = f"{self.__program.lower()}.{self.__wl_class.upper()}"
        self.__test_binary = self.__bin_dir / f"{test_stem}.x"

        self.__last_returncode = None
        self.__last_stdout = None

        self.__vanilla_compiler_bins = vanilla_compiler_bins

        # custom timeouts specified for this test case
        if program_config:
            if "compile_timeout_secs" in program_config:
                self._compile_timeout_secs = program_config["compile_timeout_secs"]
            if "run_timeout_secs" in program_config:
                self._run_timeout_secs = program_config["run_timeout_secs"]

        if "compiler_flags" in benchmark_config:
            self.compiler_flags = benchmark_config["compiler_flags"]
        if "linker_flags" in benchmark_config:
            self.linker_flags = benchmark_config["linker_flags"]

    def prepare_output(self):
        """Prepare required output directories and files"""
        bin_base = self._benchmark_dir / "direct_build" / "bin"
        bin_base.mkdir(exist_ok=True)

        self.__bin_dir = bin_base / self.__program
        self.__bin_dir.mkdir(exist_ok=True)

        build_base = self._benchmark_dir / "direct_build" / "build"
        build_base.mkdir(exist_ok=True)

        self.__build_dir = build_base / self.__program
        self.__build_dir.mkdir(exist_ok=True)

    @property
    def test_binary(self) -> Path:
        return self.__test_binary

    def clean(self) -> bool:
        clean_cmd = SNUNPB_DIRECT_TestCase.clean_cmd_template.format(
            benchmark_dir=self._benchmark_dir,
            binary_dir=self.__bin_dir,
            build_dir=self.__build_dir,
        )

        try:
            returncode, _ = run_command(
                clean_cmd, timeout=self.compile_timeout_secs, verbose=self.verbose
            )
        except TimeoutExpired:
            return False

        return returncode == 0

    def compile(
        self,
        sysprog_bins: Path,
        extension_lib: Optional[Path],
        memory_limit: Optional[int] = None,
    ) -> ExecutionResult:
        compile_flags = f'"{self.compiler_flags}"'
        link_flags = f'"{self.linker_flags}"'

        if not self.clean():
            return ExecutionResult.COMPILE_FAIL

        compile_cmd = SNUNPB_DIRECT_TestCase.compile_cmd_template.format(
            benchmark_dir=self._benchmark_dir,
            benchmark_name=self.__program.lower(),
            benchmark_class=self.__wl_class.upper(),
            binary_dir=self.__bin_dir,
            build_dir=self.__build_dir,
            compiler_bins=self.__vanilla_compiler_bins,
            sysprog_bins=sysprog_bins,
            compile_flags=compile_flags,
            link_flags=link_flags,
            extension_lib=extension_lib if extension_lib is not None else '""',
        )

        try:
            returncode, stdout = run_command(
                compile_cmd,
                timeout=self.compile_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
        except TimeoutExpired:
            return ExecutionResult.COMPILE_TIMEOUT

        if returncode != 0 and SNUNPB_DIRECT_TestCase.bad_alloc_error in stdout:
            logger.info("Bad alloc detected. Possible memory overflow.")
        return (
            ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.COMPILE_FAIL
        )

    def run(self, memory_limit: Optional[int] = None) -> ExecutionResult:
        try:
            returncode, stdout = run_command(
                f"{self.test_binary}",
                timeout=self.run_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
            self.__last_returncode = returncode
            self.__last_stdout = stdout

        except TimeoutExpired:
            return ExecutionResult.RUN_TIMEOUT

        return ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.RUN_FAIL

    def verify(self) -> ExecutionResult:
        if self.__last_returncode is None or self.__last_stdout is None:
            return ExecutionResult.VERIFY_FAIL
        else:
            verified = False
            if self.__verifier is not None:
                verified = self.__verifier.verify(self.__last_stdout)
            else:
                logger.warning("Verification not uncoupled for test case " + str(self))
                verified = (
                    self.__last_stdout.find(SNUNPB_DIRECT_TestCase.verification_success)
                    >= 0
                )

            verify_ok = self.__last_returncode == 0 and verified

            return ExecutionResult.SUCCESS if verify_ok else ExecutionResult.VERIFY_FAIL

    def __str__(self) -> str:
        return f"SNU_NPB_DIRECT {self.__program} {self.__wl_class}"

    @classmethod
    def generate_test_case_from_config(
        cls,
        b_cfg: Dict[str, Any],
        tools: Dict[str, Any],
        benchmark_src_dir: Path,
        verbose: bool,
        bfilter: Optional[Dict[str, Iterable[str]]] = None,
    ) -> Dict[str, TestCase]:
        test_cases = dict()

        vanilla_compiler_bins = Path(tools["compiler_bin"])

        for b in b_cfg["benchmarks"]:
            classes = b_cfg["default_classes"]
            b_conf = b_cfg["benchmark_config"]
            prog_conf = None
            if b in b_conf:
                prog_conf = b_conf[b]
                if "classes" in prog_conf:
                    classes = prog_conf["classes"]
            for c in classes:
                case = cls(
                    b_cfg,
                    vanilla_compiler_bins,
                    benchmark_src_dir,
                    b,
                    prog_conf,
                    c,
                    verbose,
                )
                assert (
                    str(case) not in test_cases
                ), "Test case must have unique representation"
                test_cases[str(case)] = case

        return test_cases


@register("POLYBENCH")
class PolybenchTestCase(TestCase):
    """
    Polybench benchmark suite test case using modified clang to
    build object files and vanilla clang to link them together.

    https://web.cse.ohio-state.edu/~pouchet.2/software/polybench/
    """

    compile_cmd_template = """
{benchmark_dir}/augmentum/build.sh {benchmark_name} {benchmark_class} {benchmark_dir} {benchmark_src} {binary_dir} {build_dir} {compiler_bins}/clang {sysprog_bins}/clang {compile_flags} {link_flags} {extension_lib}
    """

    clean_cmd_template = """
rm -rf {binary_dir}/*.x {build_dir}/*.o
    """

    bad_alloc_error = "what():  std::bad_alloc"

    def __init__(
        self,
        benchmark_config: Dict[str, Any],
        vanilla_compiler_bins: Path,
        benchmark_src_dir: Path,
        program: str,
        program_dir: Path,
        program_config: Optional[Dict[str, Any]],
        wl_class: str,
        verbose=False,
    ):
        super().__init__(benchmark_config, benchmark_src_dir, verbose)

        # the program name from the polybench suite
        self.__program = program
        self.__program_dir = benchmark_src_dir / program_dir

        # the workload class to be used for the benchmark suite
        self.__wl_class = wl_class

        self.__verifier = Polybench_Verifier()

        self.prepare_output()

        # the benchmark binary to be executed
        test_stem = f"{self.__program.lower()}.{self.__wl_class.upper()}"
        self.__test_binary = self.__bin_dir / f"{test_stem}.x"

        self.__last_returncode = None
        self.__last_stdout = None

        self.__vanilla_compiler_bins = vanilla_compiler_bins

        # custom timeouts specified for this test case
        if program_config:
            if "compile_timeout_secs" in program_config:
                self._compile_timeout_secs = program_config["compile_timeout_secs"]
            if "run_timeout_secs" in program_config:
                self._run_timeout_secs = program_config["run_timeout_secs"]

        if "compiler_flags" in benchmark_config:
            self.compiler_flags = benchmark_config["compiler_flags"]
        if "linker_flags" in benchmark_config:
            self.linker_flags = benchmark_config["linker_flags"]

    def prepare_output(self):
        """Prepare required output directories and files"""
        bin_base = self._benchmark_dir / "augmentum" / "bin"
        bin_base.mkdir(exist_ok=True)

        self.__bin_dir = bin_base / self.__program
        self.__bin_dir.mkdir(exist_ok=True)

        build_base = self._benchmark_dir / "augmentum" / "build"
        build_base.mkdir(exist_ok=True)

        self.__build_dir = build_base / self.__program
        self.__build_dir.mkdir(exist_ok=True)

    @property
    def test_binary(self) -> Path:
        return self.__test_binary

    def clean(self) -> bool:
        clean_cmd = PolybenchTestCase.clean_cmd_template.format(
            benchmark_dir=self._benchmark_dir,
            binary_dir=self.__bin_dir,
            build_dir=self.__build_dir,
        )

        try:
            returncode, _ = run_command(
                clean_cmd, timeout=self.compile_timeout_secs, verbose=self.verbose
            )
        except TimeoutExpired:
            return False

        return returncode == 0

    def compile(
        self,
        sysprog_bins: Path,
        extension_lib: Optional[Path],
        memory_limit: Optional[int] = None,
    ) -> ExecutionResult:
        compile_flags = f'"{self.compiler_flags}"'
        link_flags = f'"{self.linker_flags}"'

        if not self.clean():
            return ExecutionResult.COMPILE_FAIL

        compile_cmd = PolybenchTestCase.compile_cmd_template.format(
            benchmark_dir=self._benchmark_dir,
            benchmark_name=self.__program.lower(),
            benchmark_class=self.__wl_class.upper(),
            benchmark_src=self.__program_dir,
            binary_dir=self.__bin_dir,
            build_dir=self.__build_dir,
            compiler_bins=self.__vanilla_compiler_bins,
            sysprog_bins=sysprog_bins,
            compile_flags=compile_flags,
            link_flags=link_flags,
            extension_lib=extension_lib if extension_lib is not None else '""',
        )

        try:
            returncode, stdout = run_command(
                compile_cmd,
                timeout=self.compile_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
        except TimeoutExpired:
            return ExecutionResult.COMPILE_TIMEOUT

        if returncode != 0 and PolybenchTestCase.bad_alloc_error in stdout:
            logger.info("Bad alloc detected. Possible memory overflow.")
        return (
            ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.COMPILE_FAIL
        )

    def run(self, memory_limit: Optional[int] = None) -> ExecutionResult:
        try:
            returncode, stdout = run_command(
                f"{self.test_binary}",
                timeout=self.run_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
            self.__last_returncode = returncode
            self.__last_stdout = stdout

        except TimeoutExpired:
            return ExecutionResult.RUN_TIMEOUT

        return ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.RUN_FAIL

    def verify(self) -> ExecutionResult:
        if self.__last_returncode is None or self.__last_stdout is None:
            return ExecutionResult.VERIFY_FAIL
        else:
            assert (
                self.__verifier is not None
            ), f"No verifier entry found for Polybench test {self.__program}"

            verified = self.__verifier.verify(self.__program, self.__last_stdout)
            verify_ok = self.__last_returncode == 0 and verified

            return ExecutionResult.SUCCESS if verify_ok else ExecutionResult.VERIFY_FAIL

    def __str__(self) -> str:
        return f"POLYBENCH {self.__program} {self.__wl_class}"

    @classmethod
    def generate_test_case_from_config(
        cls,
        b_cfg: Dict[str, Any],
        tools: Dict[str, Any],
        benchmark_src_dir: Path,
        verbose: bool,
        bfilter: Optional[Dict[str, Iterable[str]]] = None,
    ) -> Dict[str, TestCase]:
        test_cases = dict()

        vanilla_compiler_bins = Path(tools["compiler_bin"])

        for b in b_cfg["benchmarks"]:
            b_name = Path(b).name
            classes = b_cfg["default_classes"]
            b_conf = b_cfg["benchmark_config"]
            prog_conf = None
            if b in b_conf:
                prog_conf = b_conf[b]
                if "classes" in prog_conf:
                    classes = prog_conf["classes"]
            for c in classes:
                case = cls(
                    b_cfg,
                    vanilla_compiler_bins,
                    benchmark_src_dir,
                    b_name,
                    Path(b),
                    prog_conf,
                    c,
                    verbose,
                )
                assert (
                    str(case) not in test_cases
                ), "Test case must have unique representation"
                test_cases[str(case)] = case

        return test_cases


@register("LLVM_SUITE")
class LLVMSuiteTestCase(TestCase):
    """
    Test cases from the llvm test suite.
    https://llvm.org/docs/TestSuiteGuide.html
    """

    compile_direct_cmd_template = (
        """{compiler} {compile_flags} {link_flags} {libs} {src_files} -o {target}"""
    )

    compile_object_cmd_template = (
        """{compiler} -c {compile_flags} {src_file} -o {target}"""
    )

    link_binary_cmd_template = (
        """{compiler} {link_flags} {libs} {obj_files} -o {target}"""
    )

    clean_cmd_template = """rm -rf {output_dir}/*.out {output_dir}/*.o"""

    bad_alloc_error = "what():  std::bad_alloc"

    def __init__(
        self,
        benchmark_config: Dict[str, Any],
        vanilla_compiler_bins: Path,
        benchmark_src_dir: Path,
        program: str,
        suite: str,
        fpcmp: Path,
        direct_compile: bool = False,
        verbose: bool = False,
        output_dir: Optional[Path] = None,
    ):
        super().__init__(benchmark_config, benchmark_src_dir, verbose)

        # the program from the test suite
        self.__suite = suite
        self.__program = program

        if output_dir is None:
            self.__output_dir = (
                self.benchmark_dir / "output" / self.__suite / self.__program
            )
        else:
            self.__output_dir = output_dir

        self.clean()

        self.__test_binary = self.__output_dir / f"{self.__program}.out"
        self.__last_returncode = None
        self.__last_stdout = None

        self.__vanilla_compiler_bins = vanilla_compiler_bins

        generic_test_config = benchmark_config["suites"][self.__suite]["generic"]
        self.__test_config = benchmark_config["suites"][self.__suite]["benchmarks"][
            self.__program
        ]

        # override verbose flag for this test case
        self.__silent_run = False
        if "silent_run" in self.__test_config:
            self.__silent_run = self.__test_config["silent_run"]

        # custom timeouts specified for this test case
        if "compile_timeout_secs" in self.__test_config:
            self._compile_timeout_secs = self.__test_config["compile_timeout_secs"]
        if "run_timeout_secs" in self.__test_config:
            self._run_timeout_secs = self.__test_config["run_timeout_secs"]

        # set compiler and linker flags
        self.__compile_flags = benchmark_config["compiler_flags"]
        if "compiler_flags" in generic_test_config:
            self.__compile_flags += " " + generic_test_config["compiler_flags"]
        self.__link_flags = benchmark_config["linker_flags"]
        if "linker_flags" in generic_test_config:
            self.__link_flags += " " + generic_test_config["linker_flags"]

        # compile to objects and then link or compile and link directly in one command?
        self.__direct_compile = direct_compile

        # check if we can use the small reference output
        reference_output = (
            self.benchmark_dir / self.__suite / f"{self.__program}.reference_output"
        )
        if "-DSMALL_PROBLEM_SIZE" in self.__compile_flags:
            small_ref = reference_output.parent / (reference_output.name + ".small")
            if small_ref.is_file():
                reference_output = small_ref

        # perpare verification
        fpcmp_flags = (
            generic_test_config["fpcmp_flags"]
            if "fpcmp_flags" in generic_test_config
            else ""
        )
        hash_output = (
            self.__test_config["hash_output"]
            if "hash_output" in self.__test_config
            else False
        )
        self.__verifier = LLVMOutputVerifier(
            reference_output,
            fpcmp,
            fpcmp_flags,
            hash_output=hash_output,
            verbose=verbose,
        )

    @property
    def test_binary(self) -> Path:
        return self.__test_binary

    def select_compiler(self, program: Path) -> str:
        if program.suffix == ".c":
            return "clang"
        elif program.suffix == ".cpp":
            return "clang++"
        else:
            raise RuntimeError("Unsupported test case extension: " + str(program))

    def clean(self) -> bool:
        if self.__output_dir.exists():
            for p in self.__output_dir.glob("*.out"):
                (self.__output_dir / p).unlink()
            for p in self.__output_dir.glob("*.o"):
                (self.__output_dir / p).unlink()
        else:
            self.__output_dir.mkdir(parents=True, exist_ok=False)
        return True

    def get_direct_compile_cmd(self, mclang_bins: Path) -> str:
        """
        Generate compilation command for all files of this test
        case that does object creation and linking in one step.
        """

        program_dir = (
            self.__test_config["program_dir"]
            if "program_dir" in self.__test_config
            else "."
        )
        src_dir = self.benchmark_dir / self.__suite / program_dir

        src_files = self.__test_config["src"].copy()
        sources = [str(src_dir / src) for src in src_files]
        compiler_bin = self.select_compiler(
            Path(sources[0])
        )  # select based on ending of first source file

        libs = (
            " ".join(self.__test_config["libs"]) if "libs" in self.__test_config else ""
        )

        # create command to compile in one go
        compile_cmd = LLVMSuiteTestCase.compile_direct_cmd_template.format(
            compiler=str(mclang_bins / compiler_bin),
            compile_flags=self.__compile_flags,
            link_flags=self.__link_flags,
            libs=libs,
            src_files=" ".join(sources),
            target=self.test_binary,
        )

        return compile_cmd

    def get_obj_and_link_compile_cmd(
        self, mclang_bins: Path, vclang_bins: Path, extension_flags: str
    ) -> str:
        """
        Generate compilation command for all files of this test
        case by generating object files first and then linking them together.
        """
        compiler_cmds = []
        object_files = []

        # create commands to compile all objects using extension
        program_dir = (
            self.__test_config["program_dir"]
            if "program_dir" in self.__test_config
            else "."
        )
        src_dir = self.benchmark_dir / self.__suite / program_dir

        sources = [src_dir / src for src in self.__test_config["src"]]
        compiler_bin = self.select_compiler(
            sources[0]
        )  # select based on ending of first source file

        for src in sources:
            obj = f"{self.__output_dir / src.stem}.o"
            object_files.append(obj)

            compiler_cmds.append(
                LLVMSuiteTestCase.compile_object_cmd_template.format(
                    compiler=str(mclang_bins / compiler_bin),
                    compile_flags=self.__compile_flags + " " + extension_flags,
                    src_file=src,
                    target=obj,
                )
            )

        libs = (
            " ".join(self.__test_config["libs"]) if "libs" in self.__test_config else ""
        )

        # create command to link all objects
        compiler_cmds.append(
            LLVMSuiteTestCase.link_binary_cmd_template.format(
                compiler=str(vclang_bins / compiler_bin),
                link_flags=self.__link_flags,
                libs=libs,
                obj_files=" ".join(object_files),
                target=self.__test_binary,
            )
        )

        compile_cmd = " && ".join(compiler_cmds)

        return compile_cmd

    def compile(
        self,
        sysprog_bins: Path,
        extension_lib: Optional[Path],
        memory_limit: Optional[int] = None,
    ) -> ExecutionResult:
        if not self.clean():
            return ExecutionResult.COMPILE_FAIL

        mclang_bins = sysprog_bins
        vclang_bins = self.__vanilla_compiler_bins
        extension_flags = (
            f"-Xclang -load -Xclang {extension_lib}"
            if extension_lib is not None
            else ""
        )

        # generate compilation commands
        if self.__direct_compile:
            compile_cmd = self.get_direct_compile_cmd(mclang_bins)
        else:
            compile_cmd = self.get_obj_and_link_compile_cmd(
                mclang_bins, vclang_bins, extension_flags
            )

        # run compilation commands
        try:
            returncode, stdout = run_command(
                compile_cmd,
                timeout=self.compile_timeout_secs,
                verbose=self.verbose,
                memory_limit=memory_limit,
            )
        except TimeoutExpired:
            return ExecutionResult.COMPILE_TIMEOUT

        if returncode != 0 and LLVMSuiteTestCase.bad_alloc_error in stdout:
            logger.info("Bad alloc detected. Possible memory overflow.")
        return (
            ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.COMPILE_FAIL
        )

    def run(self, memory_limit: Optional[int] = None) -> ExecutionResult:
        if self.__silent_run:
            logger.info(f"Silently running {self.test_binary}")

        try:
            returncode, stdout = run_command(
                f"{self.test_binary}",
                timeout=self.run_timeout_secs,
                verbose=False if self.__silent_run else self.verbose,
                memory_limit=memory_limit,
            )
            self.__last_returncode = returncode
            self.__last_stdout = stdout

        except TimeoutExpired:
            return ExecutionResult.RUN_TIMEOUT

        return ExecutionResult.SUCCESS if returncode == 0 else ExecutionResult.RUN_FAIL

    def verify(self) -> ExecutionResult:
        if self.__last_returncode is None or self.__last_stdout is None:
            return ExecutionResult.VERIFY_FAIL
        else:
            verify_ok = self.__verifier.verify(
                self.__last_stdout, self.__last_returncode
            )
            return ExecutionResult.SUCCESS if verify_ok else ExecutionResult.VERIFY_FAIL

    def __str__(self) -> str:
        return f"LLVM_SUITE {self.__suite} {self.__program}"

    @classmethod
    def generate_test_case_from_config(
        cls,
        b_cfg: Dict[str, Any],
        tools: Dict[str, Any],
        benchmark_src_dir: Path,
        verbose: bool,
        bfilter: Optional[Dict[str, Iterable[str]]] = None,
    ) -> Dict[str, TestCase]:
        test_cases = dict()

        vanilla_compiler_bins = Path(tools["compiler_bin"])
        fpcmp_bin = Path(tools["fpcmp"])

        available: dict[str, Iterable[str]] = dict()

        if bfilter is not None:
            available = bfilter
        else:
            for suite in b_cfg["suites"].keys():
                available[suite] = list(b_cfg["suites"][suite]["benchmarks"].keys())

        for suite, benchmarks in available.items():
            for b in benchmarks:
                case = LLVMSuiteTestCase(
                    b_cfg,
                    vanilla_compiler_bins,
                    benchmark_src_dir,
                    b,
                    suite,
                    fpcmp=fpcmp_bin,
                    direct_compile=False,
                    verbose=verbose,
                )

                assert (
                    str(case) not in test_cases
                ), "Test case must have unique representation"
                test_cases[str(case)] = case

        return test_cases


class BenchmarkFactory:
    def __init__(
        self,
        tools: Dict[str, Any],
        benchmark_cfgs: Iterable[Dict[str, Any]],
        verbose=False,
        bfilter: Optional[Dict[str, Iterable[str]]] = None,
    ):
        self.tools = tools
        self.configs = benchmark_cfgs
        self.bfilter = bfilter
        self.verbose = verbose

    def setup_benchmark_instance(self, working_dir: Path) -> Dict[str, TestCase]:
        """
        Copy benchmark sources to specified working directory
        and build configured test cases.
        """
        benchmarks = dict()
        with Timer():
            for b_cfg in self.configs:
                b_name = b_cfg["benchmark_name"]
                logger.info(f"Copying benchmark sources for benchmark {b_name}")

                original_src = build_path_or_fail(b_cfg["benchmark_dir"])
                benchmark_src_dir = working_dir / "benchmarks_src" / b_name

                logger.info(f"Copying directory tree {original_src}...")
                shutil.copytree(original_src, benchmark_src_dir, symlinks=True)

                b_instances = self.load_test_cases(benchmark_src_dir, b_cfg)
                logger.info(f"{len(b_instances)} tests created for {b_name}.")
                benchmarks.update(b_instances)

        logger.info(f"{len(benchmarks)} test cases instantiated in total.")
        return benchmarks

    def load_test_cases(
        self, benchmark_src_dir: Path, b_cfg: Dict[str, Any]
    ) -> Dict[str, TestCase]:
        """Load benchmark test cases for given source directory"""

        assert "benchmark_name" in b_cfg, "Benchmark configuration not as expected."

        bname = b_cfg["benchmark_name"]
        if bname not in _BENCHMARK_TEST_CASE_REGISTRY:
            raise ValueError(f"Unknown benchmark name {bname}")

        test_cases = _BENCHMARK_TEST_CASE_REGISTRY[
            bname
        ].generate_test_case_from_config(
            b_cfg, self.tools, benchmark_src_dir, self.verbose, self.bfilter
        )

        return test_cases
