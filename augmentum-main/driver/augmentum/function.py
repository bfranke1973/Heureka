# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import csv
import re
from pathlib import Path
from typing import Dict, Generator, Iterable

import augmentum.paths
from augmentum.type_descs import FunctionTypeDesc

function_stats_id = "function_stats"
named_struct_stats_id = "named_struct_stats"


class NamedStructData:
    MODULE_IDX = 0
    STRUCT_NAME_IDX = 1
    TYPE_IDX = 2
    LLVM_NAME_IDX = 3
    EXTRA_IDX = 4

    def __init__(
        self,
        module_name: str,
        struct_name: str,
        serialised_type: str,
        llvm_name: str,
        extra: str,
    ):
        self.module_name = module_name
        self.struct_name = struct_name
        self.serialised_type = serialised_type
        self.llvm_name = llvm_name
        self.packed = self.extract_packed(extra)
        self.__key = None

    @property
    def key(self) -> str:
        """
        Generate a type name lookup that is uniq over modules and type names
        """
        if not self.__key:
            self.__key = "@% " + self.module_name + "::" + self.struct_name + " %@"
        return self.__key

    def extract_packed(self, data: str):
        # exepected format: named:true#packed:false#literal:false#opaque:false
        elems = data.split("#")
        assert len(elems) == 4, (
            "Unexpected format for extra struct information: " + data
        )

        packed_status = elems[1].split(":")[1]
        return True if packed_status == "true" else False

    @staticmethod
    def get_from_csv_entry(csv_entry: Iterable[str]) -> "NamedStructData":
        return NamedStructData(
            csv_entry[NamedStructData.MODULE_IDX],
            csv_entry[NamedStructData.STRUCT_NAME_IDX],
            csv_entry[NamedStructData.TYPE_IDX],
            csv_entry[NamedStructData.LLVM_NAME_IDX],
            csv_entry[NamedStructData.EXTRA_IDX],
        )

    def __str__(self):
        return (
            self.key
            + " "
            + self.module_name
            + " "
            + self.struct_name
            + " "
            + self.serialised_type
            + " "
            + self.llvm_name
        )


def load_named_structs(struct_file: Path) -> Dict[str, NamedStructData]:
    """
    Load named structs and their types from csv file.
    """
    struct_types = dict()
    with struct_file.open("r") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # skip header
        for row in reader:
            struct_data = NamedStructData.get_from_csv_entry(row)
            struct_types[struct_data.key] = struct_data

    return struct_types


class FunctionData:
    MODULE_IDX = 0
    FUNCTION_NAME = 1
    FUNCTION_NAME_DEMANGLED = 2
    INSTRUCTION_COUNT = 3
    PARAMETER_COUNT = 4
    FUNCTION_TYPE = 5
    CAN_INSTRUMENT = 6
    SHOULD_INSTRUMENT = 7

    def __init__(
        self,
        module_name: str,
        function_name: str,
        serialised_type: str,
        demangled_name: str,
        instruction_count: int,
        can_instrument: str,
    ):
        self.module_name = module_name
        self.function_name = function_name
        self.serialised_type = serialised_type
        self.function_name_demangled = demangled_name
        self.instruction_count = instruction_count
        self.can_instrument = can_instrument

    @staticmethod
    def get_from_csv_entry(csv_entry: Iterable[str]) -> "FunctionData":
        return FunctionData(
            csv_entry[FunctionData.MODULE_IDX],
            csv_entry[FunctionData.FUNCTION_NAME],
            csv_entry[FunctionData.FUNCTION_TYPE],
            csv_entry[FunctionData.FUNCTION_NAME_DEMANGLED],
            csv_entry[FunctionData.INSTRUCTION_COUNT],
            csv_entry[FunctionData.CAN_INSTRUMENT],
        )

    def __str__(self):
        return (
            self.module_name
            + " "
            + self.function_name
            + " "
            + self.serialised_type
            + " "
            + self.function_name_demangled
        )


def load_target_function_stats(
    function_file: Path,
) -> Generator[FunctionData, None, None]:
    """
    Return generator for deserialised target function statistics from csv file.
    """
    target_functions = []
    with function_file.open("r") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # skip header
        for row in reader:
            yield FunctionData.get_from_csv_entry(row)

    return target_functions


