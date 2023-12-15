# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import math
import unittest
from numbers import Number
from typing import Dict, Iterable, Optional, Tuple

from augmentum.function import Function, FunctionData
from augmentum.priors import (
    REAL_ACCURACY,
    REAL_TOLERANCE,
    BinaryBoundsSearch,
    BinarySearch,
    BoundedPrior,
    IntegerBinaryBoundsSearch,
    IntegerBinarySearch,
    IntegerOffsetPrior,
    IntegerRangePrior,
    IntegerScalePrior,
    Prior,
    ProbeResult,
    RangePrior,
    RealBinaryBoundsSearch,
    RealOffsetPrior,
    RealRangePrior,
    RealScalePrior,
    SearchTarget,
    get_real_limit,
)
from augmentum.probes import OffsetProbe, ScaleProbe, StaticProbe
from augmentum.type_descs import FunctionTypeDesc, double_t, float_t, i32_t, i64_t

from augmentum.benchmarks import ExecutionResult

# Flip this for print output
VERBOSE = False


def prior_update_check(test: unittest.TestCase, prior: Prior):
    if isinstance(prior, BoundedPrior):
        search_strat = prior.upper_search_strat
    elif isinstance(prior, RangePrior):
        search_strat = prior.search_strat
    else:
        test.fail("Unhandled Prior type.")

    search_strat.target = SearchTarget(0)
    result = ProbeResult(None, None)
    result.compile_ok = ExecutionResult.SUCCESS
    result.run_ok = ExecutionResult.SUCCESS
    result.verify_ok = ExecutionResult.SUCCESS
    prior.update(result)

    test.assertTrue(
        search_strat.target.eval_success,
        "Updated not registered successful probe as expected.",
    )

    search_strat.target = SearchTarget(0)
    result = ProbeResult(None, None)
    result.compile_ok = ExecutionResult.COMPILE_FAIL
    result.run_ok = ExecutionResult.NA
    result.verify_ok = ExecutionResult.NA
    prior.update(result)

    test.assertFalse(
        search_strat.target.eval_success,
        "Updated not registered successful probe as expected.",
    )

    # update same search value again
    result = ProbeResult(None, None)
    result.compile_ok = ExecutionResult.SUCCESS
    result.run_ok = ExecutionResult.SUCCESS
    result.verify_ok = ExecutionResult.SUCCESS
    prior.update(result)

    test.assertFalse(
        search_strat.target.eval_success,
        "Updating for the same search value"
        " twice should require all results to be successful.",
    )


class TestIntervalSearch(unittest.TestCase):
    def check(
        self,
        values: Dict[Number, bool],
        min_bound: Number,
        max_bound: Number,
        exp_lower: Number,
        exp_upper: Number,
        exp_min: Number,
        exp_max: Number,
    ):
        lower, upper, min_bound, max_bound = BinaryBoundsSearch.find_initial_bounds(
            values, min_bound, max_bound
        )

        self.assertEqual(
            lower, exp_lower, f"Unexpected lower bound for initial values {values}"
        )
        self.assertEqual(
            upper, exp_upper, f"Unexpected upper bound for initial values {values}"
        )
        self.assertEqual(
            min_bound,
            exp_min,
            f"Unexpected min_bound bound for initial values {values}",
        )
        self.assertEqual(
            max_bound,
            exp_max,
            f"Unexpected max_bound bound for initial values {values}",
        )

    def test_bounds(self):
        self.check({-5: True}, -500, 500, -5, -5, -500, 500)
        self.check({-5: False}, -500, 500, None, None, None, None)

        self.check({-5: True, 4: True, 20: True}, -500, 500, -5, 20, -500, 500)
        self.check({-5: False, 4: True, 20: True}, -500, 500, 4, 20, -5, 500)
        self.check({-5: True, 4: True, 20: False}, -500, 500, -5, 4, -500, 20)
        self.check({-5: False, 4: True, 9: True, 20: False}, -500, 500, 4, 9, -5, 20)
        self.check({-5: False, 4: True, 20: False}, -500, 500, 4, 4, -5, 20)
        self.check({-5: False, 4: False, 20: False}, -500, 500, None, None, None, None)
        self.check({-5: True, 4: False, 20: False}, -500, 500, -5, -5, -500, 4)
        self.check({-5: False, 4: False, 20: True}, -500, 500, 20, 20, 4, 500)

        # # first diff (-5,5) = 10, second diff (5,40) = 35
        self.check(
            {-5: True, 4: True, 5: False, 8: True, 34: True, 40: True},
            -500,
            500,
            8,
            40,
            5,
            500,
        )

        # # first diff (-5,4) = 9, second diff (4,8) = 4
        self.check(
            {-5: True, 4: False, 5: True, 8: False, 34: False, 40: False},
            -500,
            500,
            -5,
            -5,
            -500,
            4,
        )

        # # first diff (4,8) = 4, second diff (8,40) = 32
        self.check(
            {-5: False, 4: False, 5: True, 8: False, 34: True, 40: False},
            -500,
            500,
            34,
            34,
            8,
            40,
        )

        # # first diff (-200,105) = 305, second diff (150,400) = 250
        self.check(
            {
                -200: True,
                23: True,
                55: True,
                105: False,
                110: False,
                150: False,
                200: True,
                400: True,
            },
            -2147483648,
            2147483647,
            -200,
            55,
            -2147483648,
            105,
        )

        # # first diff (-200,105) = 305, second diff (150,499) = 349
        self.check(
            {
                -200: True,
                23: True,
                55: True,
                105: False,
                110: False,
                150: False,
                200: True,
                499: True,
            },
            -2147483648,
            2147483647,
            200,
            499,
            150,
            2147483647,
        )


