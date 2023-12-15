# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import subprocess
import unittest


class TestExtensions(unittest.TestCase):
    def run_native_executable(self, exec: str):
        completedProc = subprocess.run(
            exec,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if completedProc.returncode != 0:
            print(completedProc.stdout)
            print(f"Exit status: {completedProc.returncode}")
            self.fail("Non-zero exit status.")

    def test_uninstrumented(self):
        self.run_native_executable("test/native/uninstrumented")

    def test_instrumented_with_none(self):
        self.run_native_executable("test/native/instrumented-with-none")

    def test_instrumented_with_c(self):
        self.run_native_executable("test/native/instrumented-with-c")

    @unittest.skip(
        "This currently only works for [int add(int,int)]. "
        "The python interface needs to be extended for all "
        "other types in order for this test to run through."
    )
    def test_instrumented_with_python(self):
        self.run_native_executable(
            "AUGMENTUM_PYTHON=test.native.extend test/native/instrumented-with-python"
        )

    def test_explicit(self):
        self.run_native_executable("test/native/explicit")