def parse_collected_function_stats(src_dir: Path, target_dir: Path) -> Dict[str, str]:
    """
    Merge function stats and named struct stats files produced by function collection
    compilation to single files.
    """

    if not src_dir.exists():
        raise RuntimeError(
            "Source directory invalid when merging function stats: " + str(src_dir)
        )
    if not target_dir.exists():
        raise RuntimeError(
            "Target directory invalid when merging function stats: " + str(target_dir)
        )

    def copy_contents(target_id: str) -> Path:
        target_file_path = target_dir / (target_id + ".csv")
        with target_file_path.open("w") as target:
            copy_header = True
            for source_file in src_dir.glob("*_" + target_id + ".csv"):
                with source_file.open("r") as source:
                    if copy_header:
                        target.writelines(source.readlines())
                        copy_header = False
                    else:
                        target.writelines(source.readlines()[1:])
        return target_file_path

    return {
        function_stats_id: copy_contents(function_stats_id),
        named_struct_stats_id: copy_contents(named_struct_stats_id),
    }


def use_relative_src_path(data_paths: Dict[str, str], src_path: Path) -> Dict[str, str]:
    """
    Drop the absolute path to the system program source location
    from each module path. This is necessary to allow different
    absolute source locations to be used for the same modules.
    """

    def drop_src_path(target_id: str):
        data_orig = Path(data_paths[target_id])
        data_mod = data_orig.parent / (data_orig.stem + "_relative" + data_orig.suffix)
        with data_orig.open("r") as f_orig, data_mod.open("w") as f_mod:
            content = f_orig.read()
            content = content.replace(str(src_path) + "/", "")
            f_mod.write(content)
        return data_mod

    return {
        function_stats_id: drop_src_path(function_stats_id),
        named_struct_stats_id: drop_src_path(named_struct_stats_id),
    }


class Module:
    """
    Represents a module and its corresponding functions
    """

    def __init__(self, name: str):
        self.name = name
        self.functions: Dict[str, Function] = dict()


ARGS_REX = r".+\((?P<args>.*)\)"


def get_const_args_from_demangled_name(demangled_name: str) -> Iterable[str]:
    def split_args(args: str) -> Iterable[str]:
        res = []
        start = 0
        open = 0
        for i, c in enumerate(args):
            if c == "," and open == 0:
                res.append(args[start:i])
                start = i + 1
            if c == "<" or c == "(" or c == "{":
                open += 1
            if c == ">" or c == ")" or c == "}":
                open -= 1
        res.append(args[start:])
        return res

    def is_const(arg: str) -> bool:
        return arg.endswith("const&") or arg.endswith("const*")

    const_args = []
    m = re.match(ARGS_REX, demangled_name)
    if m is not None:
        args_match = m.groupdict()["args"]
        if len(args_match) != 0 and "const" in args_match:
            args = split_args(args_match)
            for i, a in enumerate(args):
                if is_const(a):
                    const_args.append(f"A{i}")

    return const_args


class Function:
    """
    Represents a function.
    """

    def __init__(
        self,
        module: str,
        name: str,
        type: FunctionTypeDesc,
        function_stats: FunctionData,
    ):
        self.module = module
        self.name = name
        self.type = type
        self.function_stats = function_stats

    def get_paths(self) -> Iterable[augmentum.paths.Path]:
        paths = self.type.get_paths(ctx=augmentum.paths.PathContext.FUNCTION)

        # filter out const arguments based on demangled name
        if self.demangled_name != "NA":
            const_args = get_const_args_from_demangled_name(self.demangled_name)

            result = []
            for p in paths:
                if str(p).startswith("A") and str(p).split(".")[0] in const_args:
                    continue
                else:
                    result.append(p)
        else:
            result = paths

        return result

    @property
    def demangled_name(self):
        return self.function_stats.function_name_demangled

    def __str__(self) -> str:
        return (
            str(self.type.return_type)
            + " "
            + self.name
            + "("
            + ",".join(map(str, self.type.arg_types))
            + ")"
        )

    def __repr__(self) -> str:
        return self.__str__()


def build_modules(functions: Iterable[Function]) -> Dict[str, Module]:
    """Build modules from given list of functions"""

    modules: Dict[str, Module] = dict()
    for f in functions:
        m_name = f.module
        if m_name not in modules:
            modules[m_name] = Module(m_name)
        modules[m_name].functions[f.name] = f
    return modules
