# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import asyncio
import logging
import os
import resource
import signal
import time
from pathlib import Path
from subprocess import TimeoutExpired
from time import monotonic as timer
from typing import Any, Callable, Iterable, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# TODO use optional int to remove memory restriction for current process
def set_memory_limit(limit: int):
    """Set memory limit for current process and its subprocesses.
    NOTE: The memory limit is inherited by subprocesses as a whole,
    there is no overall limit maintained. For example, if a limit of 500MB is
    set and process A spawns process B then both A and B have a 500 MB
    limit giving a total of 1000MB.

    limit: memory value in MB
    """
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    mem_limit = limit * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (mem_limit, hard))


def get_memory() -> int:
    """Check available system memory and return in Bytes."""
    with open("/proc/meminfo", "r") as mem:
        free_memory = 0
        for i in mem:
            sline = i.split()
            if str(sline[0]) in ("MemFree:", "Buffers:", "Cached:"):
                free_memory += int(sline[1])
    return free_memory


async def run_command_async(
    command: str,
    timeout: Optional[float] = None,
    verbose: bool = False,
    memory_limit: Optional[int] = None,
    debug_log: Callable[[str], None] = logger.debug,
) -> Tuple[int, str]:
    if memory_limit is not None:
        # set given MB memory limit in KB
        command = f"ulimit -Sv {int(memory_limit * 1024)}; " + command

    # Start child process
    # NOTE: universal_newlines parameter is not supported
    if verbose:
        debug_log(command)

    # The os.setsid() is passed in the argument preexec_fn so
    # it's run after the fork() and before  exec() to run the shell.
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        preexec_fn=os.setsid,
        limit=(1024 * 512),
    )

    # Read line (sequence of bytes ending with b'\n') asynchronously
    start = timer()
    stdout = ""
    while True:
        time_left = (start + timeout) - timer() if timeout else None
        try:
            line = await asyncio.wait_for(process.stdout.readline(), time_left)
            if not line:  # EOF
                break
            else:
                stdout += line.decode("utf-8", "backslashreplace")
                if verbose:
                    debug_log(line.decode("utf-8", "backslashreplace").strip())

        except ValueError as value_err:
            logger.warning(
                "ValueError while reading stdout lines "
                "from running process:\n" + str(value_err)
            )
            # Send the signal to all the process groups
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            break
        except asyncio.TimeoutError:
            # Send the signal to all the process groups
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            await process.wait()
            raise TimeoutExpired(command, timeout)

    return_code = await process.wait()  # Wait for the child process to exit

    return return_code, stdout


def run_command(
    command: str,
    timeout: Optional[float] = None,
    verbose: bool = False,
    memory_limit: Optional[int] = None,
    debug_log: Callable[[str], None] = logger.debug,
) -> Tuple[int, str]:
    """
    Execute the given shell command and return error code and stdout when finished.

    Stderr is forwarded to stdout.

    Throws TimeoutExpired exception if timeout expires during execution.

    Prints live stdout and stderr if running verbose.
    """
    return asyncio.get_event_loop().run_until_complete(
        run_command_async(command, timeout, verbose, memory_limit, debug_log)
    )


def touch_existing_file(filename: Path):
    if filename.exists():
        filename.touch()
    else:
        raise RuntimeError("File not found for touching: " + str(filename))


def try_create_dir(
    path: Path, use_time: bool = False, tries: int = 100
) -> Optional[Path]:
    """Try creating a path that does not exist yet."""
    curr_path = path

    if use_time:
        curr_path = path.parent / f"{path.stem}_{int(time.time())}{path.suffix}"

    count = 0
    while curr_path.exists() and count < tries:
        curr_path = path.parent / f"{path.stem}_{count}{path.suffix}"
        count += 1

    if count < tries:
        curr_path.mkdir(exist_ok=False)
        return curr_path
    else:
        return None


def build_path_or_fail(path_str: str) -> Path:
    path = Path(path_str)
    if not path.exists():
        raise RuntimeError("Path invalid: " + path_str)

    return path


def check_arg_pred(parser, value, predicate, error="Invalid cmd argument."):
    """
    Intended to be used for argument parsing with argparse library.
    Check given argument value against predicate function.
    """
    if predicate(value):
        return value
    else:
        parser.error(error + " [" + str(value) + "]")
        return None


def check_arg_list(
    parser, value: Any, expected: Iterable[Any], error: str = "Invalid cmd argument."
):
    """
    Intended to be used for argument parsing with argparse library.
    Check given argument value against list of expected values.
    """
    if value in expected:
        return value
    else:
        parser.error(error + " [" + str(value) + "]")
        return None


def unique_random_integers(
    start: int, end: int, num: int, max_tries: int = 100, open_interval=False
) -> Iterable[int]:
    """
    Create array with num random integers between start and end.

    Generated random numbers have no duplicates.

    Boundaries are inclusive.
    Distribution is uniform between start and end.
    """
    if open_interval:
        start += 1
        end -= 1

    if num < 0:
        raise ValueError("Number of samples must be larger or equal zero.")
    if start > end:
        raise ValueError("Start must be smaller or equal end.")
    if (end - start + 1) < num:
        raise ValueError("Interval too small for requested number of samples.")
    if max_tries <= 0:
        raise ValueError("Number of tries must be larger 0")

    if num == 0:
        return []

    if start == end:
        return [start]

    if end - start == num:
        arr = list(range(start, end + 1))
        np.random.shuffle(arr)
        return arr

    rng = np.random.default_rng()
    res = set()

    tries = 0

    # generate random numbers and avoid duplicates
    while len(res) < num and tries <= max_tries:
        tmp_cnt = num - len(res)
        nums = rng.integers(start, end, size=tmp_cnt, endpoint=True)
        res.update(nums)

        tries += 1

    # convert to native int
    res = [i.item() for i in list(res)]

    return res


def unique_random_reals(
    start: float, end: float, num: int, max_tries: int = 100
) -> Iterable[float]:
    """
    Create array with num random floating point numbers between start and end.

    Generated random numbers have no duplicates.

    Boundaries are inclusive for start and exclusive for end.
    Distribution is uniform between start and end.
    """
    if num < 0:
        raise ValueError("Number of samples must be larger or equal zero.")
    if start > end:
        raise ValueError("Start must be smaller or equal end.")
    if max_tries <= 0:
        raise ValueError("Number of tries must be larger 0")

    if num == 0:
        return []

    if start == end:
        return [float(start)]

    rng = np.random.default_rng()
    res = set()

    tries = 0

    # generate random numbers and avoid duplicates
    while len(res) < num and tries <= max_tries:
        tmp_cnt = num - len(res)
        nums = rng.uniform(start, end, tmp_cnt)

        res.update(nums)

        tries += 1

    # convert to native float
    res = [i.item() for i in list(res)]

    return res


class KVListAction(argparse.Action):
    """Argparse action for parsing a dictionary with keys and value lists

    Expected values are of the form: KEY#VAL1,VAL2,VAL3
    """

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())

        for value in values:
            key, values = value.split("#")
            velems = values.split(",")
            attr = getattr(namespace, self.dest)

            if key in attr:
                raise ValueError(f"Key {key} appeared more than once.")

            attr[key] = list()
            for v in velems:
                attr[key].append(v)
