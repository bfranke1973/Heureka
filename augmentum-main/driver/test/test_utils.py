# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from numbers import Number

from augmentum.sysUtils import unique_random_integers, unique_random_reals


class TestUniqueGen(unittest.TestCase):
    def check_ints(
        self,
        lower: Number,
        upper: Number,
        num_samples: Number,
        max_tries: Number,
        open_interval: bool,
    ):
        targets = unique_random_integers(
            lower, upper, num_samples, max_tries=max_tries, open_interval=open_interval
        )
        # print(targets)

        self.assertEqual(
            len(targets), num_samples, "Number of targets not as expected."
        )
        for t in targets:
            # native int type should always be returned
            self.assertTrue(
                isinstance(t, int), f"Return type expected to be int but is {type(t)}"
            )
            if open_interval:
                self.assertGreater(t, lower, "Values must be larger than lower.")
                self.assertLess(t, upper, "Values must be larger than lower.")
            else:
                self.assertGreaterEqual(t, lower, "Values must be larger than lower.")
                self.assertLessEqual(t, upper, "Values must be larger than lower.")

        # open_interval=True vs False - excat result check if bounds are in or out
        if upper - lower == num_samples and num_samples > 0:
            if open_interval:
                expected = list(range(lower + 1, upper))
            else:
                expected = list(range(lower, upper + 1))
            for e in expected:
                self.assertTrue(e in targets, "Exepected number not found in result.")

    def test_integers(self):
        self.check_ints(0, 500, 30, 100, False)
        self.check_ints(0, 500, 30, 100, True)

        # upper - lower == num_samples
        self.check_ints(0, 29, 30, 10000, False)  # can fail if running out of tries
        self.check_ints(0, 29, 28, 10000, True)  # can fail if running out of tries

        # lower > upper
        with self.assertRaises(ValueError):
            self.check_ints(500, -500, 30, 100, False)

        # upper - lower < num_samples
        with self.assertRaises(ValueError):
            self.check_ints(-500, 500, 5000, 100, False)

        # max_tries < 0
        with self.assertRaises(ValueError):
            self.check_ints(-500, 500, 30, -50, False)

        # max_tries = 0
        with self.assertRaises(ValueError):
            self.check_ints(-500, 500, 30, 0, False)

        with self.assertRaises(ValueError):
            self.check_ints(-500, 500, -20, 100, False)

        # lower == upper
        self.check_ints(0, 0, 1, 100, False)
        self.check_ints(0, 0, 0, 100, False)

        self.check_ints(0, 4, 0, 100, False)

        with self.assertRaises(ValueError):
            self.check_ints(0, 0, 0, 100, True)

    def check_reals(
        self, lower: Number, upper: Number, num_samples: Number, max_tries: Number
    ):
        targets = unique_random_reals(lower, upper, num_samples, max_tries=max_tries)
        # print(targets)
        self.assertEqual(
            len(targets), num_samples, "Number of targets not as expected."
        )
        for t in targets:
            # native float type should always be returned
            self.assertTrue(
                isinstance(t, float),
                f"Return type expected to be float but is {type(t)}",
            )

            self.assertGreaterEqual(t, lower, "Values must be larger than lower.")
            self.assertLessEqual(t, upper, "Values must be larger than lower.")

    def test_reals(self):
        self.check_reals(0, 500, 30, 100)
        self.check_reals(0, 500, 30, 100)

        # upper - lower == num_samples
        self.check_reals(0, 29, 30, 10000)  # can fail if running out of tries
        self.check_reals(0, 29, 28, 10000)  # can fail if running out of tries

        # lower > upper
        with self.assertRaises(ValueError):
            self.check_reals(500, -500, 30, 100)

        # upper - lower < num_samples
        self.check_reals(-500, 500, 5000, 100)

        # max_tries < 0
        with self.assertRaises(ValueError):
            self.check_reals(-500, 500, 30, -50)

        # max_tries = 0
        with self.assertRaises(ValueError):
            self.check_reals(-500, 500, 30, 0)

        with self.assertRaises(ValueError):
            self.check_reals(-500, 500, -20, 100)

        # lower == upper
        self.check_reals(0, 0, 1, 100)
        self.check_reals(0, 0, 0, 100)

        self.check_reals(0, 4, 0, 100)

        # check float values
        self.check_reals(0.5, 0.6, 500, 100)
