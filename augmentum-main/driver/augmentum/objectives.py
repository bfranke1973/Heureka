# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from augmentum.sysUtils import run_command

from augmentum.benchmarks import ExecutionResult, TestCase

logger = logging.getLogger(__name__)


class ObjectiveResult:
    """
    Encapsulate the result of an objective measurement.
    """

    def __init__(
        self, score: Any, unit: str = None, supplementary: Optional[Dict] = None
    ):
        self.__score = score
        self.__unit = unit
        self.__supp = supplementary

    @property
    def score(self) -> Any:
        """The absolute score measured for the objective."""
        return self.__score

    @property
    def unit(self) -> Optional[str]:
        """Data unit of the measured objective, if any."""
        return self.__unit

    @property
    def supplementary(self) -> Optional[Dict]:
        """Supplementary data measured for the objective, if any."""
        return self.__supp

    def __str__(self) -> str:
        u = self.unit if self.unit else ""
        return str(self.score) + " " + u


class ObjectiveMetric(ABC):
    @abstractmethod
    def measure(
        self, test_case: TestCase, memory_limit: Optional[int] = None
    ) -> Tuple[ExecutionResult, ObjectiveResult]:
        """
        Measure objective for the given task and return
        run result and objective measurement.
        """

    @abstractmethod
    def equals(self, res_a: ObjectiveResult, res_b: ObjectiveResult) -> bool:
        """
        Returns true if the two objective results are equal
        according to the metric.
        """

    @abstractmethod
    def is_improved(self, measured: ObjectiveResult, baseline: float) -> bool:
        """
        Check if the given objective is improved compared to the given baseline
        according to the metric.
        """


class CodeSizeObjective(ObjectiveMetric):
    """
    Measure the code and data size of the binary used for the provided test case.
    The text plus data element size from the llvm-size tool is returned in bytes.

    This metric assumes that the binary has only a single binary to be measured.
    """

    EPSILON = 0.000001
    result_unit = "bytes"

    def __init__(self, size_bin: Path):
        if not size_bin.exists():
            raise RuntimeError("Given llvm-size binary invalid: " + str(size_bin))

        self.size_bin = size_bin

    def measure(
        self, test_case: TestCase, memory_limit: Optional[int] = None
    ) -> Tuple[ExecutionResult, Optional[ObjectiveResult]]:
        code_size = self.get_code_size(test_case.test_binary)
        run_result = test_case.run(memory_limit=memory_limit)

        return run_result, code_size

    def equals(self, res_a: ObjectiveResult, res_b: ObjectiveResult) -> bool:
        return abs(res_a.score - res_b.score) < CodeSizeObjective.EPSILON

    def is_improved(self, measured: ObjectiveResult, baseline: ObjectiveResult) -> bool:
        """
        For code size, smaller is better.
        """
        return measured.score < baseline.score

    def get_code_size(self, binary_path: Path) -> ObjectiveResult:
        returncode, stdout = run_command(f"{self.size_bin} {binary_path}")

        if returncode != 0:
            logger.error(f"Measuring binary size failed: {stdout}")
            return None

        text = data = bss = None

        # measure both code size and data size using Berkley output format (default)
        # Expected Sample Output:
        #   text	   data	    bss	    dec	    hex	filename
        #  56364	    644	 357352	 414360	  65298	bt.S.x

        for lnum, line in enumerate(stdout.splitlines()):
            if lnum == 1:
                elems = re.split(r"\s+", line.strip().strip())
                if len(elems) < 6:
                    logger.error(
                        "Object file segments could not be parsed when measuring binary size!"
                    )
                    logger.info(stdout)
                    return None

                text = float(elems[0])
                data = float(elems[1])
                bss = float(elems[2])
                text_data_size = text + data
                break

        if text is None:
            logger.error(
                "Object file segments could not be parsed when measuring binary size!"
            )

        # get file size
        file_size = os.path.getsize(f"{binary_path}")

        # get zipped file size
        bz2_file_size = None
        returncode, stdout = run_command(f"bzip2 -k {binary_path}")
        if returncode != 0:
            logger.warning(f"Measuring compressed binary file size failed: {stdout}")
        else:
            bz2_binary_path = Path(str(binary_path) + ".bz2")
            if not bz2_binary_path.exists():
                logger.warning(
                    f"Measuring compressed binary file size failed: {stdout}"
                )
            else:
                bz2_file_size = os.path.getsize(f"{bz2_binary_path}")
                bz2_binary_path.unlink()

        supp = {
            "text": text,
            "data": data,
            "bss": bss,
            "file": file_size,
            "bz2": bz2_file_size,
        }
        return ObjectiveResult(
            text_data_size, CodeSizeObjective.result_unit, supplementary=supp
        )