class TestIntegerRangeSearch(unittest.TestCase):
    def setUp(self):
        fn_data = FunctionData(
            "add.cpp",
            "_Z3addii",
            "@$ i32, i32, i32 $@",
            "add(int, int)",
            2,
            "instrument",
        )
        fn_type = FunctionTypeDesc(i32_t, i32_t, i32_t)
        self.fun = Function("add.cpp", "_Z3addii", fn_type, fn_data)
        paths = self.fun.get_paths()
        self.path = paths[0]
        self.assertGreater(len(paths), 0, "Available paths initialised incorrectly.")

        self.max_int = 2 ** (self.path.type.bits - 1) - 1
        self.min_int = -(2 ** (self.path.type.bits - 1))

    def init_prior(
        self,
        initial_probes: Dict[Number, bool],
        lower: Optional[int],
        upper: Optional[int],
        invalid: bool,
    ) -> IntegerRangePrior:
        prior = IntegerRangePrior(self.fun, self.path, initial_probes)

        self.assertEqual(
            prior.search_strat.lower,
            lower,
            f"Unexpected lower bound chosen for initial probes {initial_probes}",
        )
        self.assertEqual(
            prior.search_strat.upper,
            upper,
            f"Unexpected upper bound chosen for initial probes {initial_probes}",
        )
        self.assertEqual(
            prior.is_invalid(),
            invalid,
            f"Unexpected validity chosen for initial probes {initial_probes}",
        )
        return prior

    def test_init_range(self):
        self.init_prior({-5: True, 4: True, 20: True}, -5, 20, invalid=False)
        self.init_prior({-5: False, 4: True, 20: True}, 4, 20, invalid=False)
        self.init_prior({-5: True, 4: True, 20: False}, -5, 4, invalid=False)
        self.init_prior({-5: False, -1: True, 4: True, 20: False}, -1, 4, invalid=False)
        self.init_prior({-5: False, 4: False, 20: True}, 20, 20, invalid=False)

        # first diff (-5,0) = 5, second diff (0,20) = 20 --> 20
        self.init_prior(
            {-5: True, -1: True, 0: False, 4: True, 20: False}, 4, 4, invalid=False
        )

        # test invalids
        self.init_prior({-5: False, 4: False, 20: False}, None, None, invalid=True)
        self.init_prior({}, None, None, invalid=True)

        # test bound shortcuts
        prior = IntegerRangePrior(self.fun, self.path, {-5: False, 4: True, 20: True})

        self.assertEqual(
            prior.search_strat.min_bound, -5, "Unexpected minimum lower bound chosen."
        )
        self.assertEqual(
            prior.search_strat.max_bound,
            self.max_int,
            "Unexpected maximum upper bound chosen.",
        )

        prior = IntegerRangePrior(self.fun, self.path, {-5: True, 4: True, 20: False})

        self.assertEqual(
            prior.search_strat.min_bound,
            self.min_int,
            "Unexpected minimum lower bound chosen.",
        )
        self.assertEqual(
            prior.search_strat.max_bound, 20, "Unexpected maximum upper bound chosen."
        )

        prior = IntegerRangePrior(
            self.fun, self.path, {-5: False, 4: True, 20: False, 40: False}
        )

        self.assertEqual(
            prior.search_strat.min_bound, -5, "Unexpected minimum lower bound chosen."
        )
        self.assertEqual(
            prior.search_strat.max_bound, 20, "Unexpected maximum upper bound chosen."
        )

    def test_isdone(self):
        prior = self.init_prior({-5: True, 4: True, 20: False}, -5, 4, invalid=False)
        self.assertFalse(
            prior.is_done(), "Prior should not be done if valid and not executed."
        )

        prior = self.init_prior(
            {-5: False, 4: False, 20: False}, None, None, invalid=True
        )
        self.assertTrue(prior.is_done(), "Prior should be done if invalid after init.")

    def run_prior(
        self,
        target_lower: int,
        start_lower: int,
        target_upper: int,
        start_upper: int,
        initial_probes: Dict[Number, bool],
        invalid=False,
    ) -> IntegerRangePrior:
        prior = self.init_prior(
            initial_probes, start_lower, start_upper, invalid=invalid
        )
        while not prior.is_done():
            probe = prior.select_next_probe()
            result = ProbeResult(probe, None)

            self.assertTrue(
                isinstance(probe, StaticProbe),
                f"Probe expected to be StaticProbe but is {type(probe)}.",
            )

            if (
                probe.get_probe_value() > target_upper
                or probe.get_probe_value() < target_lower
            ):
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA
            else:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS

            prior.update(result)  # None test case is used for test purposes only!

        self.assertEqual(prior.is_invalid(), invalid, "Expected prior to be valid.")

        if not invalid:
            self.assertEqual(
                prior.search_strat.state,
                BinaryBoundsSearch.BinSearchState.DONE,
                "Expected prior to be done.",
            )
            self.assertEqual(
                prior.search_strat.upper,
                target_upper,
                f"Expected prior to find {target_upper} as upper bound.",
            )
            self.assertEqual(
                prior.search_strat.lower,
                target_lower,
                f"Expected prior to find {target_lower} as lower bound.",
            )
        else:
            self.assertEqual(
                prior.search_strat.upper,
                None,
                "Expected invalid prior to return None result for boundary.",
            )
            self.assertEqual(
                prior.search_strat.lower,
                None,
                "Expected invalid prior to return None result for boundary.",
            )

        return prior

    def test_find_bounds(self):
        start_bounds = [(6, 10), (0, 5000), (-2345, -499)]

        for lstart, ustart in start_bounds:
            self.run_prior(
                self.min_int, lstart, self.max_int, ustart, {lstart: True, ustart: True}
            )
            self.run_prior(
                self.min_int, lstart, 3493496, ustart, {lstart: True, ustart: True}
            )
            self.run_prior(
                -134217733, lstart, self.max_int, ustart, {lstart: True, ustart: True}
            )
            self.run_prior(
                -134217733, lstart, 235332, ustart, {lstart: True, ustart: True}
            )

            if lstart > 0:
                self.run_prior(
                    0, lstart, self.max_int, ustart, {lstart: True, ustart: True}
                )

        self.run_prior(0, 0, 0, 0, {0: True})

    def run_verification_check(
        self,
        initial_probes: Dict[Number, bool],
        target_upper: Number,
        target_lower: Number,
        fail_vals: Iterable[Tuple[Number, Number]],
        hacked_verify: Dict[Number, Iterable[Number]],
    ):
        class IntegerBinaryBoundsSearch_DEBUG(IntegerBinaryBoundsSearch):
            counter = 0

            def get_verification_targets(
                self, lower: Number, upper: Number
            ) -> Optional[Iterable[Number]]:
                if self.counter in hacked_verify:
                    if VERBOSE:
                        print(f"FOUND A HACKED VERIFICATION AT {self.counter}")
                    targets = hacked_verify[self.counter]
                else:
                    targets = super().get_verification_targets(lower, upper)

                self.counter += 1

                if VERBOSE:
                    print(
                        f"Binary Search Verification started between {lower} and {upper} with probe targets {targets}"
                    )
                return targets

            def _set_state(self, state: BinaryBoundsSearch.BinSearchState):
                if VERBOSE:
                    print(f"NEW STATE: {state}")
                super()._set_state(state)

        class IntegerRangePrior_DEBUG(IntegerRangePrior):
            def initialise_search(
                self, initial_values: Dict[Number, bool]
            ) -> BinaryBoundsSearch:
                return IntegerBinaryBoundsSearch_DEBUG(
                    -(2 ** (self.path.type.bits - 1)),
                    2 ** (self.path.type.bits - 1) - 1,
                    initial_values=initial_values,
                )

        prior = IntegerRangePrior_DEBUG(self.fun, self.path, initial_probes)

        while not prior.is_done():
            probe = prior.select_next_probe()
            if VERBOSE:
                print(f"TESTING: {probe}")
            result = ProbeResult(probe, None)

            self.assertTrue(
                isinstance(probe, StaticProbe),
                f"Probe expected to be StaticProbe but is {type(probe)}.",
            )

            pvalue = probe.get_probe_value()
            valid_presult = True
            for start, end in fail_vals:
                if start is None:
                    valid_presult &= pvalue > end
                elif end is None:
                    valid_presult &= pvalue < start
                else:
                    valid_presult &= not (start <= pvalue <= end)

            if valid_presult:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS
            else:
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA

            if VERBOSE:
                print(f"RESULT: {result.is_exec_success()}")

            prior.update(result)  # None test case is used for test purposes only!

        self.assertEqual(
            prior.search_strat.state,
            BinaryBoundsSearch.BinSearchState.DONE,
            "Expected prior to be done.",
        )
        self.assertEqual(
            prior.search_strat.upper,
            target_upper,
            f"Expected prior to find {target_upper} as upper bound.",
        )
        self.assertEqual(
            prior.search_strat.lower,
            target_lower,
            f"Expected prior to find {target_lower} as lower bound.",
        )

    def test_find_bounds_verify_fail(self):
        self.run_verification_check(
            {5: True, 9: True},
            499,
            -200,
            [(None, -201), (500, None)],
            {0: [23, 55, 105, 110, 150, 200]},
        )

        # adjust lower bound after verification
        self.run_verification_check(
            {5: True, 9: True},
            499,
            151,
            [(None, -201), (100, 150), (500, None)],
            {0: [23, 55, 105, 110, 150, 200]},
        )

        # adjust upper bound after verification
        self.run_verification_check(
            {5: True, 9: True},
            99,
            -200,
            [(None, -201), (100, 150), (400, None)],
            {0: [23, 55, 105, 110, 150, 200]},
        )

        # return range where all numbers are tested in between
        self.run_verification_check(
            {5: True, 9: True}, 14, 4, [(None, 3), (15, 18), (25, None)], {}
        )

    def test_update(self):
        prior = self.init_prior({-35: True, 34: True}, -35, 34, invalid=False)
        prior_update_check(self, prior)

    def test_prior_result(self):
        prior = self.run_prior(-134217733, -35, 23599, 34, {-35: True, 34: True})
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertTrue(result.success, "Result expected to be successful.")
        self.assertEqual(
            result.result_data, f"{prior.search_strat.lower},{prior.search_strat.upper}"
        )

        prior = self.run_prior(
            -134217733, None, 23599, None, {-35: False, 34: False}, invalid=True
        )
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertFalse(result.success, "Result expected to be unsuccessful.")
        self.assertEqual(result.result_data, "None,None")

        prior = self.run_prior(-34, -34, -34, -34, {-34: True}, invalid=False)
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertFalse(result.success, "Result expected to be unsuccessful.")
        self.assertEqual(
            result.result_data, f"{prior.search_strat.lower},{prior.search_strat.upper}"
        )


