# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import math
import random
import sys
from abc import ABC, abstractmethod
from enum import Enum
from numbers import Number
from typing import Any, Dict, Iterable, Optional, Set, Tuple

from augmentum.function import Function
from augmentum.objectives import ObjectiveResult
from augmentum.paths import Path, ResultPath
from augmentum.probes import NullProbe, OffsetProbe, PriorProbe, ScaleProbe, StaticProbe
from augmentum.sysUtils import unique_random_integers, unique_random_reals
from augmentum.type_descs import IntTypeDesc, RealTypeDesc

from augmentum.benchmarks import ExecutionResult, TestCase

logger = logging.getLogger(__name__)

REAL_ACCURACY = 2  # digits behind decimal
REAL_TOLERANCE = 10**-REAL_ACCURACY


def get_int_limits(bits: int) -> Tuple[int, int]:
    """
    Return minimum and maximum possible integer values for a signed integer
    with the given number of bits.
    """
    min_int = -(2 ** (bits - 1))
    max_int = 2 ** (bits - 1) - 1
    return min_int, max_int


def get_real_limit(bits: int) -> Tuple[float, float]:
    """
    Return the system's minimum and maximum positive real limits in that order
    (smallest and larges above zero).
    """
    # TODO this is currently hard coded
    if bits == 32:
        return 1.17549e-38, 3.40282e38
    if bits == 64:
        return 2.22507e-308, 1.79769e308

    raise ValueError(f"Unhandled bit value for real value {bits}.")


class ProbeResult:
    def __init__(self, probe: PriorProbe, test_case: TestCase):
        self.probe = probe
        self.test_case = test_case
        self.objective: Optional[ObjectiveResult] = None
        self.rel_objective: Optional[float] = None
        self.compile_ok = ExecutionResult.NA
        self.run_ok = ExecutionResult.NA
        self.verify_ok = ExecutionResult.NA
        self.compile_time = None  # compile time in seconds
        self.run_time = None  # run time in seconds
        self.ext_path = None  # path to extension file
        self.exec_log: Iterable[Iterable[Any]] = []

    def is_exec_success(self) -> bool:
        return (
            self.compile_ok == ExecutionResult.SUCCESS
            and self.run_ok == ExecutionResult.SUCCESS
            and self.verify_ok == ExecutionResult.SUCCESS
        )

    def __str__(self) -> str:
        def time_format(time: Optional[float]) -> str:
            return f"{round(time,3)}s" if time is not None else "NA"

        obj_supp = None
        if self.objective is not None:
            obj_supp = " ".join(
                "=".join((k, str(v))) for (k, v) in self.objective.supplementary.items()
            )

        return (
            str(self.probe)
            + "\n"
            + "test_case: "
            + str(self.test_case)
            + "\n"
            + "compile: "
            + str(self.compile_ok)
            + "\n"
            + "run: "
            + str(self.run_ok)
            + "\n"
            + "verify: "
            + str(self.verify_ok)
            + "\n"
            + "compile_t: "
            + time_format(self.compile_time)
            + "\n"
            + "run_t: "
            + time_format(self.run_time)
            + "\n"
            + "objective: "
            + str(self.objective)
            + "\n"
            + "relative objective: "
            + str(self.rel_objective)
            + "\n"
            + "objective supp: "
            + str(obj_supp)
            + "\n"
            + "extension path: "
            + str(self.ext_path)
            + "\n"
            + "# exec_log: "
            + str(len(self.exec_log))
            + "\n"
        )


class PriorResult:
    """
    Encapsulate execution success of a prior including
    additional prior specific information.
    """

    def __init__(self, prior: "Prior", success: bool, result_data: Any):
        self.prior = prior
        self.success = success
        self.result_data = result_data

    def __str__(self) -> str:
        return (
            f"{self.prior}\n" f"success: {self.success}\n" f"data: {self.result_data}\n"
        )


# --------------------------------------------------------------------------------


class SearchStrategy(ABC):
    """
    A strategy spefifying how a range of numbers should be searched.
    """

    @abstractmethod
    def has_next_target(self) -> bool:
        """Is another target available in the search?"""

    @abstractmethod
    def next_search_target(self) -> Optional[Number]:
        """Get the next search target or None if search is exhausted."""


class SampleSearch(SearchStrategy):
    """
    Go through all values in a specified range.
    """

    def __init__(self, targets: Iterable):
        self.targets = targets
        self.next_target = 0

    def has_next_target(self) -> bool:
        return self.next_target < len(self.targets)

    def next_search_target(self) -> Optional[Number]:
        if not self.has_next_target():
            return None

        value = self.targets[self.next_target]
        self.next_target += 1
        return value


class RandomSampleSearch(SampleSearch):
    """
    Go through a random sample of a specified range.
    """

    def __init__(self, targets: Iterable, max_samples: int):
        super().__init__(targets)
        if max_samples < 0:
            logger.error(
                f"Maximum samples to be chosen for search strategy must be larger or equal zero but is {max_samples}."
            )
            max_samples = 0

        self.targets = random.sample(targets, k=min(len(self.targets), max_samples))


class MinMaxSampleSearch(SampleSearch):
    """
    Go through a random sample of a specified range including the ranges min and max values.
    """

    def __init__(self, targets: Iterable, max_samples: int):
        super().__init__(targets)
        if max_samples < 0:
            logger.error(
                f"Maximum samples to be chosen for search strategy must be larger or equal zero but is {max_samples}."
            )
            max_samples = 0

        min_sample = min(self.targets)
        max_sample = max(self.targets)
        self.targets = random.sample(targets, k=min(len(self.targets), max_samples))
        if min_sample not in self.targets:
            self.targets.append(min_sample)
        if max_sample not in self.targets:
            self.targets.append(max_sample)


class VerifySampleSearch(SampleSearch):
    """
    Go through all values in a specified range and record verification outcomes.
    """

    def __init__(self, targets: Set[Number]):
        super().__init__(targets)
        # index of target to execution success
        self.sample_results: Dict[Number, bool] = dict()

    def update_search(self, prev_success: bool):
        """
        Update verification search with the result of the target chosen previously.
        """
        assert self.next_target > 0 and self.next_target <= len(
            self.targets
        ), "Expected available target if update was called."
        prev_target = self.targets[self.next_target - 1]
        self.sample_results[prev_target] = prev_success

    def has_failed_targets(self) -> bool:
        """Check if any of the verified targets failed"""
        return any(v is False for v in self.sample_results.values())


class SearchTarget:
    """
    Encapsulates the current search target for a binary search
    and whether all evaluations so far were successful.
    """

    def __init__(self, value: Number):
        self.value = value
        self.eval_success = True

    def update(self, success: bool):
        """Update evaluation result for this search target."""
        self.eval_success &= success


# TODO refactor Range Priors so they use the same binary search approach like Offset and Scale use
# --> calculate initial values for starting lower and upper from sample values
# use binary search to extend those initial values with an offset
# add or subtract offset from initial upper or lower when initialising a StaticProbe


