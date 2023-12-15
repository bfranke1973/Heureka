# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import re
from typing import Dict, Iterable, Tuple

from augmentum.function import Function
from augmentum.type_descs import (
    FunctionTypeDesc,
    PointerTypeDesc,
    PrimitiveTypeDesc,
    StructTypeDesc,
    TypeDesc,
    UnknownTypeDesc,
)

DTOR_REGEX = r"(_ZN)(.*)(D[0,1,2]Ev)"
STL_REGEX = r"^_Z+(St|NS|NKSt|NVKS|NVS|N9__gnu_cxx|NK9__gnu_cxx)"

# cache structs with unknown elements here
# to speed up computation and avoid endless recursion into self referring structs
structs_with_unknown_elements: Dict[str, bool] = {}


def is_stl_function(mangled_name: str) -> bool:
    return re.match(STL_REGEX, mangled_name) is not None


def is_dtor(mangled_name: str) -> bool:
    return re.match(DTOR_REGEX, mangled_name) is not None


def is_c_function(mangled_name: str) -> bool:
    return not mangled_name.startswith("_Z")


def only_primitive_types(function: Function) -> bool:
    """True if return and arg types of given function are primitives"""
    return_is_primitive = isinstance(function.type.return_type, PrimitiveTypeDesc)
    args_are_primitive = True
    for arg in function.type.arg_types:
        args_are_primitive = args_are_primitive and isinstance(arg, PrimitiveTypeDesc)

    return return_is_primitive and args_are_primitive


def has_unknown_types(
    td: TypeDesc,
    structs_with_unknown_elements: Dict[str, bool],
    is_dereffed: bool = False,
) -> bool:
    """Return true if any of the parameters or return types of the function
    are unknown or if any of their element types are unknown

    element types are followed recursively as long as they have not been derefferenced yet
    see get_cpp_type in type_descs.py
    """

    if isinstance(td, FunctionTypeDesc):
        is_unknown = has_unknown_types(
            td.return_type, structs_with_unknown_elements, is_dereffed
        )
        for a in td.arg_types:
            if is_unknown:
                break
            is_unknown = is_unknown or has_unknown_types(
                a, structs_with_unknown_elements, is_dereffed
            )
        return is_unknown

    elif isinstance(td, StructTypeDesc):
        if td.name in structs_with_unknown_elements:
            return structs_with_unknown_elements[td.name]
        else:
            # remember that we are currently looking at this struct
            structs_with_unknown_elements[td.name] = False

        is_unknown = False
        for e in td.elem_types:
            if is_unknown:
                break
            is_unknown = is_unknown or has_unknown_types(
                e, structs_with_unknown_elements, is_dereffed
            )
        structs_with_unknown_elements[td.name] = is_unknown
        return is_unknown

    elif isinstance(td, PointerTypeDesc):
        if is_dereffed:  # do not recurse deeper if already dereffed
            return False
        else:
            return has_unknown_types(
                td.pointee, structs_with_unknown_elements, is_dereffed=True
            )

    elif isinstance(td, UnknownTypeDesc):
        return True

    else:
        return False


class FunctionFilter:
    def should_instrument(self, function: Function) -> bool:
        raise NotImplementedError


class InstrumentAllFilter(FunctionFilter):
    def should_instrument(self, function: Function) -> bool:
        return True


class InstrumentDefault(FunctionFilter):
    """
    Instrument all functions that can be instrumented,
    are not standard library functions, destructors, main or c functions,
    or contain structs which have unknown types.
    """

    def should_instrument(self, function: Function) -> bool:
        if function.function_stats.can_instrument != "instrument":
            return False

        if function.name == "main":
            return False

        if is_c_function(function.name):
            return False

        if is_stl_function(function.name):
            return False

        if is_dtor(function.name):
            return False

        global structs_with_unknown_elements
        if has_unknown_types(function.type, structs_with_unknown_elements):
            return False

        return True


class InstrumentPrimitiveReturn(InstrumentDefault):
    """
    Instrument all functions that can be instrumented,
    are not standard library functions, destructors, main or c functions,
    contain structs which have unknown types, and have a primitive return type.
    """

    def should_instrument(self, function: Function) -> bool:
        return super().should_instrument(function) and isinstance(
            function.type.return_type, PrimitiveTypeDesc
        )


class InstrumentPrimitiveOnly(InstrumentDefault):
    """
    Instrument all functions that can be instrumented,
    are not standard library functions, destructors, main or c functions,
    contain structs which have unknown types, and have a primitive type only as parameters and returns.
    """

    def should_instrument(self, function: Function) -> bool:
        return super().should_instrument(function) and only_primitive_types(function)


class InstrumentFunctionList(FunctionFilter):
    """
    Instrument function from a given list only.
    """

    def __init__(self, allow_list: Iterable[Tuple[str, str]]):
        self.allow_list = dict()
        for entry in allow_list:
            module = entry[0]
            function = entry[1]
            if module not in self.allow_list:
                self.allow_list[module] = set()
            self.allow_list[module].add(function)

    def should_instrument(self, function: Function) -> bool:
        if (
            function.module in self.allow_list
            and function.name in self.allow_list[function.module]
        ):
            return True
        else:
            return False
