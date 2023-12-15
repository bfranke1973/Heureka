#!/usr/bin/env python3

# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Generate extension code for a specified function and path.
"""

import argparse
import pathlib
import pickle
import sys
from typing import Dict, Generator, Iterable, Optional

from augmentum.function import (
    Function,
    FunctionData,
    NamedStructData,
    load_named_structs,
    load_target_function_stats,
)
from augmentum.functionfilter import FunctionFilter, InstrumentDefault
from augmentum.probes import NullProbe
from augmentum.timer import Timer
from augmentum.type_serialisation import DeserialisationContext, TypeDeserialiser


def deserialise_functions(
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


def load_functions(
    cfg: pathlib.Path,
    function_filter: FunctionFilter,
    function_cache: Optional[pathlib.Path],
) -> Iterable[Function]:
    """
    Collect target functions, deserialise and filter them.

    Use cached version if available.
    """

    if function_cache is not None and function_cache.exists():
        print("Loading cached target functions from " + str(function_cache) + " ...")
        with function_cache.open("rb") as infile:
            target_functions = pickle.load(infile)
    else:
        print("Loading functions ...")
        with Timer(logger=print):
            target_function_data = load_target_function_stats(
                cfg / "function_stats_relative.csv"
            )
            named_structs = load_named_structs(cfg / "named_struct_stats_relative.csv")

        print("Deserialising funtions ...")
        with Timer(logger=print):
            target_functions = deserialise_functions(
                function_filter, target_function_data, named_structs
            )

        if function_cache is not None:
            print("Caching target functions to " + str(function_cache) + " ...")
            with function_cache.open("wb") as outfile:
                pickle.dump(target_functions, outfile)

    return target_functions


def generate_extension(
    module: str,
    function: str,
    path: str,
    wd: pathlib.Path,
    cfg: pathlib.Path,
    fn_cache: Optional[pathlib.Path],
):
    functions = load_functions(cfg, InstrumentDefault(), fn_cache)

    my_fn = None
    my_path = None

    for fn in functions:
        if fn.name == function and fn.module == module:
            paths = fn.get_paths()
            for p in paths:
                if str(p) == path:
                    my_fn = fn
                    my_path = p
                    break
            if p is not None:
                break

    if my_fn is None or my_path is None:
        print("ERROR: Function or path not found.")
        sys.exit(1)

    my_probe = NullProbe(my_fn, my_path, "Manual Extension Generator")
    extension_code = my_probe.extension_code(
        pathlib.Path("this/is/not/required.txt"), pathlib.Path("/this/is/not/required")
    )
    outfile = pathlib.Path(wd) / "extension.cpp"
    with outfile.open("w") as f:
        f.write(extension_code)

    print(
        f"Null Probe extension generated for\n function {my_fn}\n path {my_path}\n at {outfile}"
    )


def parse_args():
    """Specification and parsing of command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate the extension code for the specified function."
    )

    parser.add_argument(
        "--mod", metavar="NAME", type=str, required=True, help="Specify a module name."
    )
    parser.add_argument(
        "--fn", metavar="NAME", type=str, required=True, help="Specify a function name."
    )
    parser.add_argument(
        "--path", metavar="NAME", type=str, required=True, help="Specify a path name."
    )

    parser.add_argument(
        "--working_dir",
        metavar="DIR",
        type=pathlib.Path,
        required=True,
        help="Directory for generated data.",
    )
    parser.add_argument(
        "--config_dir",
        metavar="DIR",
        type=pathlib.Path,
        required=True,
        help="Directory holding function configuration data.",
    )
    parser.add_argument(
        "--function_cache",
        metavar="FILE",
        type=pathlib.Path,
        help="File path to function cache. "
        "If file does not exist, a cache will be create after colleting functions.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    generate_extension(
        args.mod,
        args.fn,
        args.path,
        args.working_dir,
        args.config_dir,
        fn_cache=args.function_cache,
    )


if __name__ == "__main__":
    main()