class BinaryBoundsSearch(SearchStrategy, ABC):
    """
    Find minimum and maximum success in tested values as initial upper and lower bounds.

    use max/min int as initial extension then use binary search to go inwards
    if initial probes indicate lower or higher max/min bounds, consider those as initial ones
    """

    class BinSearchState(Enum):
        """
        State indicator for binary search of upper and lower interval bounds.
        """

        # binary search between left and right bound until left and right are next to each other
        SEARCH_UPPER = 1
        # push lower bound to the left until failure or min lower bound succeeds
        SEARCH_LOWER = 2
        # initialise verification
        INIT_VERIFICATION = 3
        # execute a random set of sample values within the new bounds to verify them
        VERIFY_BOUNDS = 4
        # evaluate the result of the verification and decide if we need to run again
        EVAL_VERIFICATION = 5
        # search is done
        DONE = 6

    def __init__(
        self,
        min_bound: Number,
        max_bound: Number,
        lower: Optional[Number] = None,
        upper: Optional[Number] = None,
        initial_values: Optional[Dict[Number, bool]] = None,
    ):
        """
        Use lower and upper optional values to set those directly as start values
        or set initial values to have it search automatically. If none are given,
        zero,zero is used.
        """

        self.min_bound = min_bound
        self.max_bound = max_bound

        if lower is not None and upper is not None:
            self.lower = lower
            self.upper = upper
            self.invalid = self.lower > self.upper

        elif initial_values is not None:
            (
                self.lower,
                self.upper,
                self.min_bound,
                self.max_bound,
            ) = BinaryBoundsSearch.find_initial_bounds(
                initial_values, self.min_bound, self.max_bound
            )
            self.invalid = self.lower is None
        else:
            self.lower = self.upper = 0
            self.invalid = False

        if self.invalid:
            self.lower = self.upper = None

        self.target = None

        # initialise bounds search
        self.left = self.upper
        self.right = self.max_bound
        self.center = None
        self._set_state(self.BinSearchState.SEARCH_UPPER)

        self.verify_search = None
        self.verify_history: Dict[Number, bool] = None
        self.skip_lower = self.skip_upper = False  # this can be used for verification

    def _set_state(self, state: BinSearchState):
        """Set the current state of this search"""
        self.state = state

    @staticmethod
    def find_initial_bounds(
        tests: Dict[Number, bool], initial_min_bound: Number, initial_max_bound: Number
    ) -> Optional[Tuple[Number, Number, Number, Number]]:
        """
        Determine the longest contiguous interval in the given initial values
        and return initial lower and upper bound at the left and right of that
        interval.

        Interval can be a single value in which case upper and lower are the same.

        Interval size is measured at a change from failing to succeeding tests until
        change from succeeding to failing test.

        Min_bound and max_bound are either their original value if lower and upper
        are at the borders of the initial values or the closest failing value
        next to its corresponding bound.

        Returns Lower, Upper, Min_Bound, Max_Bound or none if no matching bounds
        can be found.
        """
        n = len(tests)
        li = 0  # lower idx
        ui = 0  # upper idx

        max_lower_idx = None
        max_upper_idx = None
        max_diff = None

        keys = sorted(tests.keys())

        # edge case for single true entry
        if n == 1 and tests[keys[0]] is True:
            return keys[0], keys[0], initial_min_bound, initial_max_bound

        while ui < n and li < n - 1:
            # look for change from False to True for lower (or if at True zero index)
            if not (
                (tests[keys[li]] is True and li == 0)
                or (tests[keys[li]] is False and tests[keys[li + 1]] is True)
            ):
                li += 1
                ui = li
            # look for change from True to False for upper (or if at True last index)
            elif not (
                (tests[keys[ui]] is True and ui == n - 1)
                or (tests[keys[ui]] is True and tests[keys[ui + 1]] is False)
            ):
                ui += 1
            else:
                u_bound = keys[ui + 1] if ui < n - 1 else keys[ui]
                l_bound = keys[li]
                curr_diff = abs(u_bound - l_bound)
                if max_diff is None or max_diff < curr_diff:
                    max_diff = curr_diff
                    # remember valid values
                    max_lower_idx = (
                        li if li == 0 and tests[keys[li]] is True else li + 1
                    )
                    max_upper_idx = ui

                ui += 1
                li = ui

        if max_diff is None:
            return None, None, None, None

        lower = keys[max_lower_idx]
        upper = keys[max_upper_idx]
        min_bound = initial_min_bound
        max_bound = initial_max_bound

        # set min and max bound to closest failing value in history
        # if one exists beyond the starting bounds
        if max_lower_idx > 0:
            min_bound = keys[max_lower_idx - 1]

        if max_upper_idx < n - 1:
            max_bound = keys[max_upper_idx + 1]

        return lower, upper, min_bound, max_bound

    @abstractmethod
    def compare_bounds(self, a: Number, b: Number) -> bool:
        """Compare given numbers and decide if they are close enough."""

    @abstractmethod
    def split_interval(self, left: Number, right: Number) -> Number:
        """Return a central point for the given interval"""

    @abstractmethod
    def get_verification_targets(
        self, lower: Number, upper: Number
    ) -> Optional[Iterable[Number]]:
        """Return a list of verification targets for the give interval."""

    def handle_search_upper(self):
        """
        Binary search between left and right to find max working upper bound.
        """
        if self.target is None:  # initial
            self.target = SearchTarget(self.right)
            return

        if self.target.eval_success:  # pull left towards right
            if self.center is None:  # we are done, the max value worked
                self.upper = self.right  # final value
                self.right = self.lower
                self.left = self.min_bound
                self._set_state(self.BinSearchState.SEARCH_LOWER)
                self.target = None
                return

            else:
                self.left = self.center

        else:  # pull right bound towards left
            if self.center is not None:  # could be none for initial search
                self.right = self.center

        self.center = self.split_interval(self.left, self.right)
        self.target = SearchTarget(self.center)

        # left and right are now next to each other
        if self.compare_bounds(self.left, self.center):
            self.upper = self.left  # final result

            self.right = self.lower
            self.left = self.min_bound
            self.center = None
            self.target = None
            self._set_state(self.BinSearchState.SEARCH_LOWER)

    def handle_search_lower(self):
        """
        Binary search between left and right to find min working lower bound.
        """
        if self.target is None:  # initial
            self.target = SearchTarget(self.left)
            return

        if self.target.eval_success:  # pull right towards left
            if self.center is None:  # we are done, the min value worked
                self.lower = self.left  # final value
                self._set_state(self.BinSearchState.INIT_VERIFICATION)
                return

            else:
                self.right = self.center

        else:  # pull left bound towards right
            if self.center is not None:  # could be none for initial search
                self.left = self.center

        self.center = self.split_interval(self.left, self.right)
        self.target = SearchTarget(self.center)

        # left and right are now next to each other (rounding down in diff)
        if self.compare_bounds(self.left, self.center):
            self.lower = self.right  # final result
            self._set_state(self.BinSearchState.INIT_VERIFICATION)

    def initialise_verification(self):
        """
        Initialise the verification
        """
        self.target = None

        targets = self.get_verification_targets(self.lower, self.upper)
        if targets is None or len(targets) == 0:  # nothing to validate, so we are done
            self._set_state(self.BinSearchState.DONE)
            return

        logger.debug(
            f"Binary Search Verification started between {self.lower} and {self.upper} with probe targets {targets}"
        )
        self.verify_search = SampleSearch(targets)
        self.verify_history = dict()
        self._set_state(self.BinSearchState.VERIFY_BOUNDS)

    def handle_verify_bounds(self):
        """
        After upper and lower bounds have been determined, execute a verification
        for a random sample of values in between. If that fails, start the search over
        with a narrower band, otherwise end the search.
        """
        assert (
            self.verify_search is not None
        ), "Search verification expected to be initialised."

        # store verification results if we have just evaluated a target
        if self.target is not None:
            self.verify_history[self.target.value] = self.target.eval_success

        # check all targets and evaluate in the end if we have to start again
        if self.verify_search.has_next_target():
            self.target = SearchTarget(self.verify_search.next_search_target())

        else:
            self.target = None
            self._set_state(self.BinSearchState.EVAL_VERIFICATION)

    def evaluate_verification(self):
        """Evaluate verification results."""
        # are any of the verification values invalid?
        verify_fail = any(v is False for v in self.verify_history.values())

        if verify_fail:
            # verification failed, find new bounds within verification values
            # and start over
            self.verify_history[self.lower] = True
            self.verify_history[self.upper] = True

            prev_lower = self.lower
            prev_upper = self.upper

            (
                self.lower,
                self.upper,
                self.min_bound,
                self.max_bound,
            ) = BinaryBoundsSearch.find_initial_bounds(
                self.verify_history, self.min_bound, self.max_bound
            )

            self.invalid = self.lower is None

            self.target = None
            self.left = self.upper
            self.right = self.max_bound
            self.center = None
            self._set_state(self.BinSearchState.SEARCH_UPPER)

            self.verify_search = None
            self.verify_history = None
            # skip specific searches if bound has not changed
            self.skip_lower = prev_lower == self.lower
            self.skip_upper = prev_upper == self.upper

        else:  # verification succeeded, so we are done with the interval search
            self._set_state(self.BinSearchState.DONE)

    def has_next_target(self) -> bool:
        while True:
            if self.state == self.BinSearchState.SEARCH_UPPER:
                if self.skip_upper:
                    self.right = self.lower
                    self.left = self.min_bound
                    self._set_state(self.BinSearchState.SEARCH_LOWER)
                else:
                    self.handle_search_upper()

            if self.state == self.BinSearchState.SEARCH_LOWER:
                if self.skip_lower:
                    self._set_state(self.BinSearchState.INIT_VERIFICATION)
                else:
                    self.handle_search_lower()

            if self.state == self.BinSearchState.INIT_VERIFICATION:
                self.initialise_verification()

            if self.state == self.BinSearchState.VERIFY_BOUNDS:
                self.handle_verify_bounds()

            if self.state == self.BinSearchState.EVAL_VERIFICATION:
                self.evaluate_verification()

            if self.state == self.BinSearchState.DONE or self.target is not None:
                break

        return not self.invalid and self.state != self.BinSearchState.DONE

    def next_search_target(self) -> Optional[Number]:
        assert (
            self.target is not None
        ), "Target not expected to be null if search is not done."

        return self.target.value

    def update_search(self, prev_success: bool):
        """
        Update binary search with the result of the target chosen previously.
        """
        assert self.target is not None, "Expected available value if update was called."
        self.target.update(prev_success)


