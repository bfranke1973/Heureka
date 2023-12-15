# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from abc import ABC, abstractmethod

from typing import Optional

import re
import logging

from enum import Enum

logger = logging.getLogger(__name__)

class RegexType(Enum):
    """Specifies type of regex for benchmark verifier."""
    REGULAR = 0
    STL_WRAP = 1

class NAS_Verifier(ABC):
    """
    Verify NAS benchmark
    """
    def __init__(self, wl_class : str, stl_wrap : bool = False):
        wl_rex = None
        if stl_wrap:
            wl_rex = self._get_regex()[RegexType.STL_WRAP]
        else:
            wl_rex = self._get_regex()[RegexType.REGULAR]

        if wl_class not in wl_rex:
            raise NotImplementedError(f"Unsupported workload class for {self} benchmark {wl_class}")

        self._regex = wl_rex[wl_class]

    @abstractmethod
    def _get_regex(self):
        """Return regex collection."""

    def verify(self, output : str) -> bool:
        """Verify this benchmark for the given output."""
        matches = re.fullmatch(self._regex, output, re.MULTILINE)
        return matches is not None

    @abstractmethod
    def __str__(self) -> str:
        """Return string representation of this benchmark verifier"""


class BT(NAS_Verifier):
    """
    Verifier for BT benchmark
    """

    # https://regex101.com/r/w6yWlZ/1
    BT_OUT_REX = {
        RegexType.STL_WRAP : {
            "S" : (
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(timer\.flag,r\) = \(nil\)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(inputbt\.data,r\) = \(nil\)\n\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - BT Benchmark\n\n"
                r"\s*No input file inputbt\.data\. Using compiled defaults\n"
                r"\s*Size:   12x  12x  12\n"
                r"\s*Iterations:   60    dt:   0\.010000\n\n"
                r"\s*Time step    1\n"
                r"\s*Time step   20\n"
                r"\s*Time step   40\n"
                r"\s*Time step   60\n"
                r"\s*Verification being performed for class S\n"
                r"\s*accuracy setting for epsilon =  1\.0000000000000E-08\n"
                r"\s*Comparison of RMS-norms of residual\n"
                r"\s*1 1\.7034\d{9}E-01 1\.7034\d{9}E-01 7\.2019\d{9}E-14\n"
                r"\s*2 1\.2975\d{9}E-02 1\.2975\d{9}E-02 3\.6806\d{9}E-13\n"
                r"\s*3 3\.2527\d{9}E-02 3\.2527\d{9}E-02 1\.2756\d{9}E-13\n"
                r"\s*4 2\.6436\d{9}E-02 2\.6436\d{9}E-02 8\.0776\d{9}E-13\n"
                r"\s*5 1\.9211\d{9}E-01 1\.9211\d{9}E-01 1\.3493\d{9}E-13\n"
                r"\s*Comparison of RMS-norms of solution error\n"
                r"\s*1 4\.9976\d{9}E-04 4\.9976\d{9}E-04 1\.9633\d{9}E-13\n"
                r"\s*2 4\.5195\d{9}E-05 4\.5195\d{9}E-05 2\.4124\d{9}E-13\n"
                r"\s*3 7\.3973\d{9}E-05 7\.3973\d{9}E-05 6\.0659\d{9}E-13\n"
                r"\s*4 7\.3821\d{9}E-05 7\.3821\d{9}E-05 8\.3751\d{9}E-13\n"
                r"\s*5 8\.9269\d{9}E-04 8\.9269\d{9}E-04 3\.4856\d{9}E-14\n"
                r"\s*Verification Successful\n"
                r"AUTO2 Verification successful\.\n\n\n"
                r"\s*BT Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             12x  12x  12\n"
                r"\s*Iterations      =                       60\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = \(none\)\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        },

        RegexType.REGULAR : {
            "S" : (
                r"\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - BT Benchmark\n\n"
                r"\s*No input file inputbt\.data\. Using compiled defaults\n"
                r"\s*Size:   12x  12x  12\n"
                r"\s*Iterations:   60    dt:   0\.010000\n\n"
                r"\s*Time step    1\n"
                r"\s*Time step   20\n"
                r"\s*Time step   40\n"
                r"\s*Time step   60\n"
                r"\s*Verification being performed for class S\n"
                r"\s*accuracy setting for epsilon =  1\.0000000000000E-08\n"
                r"\s*Comparison of RMS-norms of residual\n"
                r"\s*1 1\.7034\d{9}E-01 1\.7034\d{9}E-01 7\.2019\d{9}E-14\n"
                r"\s*2 1\.2975\d{9}E-02 1\.2975\d{9}E-02 3\.6806\d{9}E-13\n"
                r"\s*3 3\.2527\d{9}E-02 3\.2527\d{9}E-02 1\.2756\d{9}E-13\n"
                r"\s*4 2\.6436\d{9}E-02 2\.6436\d{9}E-02 8\.0776\d{9}E-13\n"
                r"\s*5 1\.9211\d{9}E-01 1\.9211\d{9}E-01 1\.3493\d{9}E-13\n"
                r"\s*Comparison of RMS-norms of solution error\n"
                r"\s*1 4\.9976\d{9}E-04 4\.9976\d{9}E-04 1\.9633\d{9}E-13\n"
                r"\s*2 4\.5195\d{9}E-05 4\.5195\d{9}E-05 2\.4124\d{9}E-13\n"
                r"\s*3 7\.3973\d{9}E-05 7\.3973\d{9}E-05 6\.0659\d{9}E-13\n"
                r"\s*4 7\.3821\d{9}E-05 7\.3821\d{9}E-05 8\.3751\d{9}E-13\n"
                r"\s*5 8\.9269\d{9}E-04 8\.9269\d{9}E-04 3\.4856\d{9}E-14\n"
                r"\s*Verification Successful\n"
                r"AUTO2 Verification successful\.\n\n\n"
                r"\s*BT Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             12x  12x  12\n"
                r"\s*Iterations      =                       60\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = \(none\)\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        }
    }

    def _get_regex(self):
        return BT.BT_OUT_REX

    def __str__(self) -> str:
        return "BT"

class SP(NAS_Verifier):
    """
    Verifier for SP benchmark
    """

    # https://regex101.com/r/D9dokT/1
    SP_OUT_REX = {
        RegexType.STL_WRAP : {
            "S" : (
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(timer\.flag,r\) = \(nil\)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(inputsp\.data,r\) = \(nil\)\n\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - SP Benchmark\n"
                r"\s*No input file inputsp\.data\. Using compiled defaults\n"
                r"\s*Size:   12x  12x  12\n"
                r"\s*Iterations:  100    dt:   0\.015000\n\n"
                r"\s*Time step    1\n"
                r"\s*Time step   20\n"
                r"\s*Time step   40\n"
                r"\s*Time step   60\n"
                r"\s*Time step   80\n"
                r"\s*Time step  100\n"
                r"\s*Verification being performed for class S\n"
                r"\s*accuracy setting for epsilon =  1\.0000000000000E-08\n"
                r"\s*Comparison of RMS-norms of residual\n"
                r"\s*1 2\.7470\d{9}E-02 2\.7470\d{9}E-02 1\.2087\d{9}E-12\n"
                r"\s*2 1\.0360\d{9}E-02 1\.0360\d{9}E-02 6\.7039\d{9}E-13\n"
                r"\s*3 1\.6235\d{9}E-02 1\.6235\d{9}E-02 1\.9599\d{9}E-12\n"
                r"\s*4 1\.5840\d{9}E-02 1\.5840\d{9}E-02 9\.0456\d{9}E-14\n"
                r"\s*5 3\.4849\d{9}E-02 3\.4849\d{9}E-02 2\.0110\d{9}E-14\n"
                r"\s*Comparison of RMS-norms of solution error\n"
                r"\s*1 2\.7289\d{9}E-05 2\.7289\d{9}E-05 1\.0309\d{9}E-12\n"
                r"\s*2 1\.0364\d{9}E-05 1\.0364\d{9}E-05 3\.3866\d{9}E-13\n"
                r"\s*3 1\.6154\d{9}E-05 1\.6154\d{9}E-05 2\.3724\d{9}E-12\n"
                r"\s*4 1\.5750\d{9}E-05 1\.5750\d{9}E-05 2\.4952\d{9}E-14\n"
                r"\s*5 3\.4177\d{9}E-05 3\.4177\d{9}E-05 1\.6416\d{9}E-13\n"
                r"\s*Verification Successful\n"
                r"AUTO2 Verification successful\.\n\n\n"
                r"\s*SP Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             12x  12x  12\n"
                r"\s*Iterations      =                      100\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = \(none\)\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        },

        RegexType.REGULAR : {
            "S" : (
                r"\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - SP Benchmark\n"
                r"\s*No input file inputsp\.data\. Using compiled defaults\n"
                r"\s*Size:   12x  12x  12\n"
                r"\s*Iterations:  100    dt:   0\.015000\n\n"
                r"\s*Time step    1\n"
                r"\s*Time step   20\n"
                r"\s*Time step   40\n"
                r"\s*Time step   60\n"
                r"\s*Time step   80\n"
                r"\s*Time step  100\n"
                r"\s*Verification being performed for class S\n"
                r"\s*accuracy setting for epsilon =  1\.0000000000000E-08\n"
                r"\s*Comparison of RMS-norms of residual\n"
                r"\s*1 2\.7470\d{9}E-02 2\.7470\d{9}E-02 1\.2087\d{9}E-12\n"
                r"\s*2 1\.0360\d{9}E-02 1\.0360\d{9}E-02 6\.7039\d{9}E-13\n"
                r"\s*3 1\.6235\d{9}E-02 1\.6235\d{9}E-02 1\.9599\d{9}E-12\n"
                r"\s*4 1\.5840\d{9}E-02 1\.5840\d{9}E-02 9\.0456\d{9}E-14\n"
                r"\s*5 3\.4849\d{9}E-02 3\.4849\d{9}E-02 2\.0110\d{9}E-14\n"
                r"\s*Comparison of RMS-norms of solution error\n"
                r"\s*1 2\.7289\d{9}E-05 2\.7289\d{9}E-05 1\.0309\d{9}E-12\n"
                r"\s*2 1\.0364\d{9}E-05 1\.0364\d{9}E-05 3\.3866\d{9}E-13\n"
                r"\s*3 1\.6154\d{9}E-05 1\.6154\d{9}E-05 2\.3724\d{9}E-12\n"
                r"\s*4 1\.5750\d{9}E-05 1\.5750\d{9}E-05 2\.4952\d{9}E-14\n"
                r"\s*5 3\.4177\d{9}E-05 3\.4177\d{9}E-05 1\.6416\d{9}E-13\n"
                r"\s*Verification Successful\n"
                r"AUTO2 Verification successful\.\n\n\n"
                r"\s*SP Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             12x  12x  12\n"
                r"\s*Iterations      =                      100\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = \(none\)\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        }
    }

    def _get_regex(self):
        return SP.SP_OUT_REX

    def __str__(self) -> str:
        return "SP"

class CG(NAS_Verifier):
    """
    Verifier for CG benchmark
    """

    # https://regex101.com/r/rAR05b/1
    CG_OUT_REX = {
        RegexType.STL_WRAP : {
            "S" : (
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(timer\.flag,r\) = \(nil\)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - CG Benchmark\n\n"
                r"\s*Size:        1400\n"
                r"\s*Iterations:    15\n\n"
                r"\s*Initialization time =\s*[0-9]*[.]?[0-9]+ seconds\n\n"
                r"\s*iteration\s+\|\|r\|\|\s+zeta\n"
                r"\s*1\s+1\.3559\d{10}E-13\s+9\.9986\d{9}\n"
                r"\s*2\s+2\.0968\d{10}E-15\s+8\.5733\d{9}\n"
                r"\s*3\s+2\.1220\d{10}E-15\s+8\.5954\d{9}\n"
                r"\s*4\s+1\.9264\d{10}E-15\s+8\.5969\d{9}\n"
                r"\s*5\s+1\.9149\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*6\s+2\.0265\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*7\s+1\.8896\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*8\s+1\.9757\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*9\s+2\.0444\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*10\s+1\.8659\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*11\s+1\.8246\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*12\s+1\.9752\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*13\s+1\.9111\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*14\s+1\.8421\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*15\s+1\.8145\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*Benchmark completed\n"
                r"\s*VERIFICATION SUCCESSFUL\n"
                r"\s*Zeta is     8\.5971\d{9}E\+00\n"
                r"\s*Error is    1\.0331\d{9}E-15\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*CG Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =                     1400\n"
                r"\s*Iterations      =                       15\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = randdp\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        },

        RegexType.REGULAR : {
            "S" : (
                r"\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - CG Benchmark\n\n"
                r"\s*Size:        1400\n"
                r"\s*Iterations:    15\n\n"
                r"\s*Initialization time =\s*[0-9]*[.]?[0-9]+ seconds\n\n"
                r"\s*iteration\s+\|\|r\|\|\s+zeta\n"
                r"\s*1\s+1\.3559\d{10}E-13\s+9\.9986\d{9}\n"
                r"\s*2\s+2\.0968\d{10}E-15\s+8\.5733\d{9}\n"
                r"\s*3\s+2\.1220\d{10}E-15\s+8\.5954\d{9}\n"
                r"\s*4\s+1\.9264\d{10}E-15\s+8\.5969\d{9}\n"
                r"\s*5\s+1\.9149\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*6\s+2\.0265\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*7\s+1\.8896\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*8\s+1\.9757\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*9\s+2\.0444\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*10\s+1\.8659\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*11\s+1\.8246\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*12\s+1\.9752\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*13\s+1\.9111\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*14\s+1\.8421\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*15\s+1\.8145\d{10}E-15\s+8\.5971\d{9}\n"
                r"\s*Benchmark completed\n"
                r"\s*VERIFICATION SUCCESSFUL\n"
                r"\s*Zeta is     8\.5971\d{9}E\+00\n"
                r"\s*Error is    1\.0331\d{9}E-15\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*CG Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =                     1400\n"
                r"\s*Iterations      =                       15\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = randdp\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        }
    }

    def _get_regex(self):
        return CG.CG_OUT_REX

    def __str__(self) -> str:
        return "CG"



class EP(NAS_Verifier):
    """
    Verifier for EP benchmark
    """

    # https://regex101.com/r/Tn06wb/1
    EP_OUT_REX = {
        RegexType.STL_WRAP : {
            "S" : (
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(timer\.flag,r\) = \(nil\)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - EP Benchmark\n\n"
                r"\s*Number of random numbers generated:        33554432\n\n"
                r"\s*EP Benchmark Results:\n\n"
                r"\s*CPU Time =\s+[0-9]*[.]?[0-9]+\n"
                r"\s*N = 2\^   24\n"
                r"\s*No\. Gaussian Pairs =        13176389\n"
                r"\s*Sums =    -3\.2478\d{11}E\+03    -6\.9584\d{11}E\+03\n"
                r"\s*Counts: \n"
                r"\s*0        6140517\n"
                r"\s*1        5865300\n"
                r"\s*2        1100361\n"
                r"\s*3          68546\n"
                r"\s*4           1648\n"
                r"\s*5             17\n"
                r"\s*6              0\n"
                r"\s*7              0\n"
                r"\s*8              0\n"
                r"\s*9              0\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*EP Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =                 33554432\n"
                r"\s*Iterations      =                        0\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  = Random numbers generated\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = randdp\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        },

        RegexType.REGULAR : {
            "S" : (
                r"\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - EP Benchmark\n\n"
                r"\s*Number of random numbers generated:        33554432\n\n"
                r"\s*EP Benchmark Results:\n\n"
                r"\s*CPU Time =\s+[0-9]*[.]?[0-9]+\n"
                r"\s*N = 2\^   24\n"
                r"\s*No\. Gaussian Pairs =        13176389\n"
                r"\s*Sums =    -3\.2478\d{11}E\+03    -6\.9584\d{11}E\+03\n"
                r"\s*Counts: \n"
                r"\s*0        6140517\n"
                r"\s*1        5865300\n"
                r"\s*2        1100361\n"
                r"\s*3          68546\n"
                r"\s*4           1648\n"
                r"\s*5             17\n"
                r"\s*6              0\n"
                r"\s*7              0\n"
                r"\s*8              0\n"
                r"\s*9              0\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*EP Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =                 33554432\n"
                r"\s*Iterations      =                        0\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  = Random numbers generated\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = randdp\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        }
    }

    def _get_regex(self):
        return EP.EP_OUT_REX

    def __str__(self) -> str:
        return "EP"


class MG(NAS_Verifier):
    """
    Verifier for MG benchmark
    """

    #https://regex101.com/r/c5xcl4/1
    MG_OUT_REX = {
        RegexType.STL_WRAP : {
            "S" : (
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(timer\.flag,r\) = \(nil\)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(mg\.input,r\) = \(nil\)\n\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - MG Benchmark\n\n"
                r"\s*No input file\. Using compiled defaults \n"
                r"\s*Size:   32x  32x  32  \(class S\)\n"
                r"\s*Iterations:   4\n\n"
                r"\s*Initialization time:\s*[0-9]*[.]?[0-9]+ seconds\n\n"
                r"\s*iter   1\n"
                r"\s*iter   4\n\n"
                r"\s*Benchmark completed\n"
                r"\s*VERIFICATION SUCCESSFUL\n"
                r"\s*L2 Norm is\s+5\.3077\d{9}E-05\n"
                r"\s*Error is\s+1\.6596\d{9}E-13\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*MG Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             32x  32x  32\n"
                r"\s*Iterations      =                        4\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = randdp\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        },

        RegexType.REGULAR : {
            "S" : (
                r"\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - MG Benchmark\n\n"
                r"\s*No input file\. Using compiled defaults \n"
                r"\s*Size:   32x  32x  32  \(class S\)\n"
                r"\s*Iterations:   4\n\n"
                r"\s*Initialization time:\s*[0-9]*[.]?[0-9]+ seconds\n\n"
                r"\s*iter   1\n"
                r"\s*iter   4\n\n"
                r"\s*Benchmark completed\n"
                r"\s*VERIFICATION SUCCESSFUL\n"
                r"\s*L2 Norm is\s+5\.3077\d{9}E-05\n"
                r"\s*Error is\s+1\.6596\d{9}E-13\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*MG Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             32x  32x  32\n"
                r"\s*Iterations      =                        4\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = randdp\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        }
    }

    def _get_regex(self):
        return MG.MG_OUT_REX

    def __str__(self) -> str:
        return "MG"


class LU(NAS_Verifier):
    """
    Verifier for LU benchmark
    """

    # https://regex101.com/r/wwmjIa/1
    LU_OUT_REX = {
        RegexType.STL_WRAP : {
            "S" : (
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(timer\.flag,r\) = \(nil\)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(inputlu\.data,r\) = \(nil\)\n\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - LU Benchmark\n\n"
                r"\s*Size:   12x  12x  12\n"
                r"\s*Iterations:   50\n\n"
                r"\s*Time step    1\n"
                r"\s*Time step   20\n"
                r"\s*Time step   40\n"
                r"\s*Time step   50\n\n"
                r"\s*Verification being performed for class S\n"
                r"\s*Accuracy setting for epsilon =  1\.0000000000000E-08\n"
                r"\s*Comparison of RMS-norms of residual\n"
                r"\s*1\s+1\.6196\d{9}E-02 1\.6196343210977E-02 8\.8041\d{9}E-14\n"
                r"\s*2\s+2\.1976\d{9}E-03 2\.1976745164821E-03 1\.2886\d{9}E-13\n"
                r"\s*3\s+1\.5179\d{9}E-03 1\.5179927653399E-03 3\.0026\d{9}E-13\n"
                r"\s*4\s+1\.5029\d{9}E-03 1\.5029584435994E-03 1\.2375\d{9}E-12\n"
                r"\s*5\s+3\.4264\d{9}E-02 3\.4264073155896E-02 1\.3770\d{9}E-14\n"
                r"\s*Comparison of RMS-norms of solution error\n"
                r"\s*1\s+6\.4223\d{9}E-04 6\.4223319957961E-04 8\.9304\d{9}E-14\n"
                r"\s*2\s+8\.4144\d{9}E-05 8\.4144342047348E-05 3\.7849\d{9}E-14\n"
                r"\s*3\s+5\.8588\d{9}E-05 5\.8588269616485E-05 3\.2303\d{9}E-13\n"
                r"\s*4\s+5\.8474\d{9}E-05 5\.8474222595157E-05 2\.0870\d{9}E-13\n"
                r"\s*5\s+1\.3103\d{9}E-03 1\.3103347914111E-03 5\.5106\d{9}E-14\n"
                r"\s*Comparison of surface integral\n"
                r"\s*7\.8418\d{9}E\+00 7\.8418928865937E\+00 1\.1326\d{9}E-16\n"
                r"\s*Verification Successful\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*LU Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             12x  12x  12\n"
                r"\s*Iterations      =                       50\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = \(none\)\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        },

        RegexType.REGULAR : {
            "S" : (
                r"\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - LU Benchmark\n\n"
                r"\s*Size:   12x  12x  12\n"
                r"\s*Iterations:   50\n\n"
                r"\s*Time step    1\n"
                r"\s*Time step   20\n"
                r"\s*Time step   40\n"
                r"\s*Time step   50\n\n"
                r"\s*Verification being performed for class S\n"
                r"\s*Accuracy setting for epsilon =  1\.0000000000000E-08\n"
                r"\s*Comparison of RMS-norms of residual\n"
                r"\s*1\s+1\.6196\d{9}E-02 1\.6196343210977E-02 8\.8041\d{9}E-14\n"
                r"\s*2\s+2\.1976\d{9}E-03 2\.1976745164821E-03 1\.2886\d{9}E-13\n"
                r"\s*3\s+1\.5179\d{9}E-03 1\.5179927653399E-03 3\.0026\d{9}E-13\n"
                r"\s*4\s+1\.5029\d{9}E-03 1\.5029584435994E-03 1\.2375\d{9}E-12\n"
                r"\s*5\s+3\.4264\d{9}E-02 3\.4264073155896E-02 1\.3770\d{9}E-14\n"
                r"\s*Comparison of RMS-norms of solution error\n"
                r"\s*1\s+6\.4223\d{9}E-04 6\.4223319957961E-04 8\.9304\d{9}E-14\n"
                r"\s*2\s+8\.4144\d{9}E-05 8\.4144342047348E-05 3\.7849\d{9}E-14\n"
                r"\s*3\s+5\.8588\d{9}E-05 5\.8588269616485E-05 3\.2303\d{9}E-13\n"
                r"\s*4\s+5\.8474\d{9}E-05 5\.8474222595157E-05 2\.0870\d{9}E-13\n"
                r"\s*5\s+1\.3103\d{9}E-03 1\.3103347914111E-03 5\.5106\d{9}E-14\n"
                r"\s*Comparison of surface integral\n"
                r"\s*7\.8418\d{9}E\+00 7\.8418928865937E\+00 1\.1326\d{9}E-16\n"
                r"\s*Verification Successful\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*LU Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             12x  12x  12\n"
                r"\s*Iterations      =                       50\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = \(none\)\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n"
            )
        }
    }

    def _get_regex(self):
        return LU.LU_OUT_REX

    def __str__(self) -> str:
        return "LU"


class FT(NAS_Verifier):
    """
    Verifier for FT benchmark
    """

    # https://regex101.com/r/ERVMgN/1
    FT_OUT_REX = {
        RegexType.STL_WRAP : {
            "S" : (
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(timer\.flag,r\) = \(nil\)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - FT Benchmark\n\n"
                r"\s*Size                :   64x  64x  64\n"
                r"\s*Iterations          :              6\n\n"
                r"\s*T =    1     Checksum =    5\.5460\d{8}E\+02    4\.8453\d{8}E\+02\n"
                r"\s*T =    2     Checksum =    5\.5463\d{8}E\+02    4\.8653\d{8}E\+02\n"
                r"\s*T =    3     Checksum =    5\.5461\d{8}E\+02    4\.8839\d{8}E\+02\n"
                r"\s*T =    4     Checksum =    5\.5454\d{8}E\+02    4\.9012\d{8}E\+02\n"
                r"\s*T =    5     Checksum =    5\.5442\d{8}E\+02    4\.9174\d{8}E\+02\n"
                r"\s*T =    6     Checksum =    5\.5426\d{8}E\+02    4\.9325\d{8}E\+02\n"
                r"\s*kt=1    Sub Res=   -8\.0717\d{8}E-12   -2\.4385\d{8}E-11\n"
                r"\s*kt=1    Div Res=   -3\.0039\d{8}E-14   -1\.7725\d{8}E-14\n"
                r"\s*kt=1    Abs Err=    3\.4879\d{8}E-14\n"
                r"\s*kt=2    Sub Res=    6\.7984\d{8}E-11   -1\.3017\d{8}E-11\n"
                r"\s*kt=2    Div Res=    5\.7636\d{8}E-14   -7\.4028\d{8}E-14\n"
                r"\s*kt=2    Abs Err=    9\.3820\d{8}E-14\n"
                r"\s*kt=3    Sub Res=   -2\.4556\d{8}E-11    6\.3209\d{8}E-11\n"
                r"\s*kt=3    Div Res=    3\.1589\d{8}E-14    8\.6153\d{8}E-14\n"
                r"\s*kt=3    Abs Err=    9\.1761\d{8}E-14\n"
                r"\s*kt=4    Sub Res=   -1\.5802\d{8}E-11    3\.5925\d{8}E-11\n"
                r"\s*kt=4    Div Res=    1\.6147\d{8}E-14    5\.0511\d{8}E-14\n"
                r"\s*kt=4    Abs Err=    5\.3029\d{8}E-14\n"
                r"\s*kt=5    Sub Res=    5\.6843\d{8}E-12    1\.6541\d{8}E-11\n"
                r"\s*kt=5    Div Res=    2\.0549\d{8}E-14    1\.1609\d{8}E-14\n"
                r"\s*kt=5    Abs Err=    2\.3601\d{8}E-14\n"
                r"\s*kt=6    Sub Res=    5\.6957\d{8}E-11   -1\.6768\d{8}E-11\n"
                r"\s*kt=6    Div Res=    4\.2320\d{8}E-14   -6\.7916\d{8}E-14\n"
                r"\s*kt=6    Abs Err=    8\.0022\d{8}E-14\n"
                r"\s*Verification test for FT successful\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*FT Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             64x  64x  64\n"
                r"\s*Iterations      =                        6\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = randdp\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n")
        },

        RegexType.REGULAR : {
            "S" : (
                r"\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER-C\) - FT Benchmark\n\n"
                r"\s*Size                :   64x  64x  64\n"
                r"\s*Iterations          :              6\n\n"
                r"\s*T =    1     Checksum =    5\.5460\d{8}E\+02    4\.8453\d{8}E\+02\n"
                r"\s*T =    2     Checksum =    5\.5463\d{8}E\+02    4\.8653\d{8}E\+02\n"
                r"\s*T =    3     Checksum =    5\.5461\d{8}E\+02    4\.8839\d{8}E\+02\n"
                r"\s*T =    4     Checksum =    5\.5454\d{8}E\+02    4\.9012\d{8}E\+02\n"
                r"\s*T =    5     Checksum =    5\.5442\d{8}E\+02    4\.9174\d{8}E\+02\n"
                r"\s*T =    6     Checksum =    5\.5426\d{8}E\+02    4\.9325\d{8}E\+02\n"
                r"\s*kt=1    Sub Res=   -8\.0717\d{8}E-12   -2\.4385\d{8}E-11\n"
                r"\s*kt=1    Div Res=   -3\.0039\d{8}E-14   -1\.7725\d{8}E-14\n"
                r"\s*kt=1    Abs Err=    3\.4879\d{8}E-14\n"
                r"\s*kt=2    Sub Res=    6\.7984\d{8}E-11   -1\.3017\d{8}E-11\n"
                r"\s*kt=2    Div Res=    5\.7636\d{8}E-14   -7\.4028\d{8}E-14\n"
                r"\s*kt=2    Abs Err=    9\.3820\d{8}E-14\n"
                r"\s*kt=3    Sub Res=   -2\.4556\d{8}E-11    6\.3209\d{8}E-11\n"
                r"\s*kt=3    Div Res=    3\.1589\d{8}E-14    8\.6153\d{8}E-14\n"
                r"\s*kt=3    Abs Err=    9\.1761\d{8}E-14\n"
                r"\s*kt=4    Sub Res=   -1\.5802\d{8}E-11    3\.5925\d{8}E-11\n"
                r"\s*kt=4    Div Res=    1\.6147\d{8}E-14    5\.0511\d{8}E-14\n"
                r"\s*kt=4    Abs Err=    5\.3029\d{8}E-14\n"
                r"\s*kt=5    Sub Res=    5\.6843\d{8}E-12    1\.6541\d{8}E-11\n"
                r"\s*kt=5    Div Res=    2\.0549\d{8}E-14    1\.1609\d{8}E-14\n"
                r"\s*kt=5    Abs Err=    2\.3601\d{8}E-14\n"
                r"\s*kt=6    Sub Res=    5\.6957\d{8}E-11   -1\.6768\d{8}E-11\n"
                r"\s*kt=6    Div Res=    4\.2320\d{8}E-14   -6\.7916\d{8}E-14\n"
                r"\s*kt=6    Abs Err=    8\.0022\d{8}E-14\n"
                r"\s*Verification test for FT successful\n"
                r"\s*AUTO2 Verification successful\.\n\n\n"
                r"\s*FT Benchmark Completed\.\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =             64x  64x  64\n"
                r"\s*Iterations      =                        6\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =           floating point\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n"
                r"\s*RAND         = randdp\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n\n")
        }
    }

    def _get_regex(self):
        return FT.FT_OUT_REX

    def __str__(self) -> str:
        return "FT"

class IS(NAS_Verifier):
    """
    Verifier for IS benchmark
    """

    # https://regex101.com/r/NS79Vi/1
    IS_OUT_REX = {
        RegexType.STL_WRAP : {
            "S" : (
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n"
                r"\s*free\(0x\1\)\n"
                r"\s*fopen\(timer\.flag,r\) = \(nil\)\n"
                r"\s*malloc\(\d+\) = 0x([0-9a-z]+)\n\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER\) - IS Benchmark\n\n"
                r"\s*Size:  65536  \(class S\)\n"
                r"\s*Iterations:   10\n"
                r"(AUTO2 Data dump: 50 158 310 1697 1855 \n){11}\s*AUTO2 Verification successful\.\n"
                r"\s*IS Benchmark Completed\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =                    65536\n"
                r"\s*Iterations      =                       10\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =              keys ranked\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n"
            )
        },

        RegexType.REGULAR : {
            "S" : (
                r"\n\n"
                r"\s*NAS Parallel Benchmarks \(NPB3\.3-SER\) - IS Benchmark\n\n"
                r"\s*Size:  65536  \(class S\)\n"
                r"\s*Iterations:   10\n"
                r"(AUTO2 Data dump: 50 158 310 1697 1855 \n){11}\s*AUTO2 Verification successful\.\n"
                r"\s*IS Benchmark Completed\n"
                r"\s*Class           =                        S\n"
                r"\s*Size            =                    65536\n"
                r"\s*Iterations      =                       10\n"
                r"\s*Time in seconds =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Mop\/s total     =\s*[0-9]*[.]?[0-9]+\n"
                r"\s*Operation type  =              keys ranked\n"
                r"\s*Verification    =               SUCCESSFUL\n"
                r"\s*Version         =                    3\.3\.1\n"
                r"\s*Compile date    =\s*\d{2} ... \d{4}\n\n"
                r"\s*Compile options:\n"
                r"\s*CC           = .+\n"
                r"\s*CLINK        = \$\(CC\)\n"
                r"\s*C_LIB        = -lm\n"
                r"\s*C_INC        = -I\.\.\/common\n"
                r"\s*CFLAGS       = .+\n"
                r"\s*CLINKFLAGS   = .+\n\n"
                r"--------------------------------------\n"
                r"\s*Please send all errors\/feedbacks to:\n"
                r"\s*Center for Manycore Programming\n"
                r"\s*cmp@aces\.snu\.ac\.kr\n"
                r"\s*http:\/\/aces\.snu\.ac\.kr\n"
                r"--------------------------------------\n"
            )
        }
    }

    def _get_regex(self):
        return IS.IS_OUT_REX

    def __str__(self) -> str:
        return "IS"


def build_nas_verifier(benchmark : str, wl_class : str, stl_wrap : bool = False) -> Optional[NAS_Verifier]:
    if benchmark == "BT":
        return BT(wl_class, stl_wrap)
    if benchmark == "SP":
        return SP(wl_class, stl_wrap)
    if benchmark == "CG":
        return CG(wl_class, stl_wrap)
    if benchmark == "EP":
        return EP(wl_class, stl_wrap)
    if benchmark == "MG":
        return MG(wl_class, stl_wrap)
    if benchmark == "LU":
        return LU(wl_class, stl_wrap)
    if benchmark == "FT":
        return FT(wl_class, stl_wrap)
    if benchmark == "IS":
        return IS(wl_class, stl_wrap)

    logger.warning("NAS benchmark not supported for external verification yet: " + benchmark)
    return None