class TestRealRangeSearch(unittest.TestCase):
    def setUp(self):
        fn_data = FunctionData(
            "add.cpp",
            "_Z3addff",
            "@$ f32, f32, f32 $@",
            "add(float, float)",
            2,
            "instrument",
        )
        fn_type = FunctionTypeDesc(float_t, float_t, float_t)
        self.fun = Function("add.cpp", "_Z3addff", fn_type, fn_data)
        paths = self.fun.get_paths()
        self.path = paths[0]
        self.assertGreater(len(paths), 0, "Available paths initialised incorrectly.")

        self.min_pos, self.max_pos = get_real_limit(self.path.type.bits)
        self.max_neg = -self.max_pos
        self.min_neg = -self.min_pos

    def init_prior(
        self,
        initial_probes: Dict[Number, bool],
        lower: Optional[int],
        upper: Optional[int],
        invalid: bool,
    ) -> RealRangePrior:
        prior = RealRangePrior(self.fun, self.path, initial_probes)

        self.assertEqual(
            prior.search_strat.lower,
            lower,
            f"Unexpected lower bound chosen for initial probes {initial_probes}",
        )
        self.assertEqual(
            prior.search_strat.upper,
            upper,
            f"Unexpected upper bound chosen for initial probes {initial_probes}",
        )
        self.assertEqual(
            prior.is_invalid(),
            invalid,
            f"Unexpected validity chosen for initial probes {initial_probes}",
        )
        return prior

    def test_init_range(self):
        self.init_prior({-5.4: True, 4.5: True, 20.6: True}, -5.4, 20.6, invalid=False)
        self.init_prior({-5.4: False, 4.5: True, 20.6: True}, 4.5, 20.6, invalid=False)
        self.init_prior({-5.4: True, 4.5: True, 20.6: False}, -5.4, 4.5, invalid=False)
        self.init_prior(
            {-5.4: False, -1.5: True, 4.5: True, 20.6: False}, -1.5, 4.5, invalid=False
        )
        self.init_prior(
            {-5.4: False, 4.5: False, 20.6: True}, 20.6, 20.6, invalid=False
        )

        # first diff (-5.4,0) = 5.4, second diff (0,20.6) = 20.6 --> 20.6
        self.init_prior(
            {-5.4: True, -1.5: True, 0: False, 4.5: True, 20.6: False},
            4.5,
            4.5,
            invalid=False,
        )

        # test invalids
        self.init_prior(
            {-5.4: False, 4.5: False, 20.6: False}, None, None, invalid=True
        )
        self.init_prior({}, None, None, invalid=True)

        # test bound shortcuts
        prior = RealRangePrior(
            self.fun, self.path, {-5.4: False, 4.5: True, 20.6: True}
        )

        self.assertAlmostEqual(
            prior.search_strat.min_bound, -5.4, "Unexpected minimum lower bound chosen."
        )
        self.assertAlmostEqual(
            prior.search_strat.max_bound,
            self.max_pos,
            "Unexpected maximum upper bound chosen.",
        )

        prior = RealRangePrior(
            self.fun, self.path, {-5.4: True, 4.5: True, 20.6: False}
        )

        self.assertAlmostEqual(
            prior.search_strat.min_bound,
            self.max_neg,
            "Unexpected minimum lower bound chosen.",
        )
        self.assertAlmostEqual(
            prior.search_strat.max_bound, 20.6, "Unexpected maximum upper bound chosen."
        )

        prior = RealRangePrior(
            self.fun, self.path, {-5.4: False, 4.5: True, 20.6: False, 40.7: False}
        )

        self.assertAlmostEqual(
            prior.search_strat.min_bound, -5.4, "Unexpected minimum lower bound chosen."
        )
        self.assertAlmostEqual(
            prior.search_strat.max_bound, 20.6, "Unexpected maximum upper bound chosen."
        )

    def test_isdone(self):
        prior = self.init_prior(
            {-5.4: True, 4.5: True, 20.6: False}, -5.4, 4.5, invalid=False
        )
        self.assertFalse(
            prior.is_done(), "Prior should not be done if valid and not executed."
        )

        prior = self.init_prior(
            {-5.4: False, 4.5: False, 20.6: False}, None, None, invalid=True
        )
        self.assertTrue(prior.is_done(), "Prior should be done if invalid after init.")

    def run_prior(
        self,
        target_lower: int,
        start_lower: int,
        target_upper: int,
        start_upper: int,
        initial_probes: Dict[Number, bool],
        invalid=False,
    ) -> IntegerRangePrior:
        prior = self.init_prior(
            initial_probes, start_lower, start_upper, invalid=invalid
        )
        while not prior.is_done():
            probe = prior.select_next_probe()
            result = ProbeResult(probe, None)

            self.assertTrue(
                isinstance(probe, StaticProbe),
                f"Probe expected to be StaticProbe but is {type(probe)}.",
            )

            if (
                probe.get_probe_value() > target_upper
                or probe.get_probe_value() < target_lower
            ):
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA
            else:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS

            prior.update(result)  # None test case is used for test purposes only!

        self.assertEqual(prior.is_invalid(), invalid, "Expected prior to be valid.")

        # print(f"Prior results LOW {prior.search_strat.lower} UP {prior.search_strat.upper}")

        if not invalid:
            self.assertEqual(
                prior.search_strat.state,
                BinaryBoundsSearch.BinSearchState.DONE,
                "Expected prior to be done.",
            )
            self.assertTrue(
                math.isclose(
                    prior.search_strat.upper,
                    target_upper,
                    rel_tol=REAL_TOLERANCE * 10,
                    abs_tol=REAL_TOLERANCE * 10,
                ),
                f"Expected prior to find {target_upper} as upper bound but found {prior.search_strat.upper}.",
            )
            self.assertTrue(
                math.isclose(
                    prior.search_strat.lower,
                    target_lower,
                    rel_tol=REAL_TOLERANCE * 10,
                    abs_tol=REAL_TOLERANCE * 10,
                ),
                f"Expected prior to find {target_lower} as lower bound but found {prior.search_strat.lower}.",
            )
        else:
            self.assertEqual(
                prior.search_strat.upper,
                None,
                "Expected invalid prior to return None result for boundary.",
            )
            self.assertEqual(
                prior.search_strat.lower,
                None,
                "Expected invalid prior to return None result for boundary.",
            )

        return prior

    def test_find_bounds(self):
        start_bounds = [(6.5, 10.2), (0, 500.2e12), (-2345.3e10, -499.2e5)]
        for lstart, ustart in start_bounds:
            self.run_prior(
                self.max_neg, lstart, self.max_pos, ustart, {lstart: True, ustart: True}
            )
            self.run_prior(
                self.max_neg, lstart, 3493.496e23, ustart, {lstart: True, ustart: True}
            )
            self.run_prior(
                -1342.17733e23,
                lstart,
                self.max_pos,
                ustart,
                {lstart: True, ustart: True},
            )
            self.run_prior(
                -134217.733e31, lstart, 235.332e20, ustart, {lstart: True, ustart: True}
            )

            if lstart > 0:
                self.run_prior(
                    0, lstart, self.max_pos, ustart, {lstart: True, ustart: True}
                )

        self.run_prior(0, 0, 0, 0, {0: True})
        self.run_prior(-1.0, 0, 1.0, 0, {0: True})

    def run_verification_check(
        self,
        initial_probes: Dict[Number, bool],
        target_upper: Number,
        target_lower: Number,
        fail_vals: Iterable[Tuple[Number, Number]],
        hacked_verify: Dict[Number, Iterable[Number]],
    ):
        class RealBinaryBoundsSearch_DEBUG(RealBinaryBoundsSearch):
            counter = 0

            def get_verification_targets(
                self, lower: Number, upper: Number
            ) -> Optional[Iterable[Number]]:
                if self.counter in hacked_verify:
                    if VERBOSE:
                        print(f"FOUND A HACKED VERIFICATION AT {self.counter}")
                    targets = hacked_verify[self.counter]
                else:
                    targets = super().get_verification_targets(lower, upper)

                self.counter += 1

                if VERBOSE:
                    print(
                        f"Binary Search Verification started between {lower} and {upper} with probe targets {targets}"
                    )
                return targets

            def _set_state(self, state: BinaryBoundsSearch.BinSearchState):
                if VERBOSE:
                    print(f"NEW STATE: {state}")
                super()._set_state(state)

        class RealRangePrior_DEBUG(RealRangePrior):
            def initialise_search(
                self, initial_values: Dict[Number, bool]
            ) -> BinaryBoundsSearch:
                _, max_pos = get_real_limit(self.path.type.bits)
                max_neg = -max_pos

                bin_search = RealBinaryBoundsSearch_DEBUG(
                    max_neg, max_pos, initial_values=initial_values
                )
                return bin_search

        prior = RealRangePrior_DEBUG(self.fun, self.path, initial_probes)

        while not prior.is_done():
            probe = prior.select_next_probe()
            if VERBOSE:
                print(f"TESTING: {probe}")
            result = ProbeResult(probe, None)

            self.assertTrue(
                isinstance(probe, StaticProbe),
                f"Probe expected to be StaticProbe but is {type(probe)}.",
            )

            pvalue = probe.get_probe_value()
            valid_presult = True
            for start, end in fail_vals:
                if start is None:
                    valid_presult &= pvalue > end
                elif end is None:
                    valid_presult &= pvalue < start
                else:
                    valid_presult &= not (start <= pvalue <= end)

            if valid_presult:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS
            else:
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA

            if VERBOSE:
                print(f"RESULT: {result.is_exec_success()}")

            prior.update(result)  # None test case is used for test purposes only!

        self.assertEqual(
            prior.search_strat.state,
            BinaryBoundsSearch.BinSearchState.DONE,
            "Expected prior to be done.",
        )
        self.assertTrue(
            math.isclose(
                prior.search_strat.upper,
                target_upper,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {target_upper} as upper bound but found {prior.search_strat.upper}.",
        )
        self.assertTrue(
            math.isclose(
                prior.search_strat.lower,
                target_lower,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {target_lower} as lower bound but found {prior.search_strat.lower}.",
        )

    def test_find_bounds_verify_fail(self):
        self.run_verification_check(
            {5: True, 9: True},
            499,
            -200,
            [(None, -201), (500, None)],
            {0: [23, 55, 105, 110, 150, 200]},
        )

        # adjust lower bound after verification
        self.run_verification_check(
            {5: True, 9: True},
            499,
            151,
            [(None, -201), (100, 150), (500, None)],
            {0: [23, 55, 105, 110, 150, 200]},
        )

        # adjust upper bound after verification
        self.run_verification_check(
            {5: True, 9: True},
            99,
            -200,
            [(None, -201), (100, 150), (400, None)],
            {0: [23, 55, 105, 110, 150, 200]},
        )

        # return range where all numbers are tested in between
        self.run_verification_check(
            {5: True, 9: True}, 14.9, 3.01, [(None, 3), (15, 18), (25, None)], {}
        )

        # run test for double data type
        fn_data = FunctionData(
            "add.cpp",
            "_Z3adddd",
            "@$ f64, f64, f64 $@",
            "add(double, double)",
            2,
            "instrument",
        )
        fn_type = FunctionTypeDesc(double_t, double_t, double_t)
        self.fun = Function("add.cpp", "_Z3adddd", fn_type, fn_data)
        paths = self.fun.get_paths()
        self.path = paths[0]
        self.assertGreater(len(paths), 0, "Available paths initialised incorrectly.")

        self.min_pos, self.max_pos = get_real_limit(self.path.type.bits)
        self.max_neg = -self.max_pos
        self.min_neg = -self.min_pos

        self.run_verification_check(
            {self.max_neg / 2: True, self.max_pos / 2: True},
            self.max_pos,
            self.max_neg,
            [],
            {},
        )

    def test_update(self):
        prior = self.init_prior({-35.3: True, 34.4: True}, -35.3, 34.4, invalid=False)
        prior_update_check(self, prior)

    def test_prior_result(self):
        prior = self.run_prior(-58.34, -35.3, 60.34, 34.4, {-35.3: True, 34.4: True})
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertTrue(result.success, "Result expected to be successful.")

        lower = round(prior.search_strat.lower, REAL_ACCURACY)
        upper = round(prior.search_strat.upper, REAL_ACCURACY)
        self.assertEqual(result.result_data, f"{lower},{upper}")

        prior = self.run_prior(
            -324e20, None, 23599e12, None, {-35.3: False, 34.4: False}, invalid=True
        )
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertFalse(result.success, "Result expected to be unsuccessful.")
        self.assertEqual(result.result_data, "None,None")

        prior = self.run_prior(5.3, 5.3, 5.3, 5.3, {5.3: True}, invalid=False)
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertFalse(result.success, "Result expected to be unsuccessful.")

        lower = round(prior.search_strat.lower, REAL_ACCURACY)
        upper = round(prior.search_strat.upper, REAL_ACCURACY)
        self.assertEqual(result.result_data, f"{lower},{upper}")


class TestIntegerOffsetSearch(unittest.TestCase):
    def setUp(self):
        fn_data = FunctionData(
            "add.cpp",
            "_Z3addii",
            "@$ i32, i32, i32 $@",
            "add(int, int)",
            2,
            "instrument",
        )
        fn_type = FunctionTypeDesc(i32_t, i32_t, i32_t)
        self.fun = Function("add.cpp", "_Z3addii", fn_type, fn_data)
        paths = self.fun.get_paths()
        self.path = paths[0]
        self.assertGreater(len(paths), 0, "Available paths initialised incorrectly.")

        self.max_int = 2 ** (self.path.type.bits - 1) - 1
        self.min_int = -(2 ** (self.path.type.bits - 1))

    def init_prior(self) -> IntegerOffsetPrior:
        prior = IntegerOffsetPrior(self.fun, self.path)

        self.assertEqual(
            prior.state,
            BoundedPrior.SearchState.SEARCH_UPPER,
            "Unexpected search state after initialisation.",
        )
        self.assertFalse(prior.is_invalid(), "Not expected to be invalid after init.")

        return prior

    def test_init_range(self):
        self.init_prior()

    def run_prior(self, target_lower: int, target_upper: int) -> IntegerOffsetPrior:
        prior = self.init_prior()

        while not prior.is_done():
            probe = prior.select_next_probe()
            result = ProbeResult(probe, None)

            self.assertTrue(
                prior.state != BoundedPrior.SearchState.DONE
                and isinstance(probe, OffsetProbe),
                f"Probe not as expected but is {type(probe)}.",
            )

            if isinstance(probe, OffsetProbe) and (
                (
                    prior.state == BoundedPrior.SearchState.SEARCH_UPPER
                    and probe.get_probe_value() > target_upper
                )
                or (
                    prior.state == BoundedPrior.SearchState.SEARCH_LOWER
                    and probe.get_probe_value() * -1 > target_lower
                )
            ):
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA
            else:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS

            prior.update(result)  # None test case is used for test purposes only!

        self.assertFalse(prior.is_invalid(), "Expected prior to be valid.")
        self.assertEqual(
            prior.state, BoundedPrior.SearchState.DONE, "Expected prior to be done."
        )
        self.assertEqual(
            prior.upper_search_strat.final_bound,
            target_upper,
            f"Expected prior to find {target_upper} as upper bound.",
        )
        self.assertEqual(
            prior.lower_search_strat.final_bound,
            target_lower,
            f"Expected prior to find {target_lower} as lower bound.",
        )

        return prior

    def test_find_bounds(self):
        self.run_prior(5, 10)
        self.run_prior(5, 0)
        self.run_prior(0, 10)
        self.run_prior(0, 0)
        self.run_prior(0, self.max_int)
        self.run_prior(self.max_int, 0)
        self.run_prior(349, 13)

    def run_verification_check(
        self,
        upper_max_bound: Number,
        upper_fail_vals: Iterable[Tuple[Number, Number]],
        upper_target: Number,
        lower_max_bound: Number,
        lower_fail_vals: Iterable[Tuple[Number, Number]],
        lower_target: Number,
        hacked_verify: Dict[Number, Iterable[Number]],
    ):
        # override IntegerOffsetPrior to force verification targets
        class IntegerOffsetPrior_DEBUG(IntegerOffsetPrior):
            counter = 0

            def _get_verification_targets(
                self, search: BinarySearch
            ) -> Optional[Iterable[Number]]:
                if self.counter in hacked_verify:
                    if VERBOSE:
                        print(f"FOUND A HACKED VERIFICATION AT {self.counter}")
                    targets = hacked_verify[self.counter]
                else:
                    targets = super()._get_verification_targets(search)

                self.counter += 1

                if VERBOSE:
                    print(
                        f"Binary Search Verification started between 0 and {search.final_bound} with probe targets {targets}"
                    )
                return targets

            def _set_state(self, state: BoundedPrior.SearchState):
                if VERBOSE:
                    print(f"NEW STATE: {state}")
                super()._set_state(state)

        prior = IntegerOffsetPrior_DEBUG(self.fun, self.path)

        while not prior.is_done():
            probe = prior.select_next_probe()
            if VERBOSE:
                print(f"TESTING: {probe}")
            result = ProbeResult(probe, None)

            self.assertTrue(
                prior.state != BoundedPrior.SearchState.DONE
                and isinstance(probe, OffsetProbe),
                f"Probe not as expected but is {type(probe)}.",
            )

            if (
                prior.state == BoundedPrior.SearchState.SEARCH_UPPER
                or prior.state == BoundedPrior.SearchState.UPPER_VERIFICATION
            ):
                pvalue = probe.get_probe_value()
                valid_presult = pvalue <= upper_max_bound
                for start, end in upper_fail_vals:
                    valid_presult &= pvalue < start or pvalue > end
            elif (
                prior.state == BoundedPrior.SearchState.SEARCH_LOWER
                or prior.state == BoundedPrior.SearchState.LOWER_VERIFICATION
            ):
                pvalue = probe.get_probe_value() * -1
                valid_presult = pvalue <= lower_max_bound
                for start, end in lower_fail_vals:
                    valid_presult &= pvalue < start or pvalue > end
            else:
                self.fail(f"Invalid prior state after probe evaluation {prior.state}")

            if valid_presult:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS
                if VERBOSE:
                    print("SUCCESS")
            else:
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA
                if VERBOSE:
                    print("FAIL")

            prior.update(result)  # None test case is used for test purposes only!

        self.assertFalse(prior.is_invalid(), "Expected prior to be valid.")
        self.assertEqual(
            prior.state, BoundedPrior.SearchState.DONE, "Expected prior to be done."
        )
        self.assertEqual(
            prior.upper_search_strat.final_bound,
            upper_target,
            f"Expected prior to find {upper_target} as upper bound.",
        )
        self.assertEqual(
            prior.lower_search_strat.final_bound,
            lower_target,
            f"Expected prior to find {lower_target} as lower bound.",
        )

    def test_find_bounds_verify_fail(self):
        self.run_verification_check(
            400, [(40, 50)], 39, 300, [], 300, {0: [30, 35, 42, 46, 60, 200]}
        )

        self.run_verification_check(
            400,
            [],
            400,
            5000,
            [(3100, 3200)],
            3099,
            {1: [35, 155, 1566, 244, 3115, 3199]},
        )

        # Test first fail in verification
        self.run_verification_check(
            400, [(40, 50)], 39, 300, [], 300, {0: [40, 45, 50, 61]}
        )

        # Test first fail in verification
        self.run_verification_check(
            400, [], 400, 5000, [(3100, 3200)], 3099, {1: [3123, 3400, 3405]}
        )

        fn_data = FunctionData(
            "add.cpp",
            "_Z3addii",
            "@$ i64, i64, i64 $@",
            "add(int, int)",
            2,
            "instrument",
        )
        fn_type = FunctionTypeDesc(i64_t, i64_t, i64_t)
        self.fun = Function("add.cpp", "_Z3addii", fn_type, fn_data)
        paths = self.fun.get_paths()
        self.path = paths[0]
        self.assertGreater(len(paths), 0, "Available paths initialised incorrectly.")

        self.max_int = 2 ** (self.path.type.bits - 1) - 1
        self.min_int = -(2 ** (self.path.type.bits - 1))
        self.run_verification_check(
            3,
            [],
            3,
            9223372036854775808,
            [(7069083032380901136, 7069083032380901136)],
            7069083032380901135,
            {
                1: [
                    8017592644271433344,
                    512785532786768516,
                    8223131078824675329,
                    6284067516782266113,
                    6836160565201588871,
                    2848623699286436489,
                    6718978620038693642,
                    7069083032380901136,
                    3998408631712509587,
                    1694509785049988761,
                    3947920959936256411,
                    4908616807863520290,
                    2079012785635087526,
                    7371593622109740469,
                    2798365133792951993,
                    1153838086712650566,
                    339708350528082376,
                    3155119514743039560,
                    6133607001479635788,
                    1910444492485076304,
                    187891479186685906,
                    2239690827236022356,
                    8215133603322769875,
                    5030112268908400351,
                    8242380280981873380,
                    6665714210786571496,
                    1249245793838910703,
                    8800098160353328757,
                    5433908787818618363,
                    3072948510430934270,
                ]
            },
        )

        self.run_verification_check(
            3,
            [],
            3,
            9223372036854775808,
            [(8559802010813768848, 8559802010813768848)],
            8559802010813768847,
            {
                1: [
                    335446990719811072,
                    6503277980993031424,
                    5212604295690172421,
                    3570768080391747980,
                    4223105336765619983,
                    7936273150500417807,
                    8559802010813768848,
                    8165961956204658833,
                    7754708996688390812,
                    3651416167080584110,
                    7609236531298307501,
                    1387822548415528495,
                    5585929138155763889,
                    5547659374701485239,
                    482348720901937727,
                    4677299792248478915,
                    7217083326301504708,
                    8173738490258911175,
                    1166326002164381010,
                    4300724910272297298,
                    4175446907632450644,
                    3852827712956724822,
                    7576973784238501847,
                    5025781789655560540,
                    6423333591157828958,
                    3807901971273448036,
                    3191678067490483180,
                    5504889308361584626,
                    4374163078889332981,
                    1381261653532159097,
                ]
            },
        )

    def test_isdone(self):
        prior = self.init_prior()
        self.assertFalse(
            prior.is_done(), "Prior should not be done if valid and not executed."
        )

        prior = self.run_prior(5, 10)
        self.assertTrue(prior.is_done(), "Prior should be done if valid and executed.")

    def test_update(self):
        prior = self.init_prior()
        prior_update_check(self, prior)

    def check_result(self, lower_target: Number, upper_target: Number, success: bool):
        prior = self.run_prior(lower_target, upper_target)
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertEqual(result.success, success, "Success result not as expected.")
        self.assertEqual(
            result.result_data,
            f"{prior.lower_search_strat.final_bound},{prior.upper_search_strat.final_bound}",
        )

    def test_prior_result(self):
        self.check_result(234, 23, True)
        self.check_result(0, 10, True)
        self.check_result(5, 0, True)
        self.check_result(0, 0, False)


class TestRealOffsetSearch(unittest.TestCase):
    def setUp(self):
        fn_data = FunctionData(
            "add.cpp",
            "_Z3addff",
            "@$ f32, f32, f32 $@",
            "add(float, float)",
            2,
            "instrument",
        )
        fn_type = FunctionTypeDesc(float_t, float_t, float_t)
        self.fun = Function("add.cpp", "_Z3addff", fn_type, fn_data)
        paths = self.fun.get_paths()
        self.path = paths[0]
        self.assertGreater(len(paths), 0, "Available paths initialised incorrectly.")

        self.min_pos, self.max_pos = get_real_limit(self.path.type.bits)
        self.max_neg = -self.max_pos
        self.min_neg = -self.min_pos

    def init_prior(self) -> RealOffsetPrior:
        prior = RealOffsetPrior(self.fun, self.path)

        self.assertEqual(
            prior.state,
            BoundedPrior.SearchState.SEARCH_UPPER,
            "Unexpected search state after initialisation.",
        )
        self.assertFalse(prior.is_invalid(), "Not expected to be invalid after init.")

        return prior

    def test_init_range(self):
        self.init_prior()

    def run_prior(self, target_lower: float, target_upper: float) -> RealOffsetPrior:
        prior = self.init_prior()

        while not prior.is_done():
            probe = prior.select_next_probe()
            result = ProbeResult(probe, None)

            self.assertTrue(
                prior.state != BoundedPrior.SearchState.DONE
                and isinstance(probe, OffsetProbe),
                f"Probe not as expected but is {type(probe)}.",
            )

            if (
                prior.state == BoundedPrior.SearchState.SEARCH_UPPER
                and probe.get_probe_value() > target_upper
            ) or (
                prior.state == BoundedPrior.SearchState.SEARCH_LOWER
                and probe.get_probe_value() * -1 > target_lower
            ):
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA
            else:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS

            prior.update(result)  # None test case is used for test purposes only!

        # print(f"Prior results LOW {prior.lower_search_strat.final_bound} UP {prior.upper_search_strat.final_bound}")

        self.assertFalse(prior.is_invalid(), "Expected prior to be valid.")
        self.assertEqual(
            prior.state, BoundedPrior.SearchState.DONE, "Expected prior to be done."
        )

        self.assertTrue(
            math.isclose(
                prior.upper_search_strat.final_bound,
                target_upper,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {target_upper} as upper bound but found {prior.upper_search_strat.final_bound}.",
        )
        self.assertTrue(
            math.isclose(
                prior.lower_search_strat.final_bound,
                target_lower,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {target_lower} as lower bound but found {prior.lower_search_strat.final_bound}.",
        )

        return prior

    def test_find_bounds(self):
        self.run_prior(5.34, 10.13)
        self.run_prior(0.78, 2.03e22)
        self.run_prior(0, 1.02e10)
        self.run_prior(0, 0)
        self.run_prior(0, self.max_pos)
        self.run_prior(self.max_pos, 0)
        self.run_prior(3.49e2, 13.56)
        self.run_prior(0.01, 0.04)

    def run_verification_check(
        self,
        upper_max_bound: Number,
        upper_fail_vals: Iterable[Tuple[Number, Number]],
        upper_target: Number,
        lower_max_bound: Number,
        lower_fail_vals: Iterable[Tuple[Number, Number]],
        lower_target: Number,
        hacked_verify: Dict[Number, Iterable[Number]],
    ):
        # override RealOffsetPrior to force verification targets
        class RealOffsetPrior_DEBUG(RealOffsetPrior):
            counter = 0

            def _get_verification_targets(
                self, search: BinarySearch
            ) -> Optional[Iterable[Number]]:
                if self.counter in hacked_verify:
                    if VERBOSE:
                        print(f"FOUND A HACKED VERIFICATION AT {self.counter}")
                    targets = hacked_verify[self.counter]
                else:
                    targets = super()._get_verification_targets(search)

                self.counter += 1

                if VERBOSE:
                    print(
                        f"Binary Search Verification started between 0 and {search.final_bound} with probe targets {targets}"
                    )
                return targets

            def _set_state(self, state: BoundedPrior.SearchState):
                if VERBOSE:
                    print(f"NEW STATE: {state}")
                super()._set_state(state)

        prior = RealOffsetPrior_DEBUG(self.fun, self.path)

        while not prior.is_done():
            probe = prior.select_next_probe()
            if VERBOSE:
                print(f"TESTING: {probe}")
            result = ProbeResult(probe, None)

            self.assertTrue(
                prior.state != BoundedPrior.SearchState.DONE
                and isinstance(probe, OffsetProbe),
                f"Probe not as expected but is {type(probe)}.",
            )

            if (
                prior.state == BoundedPrior.SearchState.SEARCH_UPPER
                or prior.state == BoundedPrior.SearchState.UPPER_VERIFICATION
            ):
                pvalue = probe.get_probe_value()
                valid_presult = pvalue <= upper_max_bound
                for start, end in upper_fail_vals:
                    valid_presult &= pvalue <= start or pvalue > end
            elif (
                prior.state == BoundedPrior.SearchState.SEARCH_LOWER
                or prior.state == BoundedPrior.SearchState.LOWER_VERIFICATION
            ):
                pvalue = probe.get_probe_value() * -1
                valid_presult = pvalue <= lower_max_bound
                for start, end in lower_fail_vals:
                    valid_presult &= pvalue <= start or pvalue > end
            else:
                self.fail(f"Invalid prior state after probe evaluation {prior.state}")

            if valid_presult:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS
            else:
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA

            prior.update(result)  # None test case is used for test purposes only!

        self.assertFalse(prior.is_invalid(), "Expected prior to be valid.")
        self.assertEqual(
            prior.state, BoundedPrior.SearchState.DONE, "Expected prior to be done."
        )
        self.assertTrue(
            math.isclose(
                prior.upper_search_strat.final_bound,
                upper_target,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {upper_target} as upper bound but found {prior.upper_search_strat.final_bound}.",
        )
        self.assertTrue(
            math.isclose(
                prior.lower_search_strat.final_bound,
                lower_target,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {lower_target} as lower bound but found {prior.lower_search_strat.final_bound}.",
        )

    def test_find_bounds_verify_fail(self):
        self.run_verification_check(
            400.23, [(40, 50.55)], 40, 300, [], 300, {0: [30, 35, 42, 46, 60, 200]}
        )

        self.run_verification_check(
            400,
            [],
            400,
            5000,
            [(3100, 3200)],
            3100,
            {1: [35, 155, 1566, 244, 3115, 3199]},
        )

        # # Test first fail in verification
        self.run_verification_check(
            400, [(40, 50)], 40, 300, [], 300, {0: [40, 45, 50, 61]}
        )

        # # Test first fail in verification
        self.run_verification_check(
            400, [], 400, 5000, [(3100, 3200)], 3100, {1: [3123, 3400, 3405]}
        )

        self.run_verification_check(
            3.0, [(0.02, 0.05)], 0.01, 300, [], 300, {0: [1.4, 2.3, 0.025, 0.026]}
        )

    def test_isdone(self):
        prior = self.init_prior()
        self.assertFalse(
            prior.is_done(), "Prior should not be done if valid and not executed."
        )

        prior = self.run_prior(5.34, 10.12)
        self.assertTrue(prior.is_done(), "Prior should be done if valid and executed.")

    def test_update(self):
        prior = self.init_prior()
        prior_update_check(self, prior)

    def check_result(self, lower_target: Number, upper_target: Number, success: bool):
        prior = self.run_prior(lower_target, upper_target)
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertEqual(result.success, success, "Success result not as expected.")

        lower = round(prior.lower_search_strat.final_bound, REAL_ACCURACY)
        upper = round(prior.upper_search_strat.final_bound, REAL_ACCURACY)
        self.assertEqual(result.result_data, f"{lower},{upper}")

    def test_prior_result(self):
        self.check_result(5.34, 10.13, True)
        self.check_result(0, 10.13, True)
        self.check_result(5.34, 0, True)
        self.check_result(0, 0, False)


class TestIntegerScaleSearch(unittest.TestCase):
    def setUp(self):
        fn_data = FunctionData(
            "add.cpp",
            "_Z3addii",
            "@$ i32, i32, i32 $@",
            "add(int, int)",
            2,
            "instrument",
        )
        fn_type = FunctionTypeDesc(i32_t, i32_t, i32_t)
        self.fun = Function("add.cpp", "_Z3addii", fn_type, fn_data)
        paths = self.fun.get_paths()
        self.path = paths[0]
        self.assertGreater(len(paths), 0, "Available paths initialised incorrectly.")

        self.max_int = 2 ** (self.path.type.bits - 1) - 1
        self.min_int = -(2 ** (self.path.type.bits - 1))

    def init_prior(self) -> IntegerScalePrior:
        prior = IntegerScalePrior(self.fun, self.path)

        self.assertEqual(
            prior.state,
            BoundedPrior.SearchState.SEARCH_UPPER,
            "Unexpected search state after initialisation.",
        )
        self.assertFalse(prior.is_invalid(), "Not expected to be invalid after init.")

        return prior

    def test_init_range(self):
        self.init_prior()

    def run_prior(self, target_lower: int, target_upper: int) -> IntegerScalePrior:
        prior = self.init_prior()

        while not prior.is_done():
            probe = prior.select_next_probe()
            result = ProbeResult(probe, None)

            self.assertTrue(
                prior.state != BoundedPrior.SearchState.DONE
                and isinstance(probe, ScaleProbe),
                f"Probe not as expected but is {type(probe)}.",
            )

            if (
                prior.state == BoundedPrior.SearchState.SEARCH_UPPER
                and probe.get_probe_value() - 1 > target_upper
            ) or (
                prior.state == BoundedPrior.SearchState.SEARCH_LOWER
                and 1 - probe.get_probe_value() > target_lower
            ):
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA
            else:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS

            prior.update(result)  # None test case is used for test purposes only!

        self.assertFalse(prior.is_invalid(), "Expected prior to be valid.")
        self.assertEqual(
            prior.state, BoundedPrior.SearchState.DONE, "Expected prior to be done."
        )
        self.assertEqual(
            prior.upper_search_strat.final_bound,
            target_upper,
            f"Expected prior to find {target_upper} as upper bound.",
        )
        self.assertEqual(
            prior.lower_search_strat.final_bound,
            target_lower,
            f"Expected prior to find {target_lower} as lower bound.",
        )

        return prior

    def test_find_bounds(self):
        self.run_prior(5, 10)
        self.run_prior(5, 0)
        self.run_prior(0, 10)
        self.run_prior(0, 0)
        self.run_prior(0, self.max_int)
        self.run_prior(self.max_int, 0)
        self.run_prior(349, 13)

    def run_verification_check(
        self,
        upper_max_bound: Number,
        upper_fail_vals: Iterable[Tuple[Number, Number]],
        upper_target: Number,
        lower_max_bound: Number,
        lower_fail_vals: Iterable[Tuple[Number, Number]],
        lower_target: Number,
        hacked_verify: Dict[Number, Iterable[Number]],
        custom_start=False,
        invalid=False,
    ):
        # override IntegerScalePrior to force verification targets
        class IntegerScalePrior_DEBUG(IntegerScalePrior):
            counter = 0

            def __init__(self, function: Function, path, custom_start=False):
                super().__init__(function, path)

                if custom_start:
                    max_val = 2 ** (path.type.bits - 1)
                    self.upper_search_strat = IntegerBinarySearch(max_val, 0, 2)

            def _get_verification_targets(
                self, search: BinarySearch
            ) -> Optional[Iterable[Number]]:
                if self.counter in hacked_verify:
                    if VERBOSE:
                        print(f"FOUND A HACKED VERIFICATION AT {self.counter}")
                    targets = hacked_verify[self.counter]
                else:
                    targets = super()._get_verification_targets(search)

                self.counter += 1

                if VERBOSE:
                    print(
                        f"Binary Search Verification started between 0 and {search.final_bound} with probe targets {targets}"
                    )
                return targets

            def _set_state(self, state: BoundedPrior.SearchState):
                if VERBOSE:
                    print(f"NEW STATE: {state}")
                super()._set_state(state)

        prior = IntegerScalePrior_DEBUG(self.fun, self.path, custom_start)

        while not prior.is_done():
            probe = prior.select_next_probe()
            if VERBOSE:
                print(f"TESTING: {probe}")
            result = ProbeResult(probe, None)

            self.assertTrue(
                prior.state != BoundedPrior.SearchState.DONE
                and isinstance(probe, ScaleProbe),
                f"Probe not as expected but is {type(probe)}.",
            )

            if (
                prior.state == BoundedPrior.SearchState.SEARCH_UPPER
                or prior.state == BoundedPrior.SearchState.UPPER_VERIFICATION
            ):
                pvalue = probe.get_probe_value() - 1
                valid_presult = pvalue <= upper_max_bound
                for start, end in upper_fail_vals:
                    valid_presult &= pvalue < start or pvalue > end
            elif (
                prior.state == BoundedPrior.SearchState.SEARCH_LOWER
                or prior.state == BoundedPrior.SearchState.LOWER_VERIFICATION
            ):
                pvalue = 1 - probe.get_probe_value()
                valid_presult = pvalue <= lower_max_bound
                for start, end in lower_fail_vals:
                    valid_presult &= pvalue < start or pvalue > end
            else:
                self.fail(f"Invalid prior state after probe evaluation {prior.state}")

            if valid_presult:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS
            else:
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA

            prior.update(result)  # None test case is used for test purposes only!

        if invalid:
            self.assertTrue(prior.is_invalid(), "Expected prior to be invalid.")
        else:
            self.assertFalse(prior.is_invalid(), "Expected prior to be valid.")
            self.assertEqual(
                prior.state, BoundedPrior.SearchState.DONE, "Expected prior to be done."
            )
            self.assertEqual(
                prior.upper_search_strat.final_bound,
                upper_target,
                f"Expected prior to find {upper_target} as upper bound.",
            )
            self.assertEqual(
                prior.lower_search_strat.final_bound,
                lower_target,
                f"Expected prior to find {lower_target} as lower bound.",
            )

    def test_find_bounds_verify_fail(self):
        self.run_verification_check(
            400, [(40, 50)], 39, 300, [], 300, {0: [30, 35, 42, 46, 60, 200]}
        )

        self.run_verification_check(
            400,
            [],
            400,
            5000,
            [(3100, 3200)],
            3099,
            {1: [35, 155, 1566, 244, 3115, 3199]},
        )

        # Test first fail in verification
        self.run_verification_check(
            400, [(40, 50)], 39, 300, [], 300, {0: [40, 45, 50, 61]}
        )

        # Test first fail in verification
        self.run_verification_check(
            400, [], 400, 5000, [(3100, 3200)], 3099, {1: [3123, 3400, 3405]}
        )

        # Test verification fails for all except zero
        self.run_verification_check(
            10, [(1, 1)], 0, 5000, [], 5000, {}, custom_start=True
        )

    def test_isdone(self):
        prior = self.init_prior()
        self.assertFalse(
            prior.is_done(), "Prior should not be done if valid and not executed."
        )

        prior = self.run_prior(5, 10)
        self.assertTrue(prior.is_done(), "Prior should be done if valid and executed.")

    def test_update(self):
        prior = self.init_prior()
        prior_update_check(self, prior)

    def check_result(self, lower_target: Number, upper_target: Number, success: bool):
        prior = self.run_prior(lower_target, upper_target)
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertEqual(result.success, success, "Success result not as expected.")
        self.assertEqual(
            result.result_data,
            f"{prior.lower_search_strat.final_bound},{prior.upper_search_strat.final_bound}",
        )

    def test_prior_result(self):
        self.check_result(234, 23, True)
        self.check_result(0, 10, True)
        self.check_result(5, 0, True)
        self.check_result(0, 0, False)


class TestRealScaleSearch(unittest.TestCase):
    def setUp(self):
        fn_data = FunctionData(
            "add.cpp",
            "_Z3addff",
            "@$ f32, f32, f32 $@",
            "add(float, float)",
            2,
            "instrument",
        )
        fn_type = FunctionTypeDesc(float_t, float_t, float_t)
        self.fun = Function("add.cpp", "_Z3addff", fn_type, fn_data)
        paths = self.fun.get_paths()
        self.path = paths[0]
        self.assertGreater(len(paths), 0, "Available paths initialised incorrectly.")

        self.min_pos, self.max_pos = get_real_limit(self.path.type.bits)
        self.max_neg = -self.max_pos
        self.min_neg = -self.min_pos

    def init_prior(self) -> RealScalePrior:
        prior = RealScalePrior(self.fun, self.path)

        self.assertEqual(
            prior.state,
            BoundedPrior.SearchState.SEARCH_UPPER,
            "Unexpected search state after initialisation.",
        )
        self.assertFalse(prior.is_invalid(), "Not expected to be invalid after init.")

        return prior

    def test_init_range(self):
        self.init_prior()

    def run_prior(self, target_lower: float, target_upper: float) -> RealScalePrior:
        prior = self.init_prior()

        while not prior.is_done():
            probe = prior.select_next_probe()
            result = ProbeResult(probe, None)

            self.assertTrue(
                prior.state != BoundedPrior.SearchState.DONE
                and isinstance(probe, ScaleProbe),
                f"Probe not as expected but is {type(probe)}.",
            )

            if (
                prior.state == BoundedPrior.SearchState.SEARCH_UPPER
                and probe.get_probe_value() - 1 > target_upper
            ) or (
                prior.state == BoundedPrior.SearchState.SEARCH_LOWER
                and 1 - probe.get_probe_value() > target_lower
            ):
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA
            else:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS

            prior.update(result)  # None test case is used for test purposes only!

        # print(f"Prior results LOW {prior.lower_search_strat.final_bound} UP {prior.upper_search_strat.final_bound}")

        self.assertFalse(prior.is_invalid(), "Expected prior to be valid.")
        self.assertEqual(
            prior.state, BoundedPrior.SearchState.DONE, "Expected prior to be done."
        )

        self.assertTrue(
            math.isclose(
                prior.upper_search_strat.final_bound,
                target_upper,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {target_upper} as upper bound but found {prior.upper_search_strat.final_bound}.",
        )
        self.assertTrue(
            math.isclose(
                prior.lower_search_strat.final_bound,
                target_lower,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {target_lower} as lower bound but found {prior.lower_search_strat.final_bound}.",
        )

        return prior

    def test_find_bounds(self):
        self.run_prior(5.34, 10.13)
        self.run_prior(0.78, 2.03e22)
        self.run_prior(0, 1.02e10)
        self.run_prior(0, 0)
        self.run_prior(0, self.max_pos)
        self.run_prior(self.max_pos, 0)
        self.run_prior(3.49e2, 13.56)

    def run_verification_check(
        self,
        upper_max_bound: Number,
        upper_fail_vals: Iterable[Tuple[Number, Number]],
        upper_target: Number,
        lower_max_bound: Number,
        lower_fail_vals: Iterable[Tuple[Number, Number]],
        lower_target: Number,
        hacked_verify: Dict[Number, Iterable[Number]],
    ):
        # override RealScalePrior to force verification targets
        class RealScalePrior_DEBUG(RealScalePrior):
            counter = 0

            def _get_verification_targets(
                self, search: BinarySearch
            ) -> Optional[Iterable[Number]]:
                if self.counter in hacked_verify:
                    if VERBOSE:
                        print(f"FOUND A HACKED VERIFICATION AT {self.counter}")
                    targets = hacked_verify[self.counter]
                else:
                    targets = super()._get_verification_targets(search)

                self.counter += 1

                if VERBOSE:
                    print(
                        f"Binary Search Verification started between 0 and {search.final_bound} with probe targets {targets}"
                    )
                return targets

            def _set_state(self, state: BoundedPrior.SearchState):
                if VERBOSE:
                    print(f"NEW STATE: {state}")
                super()._set_state(state)

        prior = RealScalePrior_DEBUG(self.fun, self.path)

        while not prior.is_done():
            probe = prior.select_next_probe()
            if VERBOSE:
                print(f"TESTING: {probe}")
            result = ProbeResult(probe, None)

            self.assertTrue(
                prior.state != BoundedPrior.SearchState.DONE
                and isinstance(probe, ScaleProbe),
                f"Probe not as expected but is {type(probe)}.",
            )

            if (
                prior.state == BoundedPrior.SearchState.SEARCH_UPPER
                or prior.state == BoundedPrior.SearchState.UPPER_VERIFICATION
            ):
                pvalue = probe.get_probe_value() - 1
                valid_presult = pvalue <= upper_max_bound
                for start, end in upper_fail_vals:
                    valid_presult &= pvalue <= start or pvalue > end
            elif (
                prior.state == BoundedPrior.SearchState.SEARCH_LOWER
                or prior.state == BoundedPrior.SearchState.LOWER_VERIFICATION
            ):
                pvalue = 1 - probe.get_probe_value()
                valid_presult = pvalue <= lower_max_bound
                for start, end in lower_fail_vals:
                    valid_presult &= pvalue <= start or pvalue > end
            else:
                self.fail(f"Invalid prior state after probe evaluation {prior.state}")

            if valid_presult:
                result.compile_ok = ExecutionResult.SUCCESS
                result.run_ok = ExecutionResult.SUCCESS
                result.verify_ok = ExecutionResult.SUCCESS
            else:
                result.compile_ok = ExecutionResult.COMPILE_FAIL
                result.run_ok = ExecutionResult.NA
                result.verify_ok = ExecutionResult.NA

            prior.update(result)  # None test case is used for test purposes only!

        self.assertFalse(prior.is_invalid(), "Expected prior to be valid.")
        self.assertEqual(
            prior.state, BoundedPrior.SearchState.DONE, "Expected prior to be done."
        )
        self.assertTrue(
            math.isclose(
                prior.upper_search_strat.final_bound,
                upper_target,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {upper_target} as upper bound but found {prior.upper_search_strat.final_bound}.",
        )
        self.assertTrue(
            math.isclose(
                prior.lower_search_strat.final_bound,
                lower_target,
                rel_tol=REAL_TOLERANCE * 10,
                abs_tol=REAL_TOLERANCE * 10,
            ),
            f"Expected prior to find {lower_target} as lower bound but found {prior.lower_search_strat.final_bound}.",
        )

    def test_find_bounds_verify_fail(self):
        self.run_verification_check(
            400.23, [(40, 50.55)], 40, 300, [], 300, {0: [30, 35, 42, 46, 60, 200]}
        )

        self.run_verification_check(
            400,
            [],
            400,
            5000,
            [(3100, 3200)],
            3100,
            {1: [35, 155, 1566, 244, 3115, 3199]},
        )

        # # Test first fail in verification
        self.run_verification_check(
            400, [(40, 50)], 40, 300, [], 300, {0: [40, 45, 50, 61]}
        )

        # # Test first fail in verification
        self.run_verification_check(
            400, [], 400, 5000, [(3100, 3200)], 3100, {1: [3123, 3400, 3405]}
        )

        self.run_verification_check(
            3.0, [(0.02, 0.05)], 0.01, 300, [], 300, {0: [1.4, 2.3, 0.025, 0.026]}
        )

    def test_isdone(self):
        prior = self.init_prior()
        self.assertFalse(
            prior.is_done(), "Prior should not be done if valid and not executed."
        )

        prior = self.run_prior(5.34, 10.12)
        self.assertTrue(prior.is_done(), "Prior should be done if valid and executed.")

    def test_update(self):
        prior = self.init_prior()
        prior_update_check(self, prior)

    def check_result(self, lower_target: Number, upper_target: Number, success: bool):
        prior = self.run_prior(lower_target, upper_target)
        result = prior.prior_result()

        self.assertIsNotNone(result, "Given result not expected to be None.")
        self.assertEqual(prior, result.prior, "Unexpected returned prior.")
        self.assertEqual(result.success, success, "Success result not as expected.")

        lower = round(prior.lower_search_strat.final_bound, REAL_ACCURACY)
        upper = round(prior.upper_search_strat.final_bound, REAL_ACCURACY)
        self.assertEqual(result.result_data, f"{lower},{upper}")

    def test_prior_result(self):
        self.check_result(5.34, 10.13, True)
        self.check_result(0, 10.13, True)
        self.check_result(5.34, 0, True)
        self.check_result(0, 0, False)