class BinarySearch(SearchStrategy, ABC):
    """
    From an initial value, search for the highest acceptable value up until
    a specificed maximum.
    """

    def __init__(self, max_bound: Number, min_bound: Number, start_bound: Number):
        self.initialise(max_bound, min_bound, start_bound)

    def initialise(self, max_bound: Number, min_bound: Number, start_bound: Number):
        """Initialise the binary search to the given starting parameters"""
        logger.debug(
            f"Binary Search initialise for bounds min {min_bound} start {start_bound} max {max_bound}."
        )
        # print(f"Binary Search initialise for bounds min {min_bound} start {start_bound} max {max_bound}.")

        self.initial_min_bound = min_bound
        self.max_bound = max_bound
        self.final_bound = min_bound
        self.invalid = False

        if (
            max_bound < start_bound
            or min_bound > start_bound
            or min_bound > max_bound
            or min_bound == start_bound
        ):
            self.invalid = True
            self.final_bound = None

        # initialise bounds search
        self.left = min_bound
        self.right = start_bound
        self.center = None

        self.target = None
        self.search_done = False

    @abstractmethod
    def compare_bounds(self, a: Number, b: Number) -> bool:
        """Compare given numbers and decide if they are close enough."""

    @abstractmethod
    def split_interval(self, left: Number, right: Number) -> Number:
        """Return a central point for the given interval"""

    def _select_next_value(self):
        # Nothing to select if search is already done
        if self.search_done:
            return

        # initial setup
        if self.target is None:
            self.target = SearchTarget(self.right)
            return

        if self.target.eval_success:
            if self.center is None:
                # BREAK if we found the max bound acceptable
                if self.target.value == self.max_bound:
                    self.final_bound = self.max_bound
                    self.search_done = True
                    return

                # advance towards max until fail
                self.left = self.right
                self.right = min(self.right * 2, self.max_bound)
                self.target = SearchTarget(self.right)
            else:
                # pull left towards right
                self.left = self.center
                self.center = self.split_interval(
                    self.left, self.right
                )  # L + ((R - L) // 2)
                self.target = SearchTarget(self.center)
        else:
            if self.center:
                # move right bound inwards until success
                self.right = self.center
            self.center = self.split_interval(
                self.left, self.right
            )  # L + ((R - L) // 2)
            self.target = SearchTarget(self.center)

        # BREAK left and right are now next to each other (rounding down in diff)
        if self.compare_bounds(self.left, self.center):
            self.final_bound = self.left  # final result
            self.search_done = True

    def has_next_target(self) -> bool:
        self._select_next_value()
        return not self.invalid and not self.search_done

    def next_search_target(self) -> Optional[Number]:
        assert (
            self.target is not None
        ), "Target not expected to be null when requesting next search target."
        return self.target.value

    def update_search(self, prev_success: bool):
        """
        Update binary search with the result of the target chosen previously.
        """
        assert self.target is not None, "Expected available value if update was called."
        self.target.update(prev_success)


# TODO using lambdas at this point would be better but
# there are lambda serialisation issues, hence this ugly workaround


class IntegerBinaryBoundsSearch(BinaryBoundsSearch):
    def compare_bounds(self, a: Number, b: Number) -> bool:
        return a == b

    def split_interval(self, left: Number, right: Number) -> Number:
        return left + ((right - left) // 2)

    def get_verification_targets(
        self, lower: Number, upper: Number
    ) -> Optional[Iterable[Number]]:
        # if upper and lower are less than two values apart, everything is valid in between already
        if upper - lower < 2:
            return None

        num_samples = min(upper - lower - 1, BIN_VERIFY_SAMPLES)
        targets = unique_random_integers(lower, upper, num_samples, open_interval=True)
        return targets


class RealBinaryBoundsSearch(BinaryBoundsSearch):
    def compare_bounds(self, a: Number, b: Number) -> bool:
        return math.isclose(a, b, rel_tol=REAL_TOLERANCE, abs_tol=REAL_TOLERANCE)

    def split_interval(self, left: Number, right: Number) -> Number:
        return left + ((right - left) / 2)

    def get_verification_targets(
        self, lower: Number, upper: Number
    ) -> Optional[Iterable[Number]]:
        if not math.isfinite(lower) or not math.isfinite(upper):
            logger.warning(
                f"Non finite number for lower {lower} or upper {upper} bound received."
            )
            return None

        # if upper and lower are next to each other or the same, everything is valid in between already
        if self.compare_bounds(lower, upper):
            return None

        if upper - lower == float("inf"):  # avoid going out of float bounds
            targets = unique_random_reals(
                upper - sys.float_info.max, upper, BIN_VERIFY_SAMPLES
            )
        else:
            targets = unique_random_reals(lower, upper, BIN_VERIFY_SAMPLES)
        return targets


class IntegerBinarySearch(BinarySearch):
    def compare_bounds(self, a: Number, b: Number) -> bool:
        return a == b

    def split_interval(self, left: Number, right: Number) -> Number:
        return left + ((right - left) // 2)


class RealBinarySearch(BinarySearch):
    def compare_bounds(self, a: Optional[Number], b: Optional[Number]) -> bool:
        if a is None or b is None:
            return a == b
        return math.isclose(a, b, rel_tol=REAL_TOLERANCE, abs_tol=REAL_TOLERANCE)

    def split_interval(self, left: Number, right: Number) -> Number:
        return left + ((right - left) / 2)


# --------------------------------------------------------------------------------


class Prior(ABC):
    """
    A prior making an assumption about a range of values suitable
    for a path in an instrumented function. It offers functionality
    to evaluate this range by providing probes according to a range
    search strategy.
    """

    def __init__(self, function: Function, path: Path):
        self.function = function
        self.path = path
        self._probe_log: Iterable[ProbeResult] = []

    def get_probe_log(self) -> Iterable[ProbeResult]:
        """Get the log of all probes executed for this prior"""
        return self._probe_log

    def update(self, probe_result: ProbeResult):
        """update evidence with latest result"""
        self._probe_log.append(probe_result)

    @abstractmethod
    def get_id(self) -> str:
        """Return this prior's id."""

    @abstractmethod
    def is_done(self) -> bool:
        """decide if there is more to evaluate, needs to be called before select_next_probe"""

    @abstractmethod
    def is_invalid(self) -> bool:
        """indicate if the prior is invalid according to previous evaluation"""

    @abstractmethod
    def select_next_probe(self) -> PriorProbe:
        """
        select next probe based on evaluated priors and evidence gathered

        Needs to be called after a previous call to is_done returns true.
        """

    @abstractmethod
    def prior_result(self) -> Optional[PriorResult]:
        """
        Determine prior result including additional data if needed.

        If the prior was not fully evaluated, None is returned.
        """

    def __str__(self) -> str:
        return self.get_id()

    def __repr__(self) -> str:
        return self.__str__()


class SamplePrior(Prior, ABC):
    """
    Priors implementing this abstract class
    are given a range of values which are
    tested one by one and assume that all
    of them will work to be valid.
    """

    def __init__(
        self,
        function: Function,
        path: Path,
        search_strat: SearchStrategy,
        initial_probes: Optional[Dict[Number, bool]] = None,
        min_values_checked: int = 0,
    ):
        super().__init__(function, path)
        self.curr_value = None
        self.all_probes_valid = True
        self.search_strat = search_strat
        self.probed_values = initial_probes if initial_probes is not None else dict()

        # allow for a minimum amount of values to be checked even if some of them fail
        self.min_values_checked = min_values_checked
        self.values_checked = 0

    def is_done(self) -> bool:
        # no more targets or invalid and minimum fullfilled
        return not self.search_strat.has_next_target() or (
            self.is_invalid() and self.values_checked >= self.min_values_checked
        )

    def is_invalid(self) -> bool:
        return not self.all_probes_valid

    def select_next_probe(self) -> PriorProbe:
        self.curr_value = self.search_strat.next_search_target()
        assert (
            self.curr_value is not None
        ), "Expected available value if search is not done."

        return StaticProbe(self.function, self.path, self.get_id(), self.curr_value)

    def update(self, probe_result: ProbeResult):
        super().update(probe_result)

        # remember probed value
        assert (
            self.curr_value is not None
        ), "Expected available value if update was called."

        # if the same value is reported multiple times, e.g. for different tests
        # it needs to be successful every time
        if self.curr_value in self.probed_values:
            self.probed_values[self.curr_value] &= probe_result.is_exec_success()
        else:
            self.probed_values[self.curr_value] = probe_result.is_exec_success()
            self.values_checked += 1  # we added a new value result

        if not probe_result.is_exec_success():
            # if one fails, the prior is invalid
            self.all_probes_valid = False

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return boolean for success and all values used during search
        (not all might have been successful)
        """
        if self.is_done():
            values = "#".join([f"{n},{s}" for n, s in self.probed_values.items()])
            return PriorResult(self, self.all_probes_valid, values)

        # no conclusive result because we are not done yet
        return None


class RangePrior(Prior, ABC):
    """
    Assume that there is an uninterrupted interval
    between a min and a max value that works for the path type.

    This prior can be evaluated correctly, yet still have fields within its interval that fail.
    This is because not all values are tested to be certain.
    """

    def __init__(
        self, function: Function, path: Path, initial_values: Dict[Number, bool]
    ):
        super().__init__(function, path)
        self.search_strat = self.initialise_search(initial_values)

    @abstractmethod
    def initialise_search(
        self, initial_values: Dict[Number, bool]
    ) -> BinaryBoundsSearch:
        """Initialise binary search strategy for this range prior"""

    def is_done(self) -> bool:
        return self.is_invalid() or not self.search_strat.has_next_target()

    def is_invalid(self) -> bool:
        return self.search_strat.invalid

    def select_next_probe(self) -> PriorProbe:
        value = self.search_strat.next_search_target()

        if value is None:
            # nothing to do, so return a Null Probe should we end up in this
            # state at the end of the search
            return NullProbe(self.function, self.path, self.get_id())

        return StaticProbe(self.function, self.path, self.get_id(), value)

    def update(self, probe_result: ProbeResult):
        super().update(probe_result)

        prev_success = probe_result.is_exec_success()
        self.search_strat.update_search(prev_success)

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return boolean for success and final bounds.
        """
        if self.is_done():
            success = (
                not self.is_invalid()
                and not self.search_strat.has_next_target()
                and self.search_strat.lower != self.search_strat.upper
            )  # single value does not count as range
            result_data = f"{self.search_strat.lower},{self.search_strat.upper}"
            return PriorResult(self, success, result_data)

        # no conclusive result because we are not done yet
        return None


class BoundedPrior(Prior, ABC):
    """
    Assumes that acceptable values can be determined by a lower and upper bound and
    tries to find the minimum and maximum possible one.

    Use binary search to determine upper and lower offset. Search goes from small values to large
    values.
    """

    class SearchState(Enum):
        SEARCH_UPPER = 1
        SEARCH_LOWER = 2
        INIT_VERIFICATION = 3
        UPPER_VERIFICATION = 4
        LOWER_VERIFICATION = 5
        EVAL_VERIFICTAION = 6
        DONE = 7

    def __init__(
        self,
        function: Function,
        path: Path,
        lower_search_strat: BinarySearch,
        upper_search_strat: BinarySearch,
    ):
        super().__init__(function, path)

        self.upper_search_strat = upper_search_strat
        self.lower_search_strat = lower_search_strat

        self.upper_verify_strat = None
        self.lower_verify_strat = None

        self.upper_verify_success = False
        self.lower_verify_success = False

        self.next_probe = None
        self._set_state(BoundedPrior.SearchState.SEARCH_UPPER)

    def _set_state(self, state: SearchState):
        """set the current state"""
        self.state = state

    @abstractmethod
    def _get_lower_bound_probe(self, value: Number) -> PriorProbe:
        """Return a probe for a lower bound value."""

    @abstractmethod
    def _get_upper_bound_probe(self, value: Number) -> PriorProbe:
        """Return a probe for an upper bound value."""

    @abstractmethod
    def _get_verification_targets(
        self, search: BinarySearch
    ) -> Optional[Iterable[Number]]:
        """Return verification targets for the given search."""

    def is_done(self) -> bool:
        # while we have not selected a probe and are not done yet keep going
        while self.next_probe is None and self.state != BoundedPrior.SearchState.DONE:
            if self.state == BoundedPrior.SearchState.SEARCH_UPPER:
                if (
                    self.upper_verify_success is False
                    and self.upper_search_strat.has_next_target()
                ):
                    value = self.upper_search_strat.next_search_target()
                    assert (
                        value is not None and value >= 0
                    ), f"Expected search value to be positive but is {value}"
                    self.next_probe = self._get_upper_bound_probe(value)
                else:
                    self._set_state(BoundedPrior.SearchState.SEARCH_LOWER)

            if self.state == BoundedPrior.SearchState.SEARCH_LOWER:
                if (
                    self.lower_verify_success is False
                    and self.lower_search_strat.has_next_target()
                ):
                    value = self.lower_search_strat.next_search_target()
                    assert (
                        value is not None and value >= 0
                    ), f"Expected search value to be positive but is {value}"
                    self.next_probe = self._get_lower_bound_probe(value)
                else:
                    self._set_state(BoundedPrior.SearchState.INIT_VERIFICATION)

            if self.state == BoundedPrior.SearchState.INIT_VERIFICATION:

                def init_verification(
                    prev_success: bool, search: BinarySearch
                ) -> VerifySampleSearch:
                    """Initialise verification if required"""
                    # we already succesfully verified a range earlier
                    if prev_success:
                        return None

                    # no fitting targets found
                    targets = self._get_verification_targets(search)
                    if targets is None or len(targets) == 0:
                        return None

                    return VerifySampleSearch(targets)

                self.upper_verify_strat = init_verification(
                    self.upper_verify_success, self.upper_search_strat
                )
                self.lower_verify_strat = init_verification(
                    self.lower_verify_success, self.lower_search_strat
                )

                self._set_state(BoundedPrior.SearchState.UPPER_VERIFICATION)

            if self.state == BoundedPrior.SearchState.UPPER_VERIFICATION:
                if (
                    self.upper_verify_strat is not None
                    and self.upper_verify_strat.has_next_target()
                ):
                    value = self.upper_verify_strat.next_search_target()
                    assert (
                        value is not None and value >= 0
                    ), f"Expected search value to be positive but is {value}"
                    self.next_probe = self._get_upper_bound_probe(value)
                else:
                    self._set_state(BoundedPrior.SearchState.LOWER_VERIFICATION)

            if self.state == BoundedPrior.SearchState.LOWER_VERIFICATION:
                if (
                    self.lower_verify_strat is not None
                    and self.lower_verify_strat.has_next_target()
                ):
                    value = self.lower_verify_strat.next_search_target()
                    assert (
                        value is not None and value >= 0
                    ), f"Expected search value to be positive but is {value}"
                    self.next_probe = self._get_lower_bound_probe(value)
                else:
                    self._set_state(BoundedPrior.SearchState.EVAL_VERIFICTAION)

            if self.state == BoundedPrior.SearchState.EVAL_VERIFICTAION:

                def eval_verification(
                    verify_strat: Optional[VerifySampleSearch],
                    search_start: BinarySearch,
                ) -> bool:
                    """Evaluate verification result and reset search strategy if required."""
                    if verify_strat is None or not verify_strat.has_failed_targets():
                        return True  # verification succeeded

                    vres = verify_strat.sample_results
                    targets = sorted(vres.keys())
                    # find first failing value (there must be at least one)
                    first_fail_idx = None
                    for idx, value in enumerate(targets):
                        if vres[value] is not True:
                            first_fail_idx = idx
                            break
                    assert (
                        first_fail_idx is not None
                    ), "Failing value expected in verification results"

                    max_bound = targets[first_fail_idx]
                    min_bound = search_start.initial_min_bound
                    if first_fail_idx > 0:
                        start_bound = targets[first_fail_idx - 1]
                    else:
                        start_bound = search_start.split_interval(min_bound, max_bound)

                    # if the first verification value failed and it is right next to the min bound
                    # no other bound other than min bound will work, so do another search to verify
                    # that and end it
                    if min_bound == start_bound:
                        start_bound = max_bound

                    search_start.initialise(max_bound, min_bound, start_bound)
                    return False

                self.upper_verify_success = eval_verification(
                    self.upper_verify_strat, self.upper_search_strat
                )
                self.lower_verify_success = eval_verification(
                    self.lower_verify_strat, self.lower_search_strat
                )

                if self.upper_verify_success and self.lower_verify_success:
                    self._set_state(BoundedPrior.SearchState.DONE)
                    self.next_probe = None
                else:
                    self._set_state(BoundedPrior.SearchState.SEARCH_UPPER)

        return self.is_invalid() or self.state == BoundedPrior.SearchState.DONE

    def is_invalid(self) -> bool:
        return self.upper_search_strat.invalid or self.lower_search_strat.invalid

    def select_next_probe(self) -> PriorProbe:
        assert self.next_probe is not None, "Next probe not expected to be none."
        return self.next_probe

    def update(self, probe_result: ProbeResult):
        super().update(probe_result)

        prev_success = probe_result.is_exec_success()

        if self.state == BoundedPrior.SearchState.SEARCH_UPPER:
            self.upper_search_strat.update_search(prev_success)
        elif self.state == BoundedPrior.SearchState.SEARCH_LOWER:
            self.lower_search_strat.update_search(prev_success)
        elif self.state == BoundedPrior.SearchState.UPPER_VERIFICATION:
            self.upper_verify_strat.update_search(prev_success)
        elif self.state == BoundedPrior.SearchState.LOWER_VERIFICATION:
            self.lower_verify_strat.update_search(prev_success)

        # probe evaluated, reset
        self.next_probe = None

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return boolean for success and final bounds.
        """
        if self.is_done():
            lower = self.lower_search_strat.final_bound
            upper = self.upper_search_strat.final_bound
            success = (
                not self.is_invalid()
                and self.state == BoundedPrior.SearchState.DONE
                and (lower != 0 or upper != 0)
            )  # zero values are no actual offsets

            result_data = f"{lower},{upper}"
            return PriorResult(self, success, result_data)

        # no conclusive result because we are not done yet
        return None


class OffsetPrior(BoundedPrior):
    """
    [original-lower, original+upper]

    Use binary search to determine upper and lower offset.
    Search goes from small values to large values.
    """

    def _get_lower_bound_probe(self, value: Number) -> PriorProbe:
        return OffsetProbe(self.function, self.path, self.get_id(), -1 * value)

    def _get_upper_bound_probe(self, value: Number) -> PriorProbe:
        return OffsetProbe(self.function, self.path, self.get_id(), value)


class ScalePrior(BoundedPrior):
    """
    [original*(1-lower), original*(1+upper)]

    Use binary search to determine upper and lower scale factor.
    Search goes from small values to large values.
    """

    def _get_lower_bound_probe(self, value: Number) -> PriorProbe:
        return ScaleProbe(self.function, self.path, self.get_id(), 1 - value)

    def _get_upper_bound_probe(self, value: Number) -> PriorProbe:
        return ScaleProbe(self.function, self.path, self.get_id(), 1 + value)


# --------------------------------------------------------------------------------

# number of random samples to take for all prior intervals
ALL_PRIOR_SAMPLES = 30

BIN_VERIFY_SAMPLES = 30


class CompositePrior(Prior):
    """
    Execute multiple specified priors according to a
    predefined progression order.
    """

    ID = "Composite Prior"
    MAX_BROADCAST_SAMPLES = 5

    class PriorState(Enum):
        # execute original values with the null prior
        NULL = 0
        # check if collected original values work if broadcasted to all function executions
        BROADCAST = 1

        # try both bool values
        BOOL_ALL = 2

        # check original oblivious primitive range for int or real type
        OO_INTEGER_ALL = 3
        OO_INTEGER_RANGE = 4
        OO_REAL_ALL = 5
        OO_REAL_RANGE = 6

        # original aware with additive range for int or real type
        OA_OFFSET = 7

        # original aware with scaled range for int or real type
        OA_SCALE = 8

        # prior evaluation is done
        DONE = 9

    def __init__(self, function: Function, path: Path, skip_immutables: bool):
        super().__init__(function, path)

        # list of executed priors
        self.priors: Iterable[Prior] = []

        self.skip_immutables = skip_immutables

        # start with a null prior to record original values
        self.state = CompositePrior.PriorState.NULL
        self._set_current_prior(NullPrior(function, path))

    def get_id(self) -> str:
        return self.ID

    def get_probe_log(self) -> Iterable[ProbeResult]:
        total_log = []
        for p in self.priors:
            total_log += p.get_probe_log()

        return total_log

    def is_done(self) -> bool:
        # if the Null prior failed, don't go any further
        if (
            self.state == CompositePrior.PriorState.NULL
            and self.current_prior.is_invalid()
        ):
            return True

        # select the next one if we are done with the current but
        # still have work to do overal
        while (
            self.state != CompositePrior.PriorState.DONE
            and self.current_prior.is_done()
        ):
            self._select_next_prior()

        return self.state == CompositePrior.PriorState.DONE

    def is_invalid(self) -> bool:
        return self.current_prior.is_invalid()

    def select_next_probe(self) -> PriorProbe:
        return self.current_prior.select_next_probe()

    def update(self, probe_result: ProbeResult):
        self.current_prior.update(probe_result)

    def _set_current_prior(self, prior: Prior):
        """
        Set a new active prior and add it to the list of existing priors.
        """
        self.current_prior = prior
        self.priors.append(prior)

    def _select_next_prior(self):
        """The current prior is done, so select the next one if any are left"""

        if self.state == CompositePrior.PriorState.NULL:
            assert isinstance(
                self.current_prior, NullPrior
            ), "Expected Null prior to be active when in NULL state."

            if (
                self.skip_immutables
                and not isinstance(self.path, ResultPath)
                and self.current_prior.mutated_during_call is False
            ):
                # if we skip immutable parameter paths and the Null Prior could
                # not detect any mutation, skip to the end
                logger.info(
                    f"Immutable function parameter path suspected. Skipping Path {self.path}"
                )
                self.state = CompositePrior.PriorState.DONE

            else:
                targets = list(self.current_prior.probed_values.keys())
                assert (
                    len(targets) > 0
                ), "Expected Null prior return at least one probed value to continue with next prior."

                # if working on a boolean prior, just try both values and be done
                if isinstance(self.path.type, IntTypeDesc) and self.path.type.bits == 1:
                    self._set_current_prior(
                        BooleanPrior(self.function, self.path, targets)
                    )
                    self.state = CompositePrior.PriorState.BOOL_ALL

                # use the broadcast prior to determine if we can be original oblivious (OO)
                # or if we need to be original aware (OA)
                else:
                    logger.debug(f"Available samples for Broadcast Prior: {targets}")

                    self._set_current_prior(
                        BroadCastPrior(
                            self.function,
                            self.path,
                            MinMaxSampleSearch(
                                targets, CompositePrior.MAX_BROADCAST_SAMPLES
                            ),
                        )
                    )
                    self.state = CompositePrior.PriorState.BROADCAST

        elif self.state == CompositePrior.PriorState.BROADCAST:
            assert isinstance(
                self.current_prior, BroadCastPrior
            ), "Expected Boradcast prior to be active when in BROADCAST state."

            if (
                self.current_prior.prior_result() is not None
                and self.current_prior.prior_result().success
            ):
                # if broadcast was successful for subsample, assume
                # that all of the null prior values will be fine
                # and use it as a basis for range search
                probed_values = set(
                    self.priors[0].probed_values.keys()
                )  # first prior is NullPrior

                if isinstance(self.path.type, IntTypeDesc):
                    assert (
                        self.path.type.bits > 1
                    ), "Boolean path type not expected at this point."
                    self._set_current_prior(
                        AllIntegersPrior(self.function, self.path, probed_values)
                    )
                    self.state = CompositePrior.PriorState.OO_INTEGER_ALL

                elif isinstance(self.path.type, RealTypeDesc):
                    self._set_current_prior(
                        AllRealsPrior(self.function, self.path, probed_values)
                    )
                    self.state = CompositePrior.PriorState.OO_REAL_ALL

                else:
                    raise ValueError(
                        f"Unexpected terminal path type during prior evaluation {self.path.type}."
                    )

            else:
                if isinstance(self.path.type, IntTypeDesc):
                    assert (
                        self.path.type.bits > 1
                    ), "Boolean path type not expected at this point."
                    self._set_current_prior(
                        IntegerOffsetPrior(self.function, self.path)
                    )

                elif isinstance(self.path.type, RealTypeDesc):
                    self._set_current_prior(RealOffsetPrior(self.function, self.path))

                else:
                    raise ValueError(
                        f"Unexpected terminal path type during prior evaluation {self.path.type}."
                    )

                self.state = CompositePrior.PriorState.OA_OFFSET

        elif self.state == CompositePrior.PriorState.BOOL_ALL:
            assert isinstance(
                self.current_prior, BooleanPrior
            ), "Expected BoolPrior Prior to be active when in BOOL_ALL state."
            self.state = CompositePrior.PriorState.DONE

        elif self.state == CompositePrior.PriorState.OO_INTEGER_ALL:
            assert isinstance(
                self.current_prior, AllIntegersPrior
            ), "Expected AllIntegers Prior to be active when in OO_INTEGER_ALL state."

            # if the Full integer range worked, we are done
            # otherwise try to find an integer range and then be done
            if (
                self.current_prior.prior_result() is None
                or not self.current_prior.prior_result().success
            ):
                self._set_current_prior(
                    IntegerRangePrior(
                        self.function, self.path, self.current_prior.probed_values
                    )
                )
                self.state = CompositePrior.PriorState.OO_INTEGER_RANGE
            else:
                self.state = CompositePrior.PriorState.DONE

        elif self.state == CompositePrior.PriorState.OO_INTEGER_RANGE:
            assert isinstance(
                self.current_prior, IntegerRangePrior
            ), "Expected IntegerRange Prior to be active when in OO_INTEGER_RANGE state."

            # continue with offset and scale no matter if successful or not
            self._set_current_prior(IntegerOffsetPrior(self.function, self.path))
            self.state = CompositePrior.PriorState.OA_OFFSET

        elif self.state == CompositePrior.PriorState.OO_REAL_ALL:
            assert isinstance(
                self.current_prior, AllRealsPrior
            ), "Expected AllReals Prior to be active when in OO_REAL_ALL state."

            # if the Full real range worked, we are done
            # otherwise try to find a real range and then be done
            if (
                self.current_prior.prior_result() is None
                or not self.current_prior.prior_result().success
            ):
                self._set_current_prior(
                    RealRangePrior(
                        self.function, self.path, self.current_prior.probed_values
                    )
                )
                self.state = CompositePrior.PriorState.OO_REAL_RANGE
            else:
                self.state = CompositePrior.PriorState.DONE

        elif self.state == CompositePrior.PriorState.OO_REAL_RANGE:
            assert isinstance(
                self.current_prior, RealRangePrior
            ), "Expected RealRange Prior to be active when in OO_REAL_RANGE state."

            # continue with offset and scale no matter if successful or not
            self._set_current_prior(RealOffsetPrior(self.function, self.path))
            self.state = CompositePrior.PriorState.OA_OFFSET

        elif self.state == CompositePrior.PriorState.OA_OFFSET:
            assert isinstance(
                self.current_prior, (IntegerOffsetPrior, RealOffsetPrior)
            ), "Expected Offset Prior to be active when in OA_OFFSET state."

            # continue with corresponding scale prior
            if isinstance(self.current_prior, IntegerOffsetPrior):
                scale_prior = IntegerScalePrior(self.function, self.path)
            elif isinstance(self.current_prior, RealOffsetPrior):
                scale_prior = RealScalePrior(self.function, self.path)
            else:
                raise ValueError(
                    "Expected Offset Prior to be active when in OA_OFFSET state."
                )

            self._set_current_prior(scale_prior)
            self.state = CompositePrior.PriorState.OA_SCALE

        elif self.state == CompositePrior.PriorState.OA_SCALE:
            assert isinstance(
                self.current_prior, (IntegerScalePrior, RealScalePrior)
            ), "Expected Scale Prior to be active when in OA_SCALE state."
            # nothing else to do here
            self.state = CompositePrior.PriorState.DONE

        elif self.state == CompositePrior.PriorState.DONE:
            pass  # nothing to do here

        else:
            raise RuntimeError(f"Unhandled prior state {self.state}.")

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return if any of the priors you tested except the NULL prior were successful
        and a list of priors tested.
        """
        # skip the first prior in the list since that is
        # the NULL prior which we assume should always work
        any_success = any(
            (
                p.prior_result() is not None and p.prior_result().success
                for p in self.priors[1:]
            )
        )
        return PriorResult(self, any_success, self.priors)


class NullPrior(Prior):
    """
    Execute the original function and record corresponding values.
    """

    ID = "Null Prior"
    DATA_DELIM = "#"

    def __init__(self, function: Function, path: Path):
        super().__init__(function, path)
        # tested values and the frequency of their appearance
        self.probed_values: Dict[Number, int] = dict()

        # indicates if the value of a path was actually mutated
        # during the execution of the original extended function
        # not considered for result paths
        self.mutated_during_call: Optional[bool] = (
            None if isinstance(path, ResultPath) else False
        )

        self.executed = False
        self.invalid = False

    def get_id(self) -> str:
        return self.ID

    def is_done(self) -> bool:
        return self.executed

    def is_invalid(self) -> bool:
        return self.invalid

    def select_next_probe(self) -> PriorProbe:
        self.executed = True
        return NullProbe(self.function, self.path, self.get_id())

    def _save_probed_values(
        self, probe_result: ProbeResult, probed_values: Dict[Number, int]
    ):
        """
        Save probed values from the given probe result.
        """
        for entry in probe_result.exec_log:
            if len(entry) != 3:
                raise RuntimeError("Unexpected probe log entry format!")

            # path value before function call, probed after function call, frequency this pair was observed
            before, probed, freq = entry

            if probed == "inf" or "nan" in probed:
                # 'inf' values can appear for float overflows in the c++ code
                # 'nan' values can be used for float or double values
                # and will be ignored for now
                continue

            if isinstance(self.path.type, IntTypeDesc):
                probed_num = int(probed)
            elif isinstance(self.path.type, RealTypeDesc):
                probed_num = float(probed)
            else:
                logger.warning(f"Path type of probe not as expected {self.path.type}")
                probed_num = probed

            if probed_num not in probed_values:
                probed_values[probed_num] = 0
            probed_values[probed_num] += int(freq)

            # if before differs from probed after the function call
            # this call has likely mutated the path's value
            if self.mutated_during_call is not None:
                self.mutated_during_call |= before != probed

    def update(self, probe_result: ProbeResult):
        super().update(probe_result)

        if probe_result.is_exec_success() and len(probe_result.exec_log) > 0:
            # remember probed values
            self._save_probed_values(probe_result, self.probed_values)

            # Null probe can fail to parse any of the probe result values if all of them
            # are invalid values such as nan. This can happen for f32 types hidden
            # in i32 types.
            if len(self.probed_values) == 0:
                logger.warning(
                    f"No valid Null Probe results could be parsed for {self.function} {self.path} {probe_result.test_case}"
                )
                self.invalid = True
        else:
            # Null probe can fail for specific input values that the extension code
            # works with incorrectly such as a specific pointer value that is
            # intended as state indicator rather than valid pointer. The Null probe
            # would not know that and would try to dereference it.
            #
            # Also the original code could be faulty, the selected timeout for
            # compilation and / or execution could be too short or the given memory
            # limit could be too low.
            #
            # Null probe can have no probed values if the function is called with
            # a null pointer along one of its paths. In that case no probed value is
            # logged.
            logger.warning(
                f"Null Probe execution failed for {self.function} {self.path} {probe_result.test_case}"
            )
            self.invalid = True

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return boolean for success and list of probed values and their frequency.
        """
        if self.executed:
            values = NullPrior.DATA_DELIM.join(
                [f"{n},{f}" for n, f in self.probed_values.items()]
            )
            data_str = (
                f"MUTATED:{self.mutated_during_call}{NullPrior.DATA_DELIM}DATA:{values}"
            )
            return PriorResult(self, not self.is_invalid(), data_str)

        return None


class BroadCastPrior(SamplePrior):
    """
    Evaluate if output values from original executions work for every function call
    made during execution.

    If so, future priors can be oblivious to the original value.
    If not, future priors need to consider the original value.
    """

    ID = "Broadcast Prior"

    def __init__(self, function: Function, path: Path, search_strat: SampleSearch):
        super().__init__(function, path, search_strat)

        logger.info(
            "BroadCastPrior prior created with probe targets "
            + str(self.search_strat.targets)
        )

    def is_done(self) -> bool:
        # if only one target is available, it has been used by
        # all executions of the function already in the NullPrior, so no need to
        # test it again against all of them
        return len(self.search_strat.targets) == 1 or super().is_done()

    def get_id(self) -> str:
        return self.ID


class BooleanPrior(Prior):
    """
    Try both truth values.
    """

    ID = "Boolean Prior"

    def __init__(self, function: Function, path: Path, probed_values: Iterable[Number]):
        super().__init__(function, path)

        self.curr_value = None

        self.probed_values: Dict[Number, bool] = dict()

        # search the two possibilities and statically set them every time the probe is used
        targets = [0, 1]

        self.search_strat = SampleSearch(targets)
        logger.debug(f"Boolean Prior created with probe targets {targets}")

    def get_id(self) -> str:
        return self.ID

    def is_done(self) -> bool:
        return not self.search_strat.has_next_target()

    def is_invalid(self) -> bool:
        """
        Boolean prior is invalid if none of the two truth values could be used successfuly.
        """
        if len(self.probed_values) < 2:
            return False  # not all values tested yet

        all_invalid = True
        for _, succ in self.probed_values.items():
            if succ:
                all_invalid = False
                break
        return all_invalid

    def select_next_probe(self) -> PriorProbe:
        self.curr_value = self.search_strat.next_search_target()
        assert (
            self.curr_value is not None
        ), "Expected available value if search is not done."

        return StaticProbe(self.function, self.path, self.get_id(), self.curr_value)

    def update(self, probe_result: ProbeResult):
        super().update(probe_result)

        # remember probed value
        assert (
            self.curr_value is not None
        ), "Expected available value if update was called."

        # if the same value is reported multiple times, e.g. for different tests
        # it needs to be successful every time
        if self.curr_value in self.probed_values:
            self.probed_values[self.curr_value] &= probe_result.is_exec_success()
        else:
            self.probed_values[self.curr_value] = probe_result.is_exec_success()

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return boolean for success and which truth value it applies to.
        """
        if self.is_done():
            values = "#".join([f"{n},{s}" for n, s in self.probed_values.items()])
            all_valid = True
            for _, succ in self.probed_values.items():
                if not succ:
                    all_valid = False
                    break

            return PriorResult(self, all_valid, values)

        # no conclusive result because we are not done yet
        return None


class AllIntegersPrior(SamplePrior):
    """
    Assume that the full range of integer values works
    for the path type, i.e [-2^(bits-1), 2^(bits-1) - 1]
    """

    ID = "All Integers Prior"

    def __init__(self, function: Function, path: Path, initial_probes: Set[Number]):
        # consider probe history so far
        probed_values: Dict[Number, bool] = dict()
        for num in initial_probes:
            probed_values[num] = True  # previous values are assumed to work

        # check for a specified range if they have not be tested yet
        min_int, max_int = get_int_limits(path.type.bits)

        # select an additional random sample uniformely distributed over the total value range
        prelim_targets = unique_random_integers(min_int, max_int, ALL_PRIOR_SAMPLES)

        # select interesting boundary values
        for n in [min_int, max_int, 0, -1, 1]:
            if n not in prelim_targets:
                prelim_targets.append(n)

        targets = []
        for t in prelim_targets:
            if t not in probed_values:
                targets.append(t)

        # shortcut in case only a single value is applicable
        # this will make sure that the range search prior following this all prior
        # will not go through too many unnecessary failing values
        min_values_checked = 0
        if len(initial_probes) < 2:
            for num in initial_probes:
                targets.insert(0, num + 1)
                targets.insert(0, num - 1)
                min_values_checked += 2

        super().__init__(
            function, path, SampleSearch(targets), probed_values, min_values_checked
        )

        logger.debug(f"All Integers Prior created with probe targets {targets}")

    def get_id(self) -> str:
        return self.ID


class AllRealsPrior(SamplePrior):
    """
    Assume that the full range of real values works
    for the path type, i.e [-3.40282e+38, 3.40282e+38]
    """

    ID = "All Reals Prior"

    def __init__(self, function: Function, path: Path, initial_probes: Set[Number]):
        # consider probe history so far
        probed_values: Dict[Number, bool] = dict()
        for num in initial_probes:
            probed_values[num] = True  # previous values are assumed to work

        min_pos, max_pos = get_real_limit(path.type.bits)
        max_neg = -max_pos
        min_neg = -min_pos

        # select an additional random sample uniformely distributed over the total value range
        if max_pos - max_neg == float("inf"):  # avoid going out of float bounds
            prelim_targets = unique_random_reals(
                max_pos - sys.float_info.max, max_pos, ALL_PRIOR_SAMPLES
            )
        else:
            prelim_targets = unique_random_reals(max_neg, max_pos, ALL_PRIOR_SAMPLES)

        # select interesting boundary values
        for n in [max_neg, -1.0, min_neg, 0, min_pos, 1.0, max_pos]:
            if n not in prelim_targets:
                prelim_targets.append(n)

        targets = []
        for t in prelim_targets:
            if t not in probed_values:
                targets.append(t)

        # shortcut in case only a single value is applicable
        # this will make sure that the following range search will not go through too many
        # unnecessary failing values
        min_values_checked = 0
        if len(initial_probes) < 2:
            for num in initial_probes:
                targets.insert(0, num + (REAL_TOLERANCE * 10))
                targets.insert(0, num - (REAL_TOLERANCE * 10))
                min_values_checked += 2

        super().__init__(
            function, path, SampleSearch(targets), probed_values, min_values_checked
        )

        logger.debug(f"All Reals Prior created with probe targets {targets}")

    def get_id(self) -> str:
        return self.ID


class IntegerRangePrior(RangePrior):
    """
    Assumes that values within a given integer interval are acceptable and
    tries to find its upper and lower bound.
    """

    ID = "Integer Range Prior"

    def __init__(
        self, function: Function, path: Path, initial_probes: Dict[Number, bool]
    ):
        super().__init__(function, path, initial_probes)

        logger.debug(
            f"Integer Range Prior created with bounds [{self.search_strat.lower},{self.search_strat.upper}]"
        )

    def initialise_search(
        self, initial_values: Dict[Number, bool]
    ) -> BinaryBoundsSearch:
        min_int, max_int = get_int_limits(self.path.type.bits)
        return IntegerBinaryBoundsSearch(
            min_int, max_int, initial_values=initial_values
        )

    def get_id(self) -> str:
        return self.ID


class RealRangePrior(RangePrior):
    """
    Assumes that values within a given real value interval are acceptable and
    tries to find its upper and lower bound.
    """

    ID = "Real Range Prior"

    def __init__(
        self, function: Function, path: Path, initial_probes: Dict[Number, bool]
    ):
        super().__init__(function, path, initial_probes)

        logger.debug(
            f"Real Range Prior created with bounds [{self.search_strat.lower},{self.search_strat.upper}]"
        )

    def initialise_search(
        self, initial_values: Dict[Number, bool]
    ) -> BinaryBoundsSearch:
        _, max_pos = get_real_limit(self.path.type.bits)
        max_neg = -max_pos

        bin_search = RealBinaryBoundsSearch(
            max_neg, max_pos, initial_values=initial_values
        )

        return bin_search

    def get_id(self) -> str:
        return self.ID

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return boolean for success and final bounds.
        """
        if self.is_done():

            def bform(bound: Optional[float]) -> Optional[float]:
                if bound is None:
                    return None
                return round(bound, REAL_ACCURACY)

            lower = bform(self.search_strat.lower)
            upper = bform(self.search_strat.upper)

            success = (
                not self.is_invalid()
                and not self.search_strat.has_next_target()
                and not math.isclose(lower, upper)
            )

            result_data = f"{lower},{upper}"
            return PriorResult(self, success, result_data)

        # no conclusive result because we are not done yet
        return None


class IntegerOffsetPrior(OffsetPrior):
    """
    Assumes that an integer offset to the original output value is acceptable as modification and
    tries to find the minimum and maximum possible one.
    """

    ID = "Integer Offset Prior"

    def __init__(self, function: Function, path: Path):
        _, max_val = get_int_limits(path.type.bits)
        upper_search_strat = IntegerBinarySearch(max_val, 0, 1)
        lower_search_strat = IntegerBinarySearch(max_val, 0, 1)

        super().__init__(function, path, lower_search_strat, upper_search_strat)

        logger.debug("Integer Offset Prior created.")

    def _get_verification_targets(
        self, search: BinarySearch
    ) -> Optional[Iterable[Number]]:
        if search.final_bound < 2:
            # no values available for testing in range
            return None

        samples = min(search.final_bound - 1, BIN_VERIFY_SAMPLES)
        targets = unique_random_integers(
            0, search.final_bound, samples, open_interval=True
        )

        logger.debug(
            f"Binary Search Verification started between 0 and {search.final_bound} with probe targets {targets}"
        )
        return targets

    def get_id(self) -> str:
        return self.ID


class RealOffsetPrior(OffsetPrior):
    """
    Assumes that an real offset to the original output value is acceptable as modification and
    tries to find the minimum and maximum possible one.
    """

    ID = "Real Offset Prior"

    def __init__(self, function: Function, path: Path):
        _, max_val = get_real_limit(path.type.bits)
        upper_search_strat = RealBinarySearch(max_val, 0, 1.0)
        lower_search_strat = RealBinarySearch(max_val, 0, 1.0)

        super().__init__(function, path, lower_search_strat, upper_search_strat)

        logger.debug("Real Offset Prior created.")

    def _get_verification_targets(
        self, search: BinarySearch
    ) -> Optional[Iterable[Number]]:
        if not math.isfinite(search.final_bound):
            logger.warning(f"Final bound is non finite number {search.final_bound}.")
            return None

        # if upper and lower are next to each other or the same, everything is valid in between already
        if search.compare_bounds(0, search.final_bound):
            return None

        targets = unique_random_reals(0, search.final_bound, BIN_VERIFY_SAMPLES)
        logger.debug(
            f"Binary Search Verification started between 0 and {search.final_bound} with probe targets {targets}"
        )
        return targets

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return boolean for success and final bounds.
        """
        if self.is_done():

            def bform(bound: Optional[float]) -> Optional[float]:
                if bound is None:
                    return None
                return round(bound, REAL_ACCURACY)

            lower = bform(self.lower_search_strat.final_bound)
            upper = bform(self.upper_search_strat.final_bound)

            success = (
                not self.is_invalid()
                and self.state == BoundedPrior.SearchState.DONE
                and (not math.isclose(lower, 0) or not math.isclose(upper, 0))
            )  # zero offset is simply to original value

            result_data = f"{lower},{upper}"
            return PriorResult(self, success, result_data)

        # no conclusive result because we are not done yet
        return None

    def get_id(self) -> str:
        return self.ID


class IntegerScalePrior(ScalePrior):
    """
    Assumes that scaling the original output by an integer factor is acceptable as modification and
    tries to find the minimum and maximum possible one.
    """

    ID = "Integer Scale Prior"

    def __init__(self, function: Function, path: Path):
        _, max_val = get_int_limits(path.type.bits)
        upper_search_strat = IntegerBinarySearch(max_val, 0, 1)
        lower_search_strat = IntegerBinarySearch(max_val, 0, 1)

        super().__init__(function, path, lower_search_strat, upper_search_strat)

        logger.debug("Integer Scale Prior created.")

    def _get_verification_targets(
        self, search: BinarySearch
    ) -> Optional[Iterable[Number]]:
        if search.final_bound < 2:
            # no values available for testing in range
            return None

        samples = min(search.final_bound - 1, BIN_VERIFY_SAMPLES)
        targets = unique_random_integers(
            0, search.final_bound, samples, open_interval=True
        )

        logger.debug(
            f"Binary Search Verification started between 0 and {search.final_bound} with probe targets {targets}"
        )
        return targets

    def get_id(self) -> str:
        return self.ID


class RealScalePrior(ScalePrior):
    """
    Assumes that scaling the original output by a real factor is acceptable as modification and
    tries to find the minimum and maximum possible one.
    """

    ID = "Real Scale Prior"

    def __init__(self, function: Function, path: Path):
        _, max_val = get_real_limit(path.type.bits)
        upper_search_strat = RealBinarySearch(max_val, 0, 1.0)
        lower_search_strat = RealBinarySearch(max_val, 0, 1.0)

        super().__init__(function, path, lower_search_strat, upper_search_strat)

        logger.debug("Real Scale Prior created.")

    def _get_verification_targets(
        self, search: BinarySearch
    ) -> Optional[Iterable[Number]]:
        if not math.isfinite(search.final_bound):
            logger.warning(f"Final bound is non finite number {search.final_bound}.")
            return None

        # if upper and lower are next to each other or the same, everything is valid in between already
        if search.compare_bounds(0, search.final_bound):
            return None

        targets = unique_random_reals(0, search.final_bound, BIN_VERIFY_SAMPLES)
        logger.debug(
            f"Binary Search Verification started between 0 and {search.final_bound} with probe targets {targets}"
        )
        return targets

    def prior_result(self) -> Optional[PriorResult]:
        """
        Return boolean for success and final bounds.
        """
        if self.is_done():

            def bform(bound: Optional[float]) -> Optional[float]:
                if bound is None:
                    return None
                return round(bound, REAL_ACCURACY)

            lower = bform(self.lower_search_strat.final_bound)
            upper = bform(self.upper_search_strat.final_bound)

            success = (
                not self.is_invalid()
                and self.state == BoundedPrior.SearchState.DONE
                and (not math.isclose(lower, 0) or not math.isclose(upper, 0))
            )  # zero offset is simply to original value

            result_data = f"{lower},{upper}"
            return PriorResult(self, success, result_data)

        # no conclusive result because we are not done yet
        return None

    def get_id(self) -> str:
        return self.ID


# -----------------------------------------------------------------------------------------


def build_priors(function: Function, path: Path, skip_immutables: bool) -> Prior:
    return CompositePrior(function, path, skip_immutables)
