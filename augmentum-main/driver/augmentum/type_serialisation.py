# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
from typing import Generator, Mapping, Optional

from augmentum.function import NamedStructData
from augmentum.type_descs import (
    ArrayTypeDesc,
    FunctionTypeDesc,
    IntTypeDesc,
    RealTypeDesc,
    StructTypeDesc,
    TypeDesc,
    UnknownTypeDesc,
    void_t,
)

logger = logging.getLogger(__name__)

# next id to be used for unnamed structs
next_unnamed_struct_id = 0


def find_last_closing_token(s: str, open_t: str, close_t: str) -> Optional[int]:
    """
    Find the last closing token in a string of possibly nested tokens, e.g. { i8, { i16*, f32 }, f64 }
                                                                    start ^                 return ^
    The start index of the last closing token is returned or None if the string is malformed.
    """
    assert len(open_t) == len(
        close_t
    ), "Opening and closing token are expected to have the same length"

    s_n = len(s)  # string lenght
    t_n = len(open_t)  # token length

    assert (
        s_n >= t_n * 2
    ), "At least one opening and closing token are expected in the string"
    assert s.startswith(open_t), "Initial character is expected to be the opening token"

    stack = []
    idx = 0
    while idx < s_n - t_n + 1:  # look ahead token length
        token = s[idx : idx + t_n]
        if token == open_t:
            stack.append(idx)
        elif token == close_t:
            stack.pop()
            if not stack:  # stack is empty, we found the last
                return idx
        idx += 1

    # the string was malformed
    return None


def get_elements(raw_type: str) -> Generator[str, None, None]:
    """
    Generator for splitting out comma separated elements from raw function or struct data,
    e.g. { A, B, {C, D} } yields A, B and {C,D}
    """
    if not raw_type:
        return

    start = 0
    idx = 0
    while idx < len(raw_type):
        c = raw_type[idx]
        if c == ",":
            yield raw_type[start:idx]
            start = idx + 1
        if c == "{":
            struct_close = find_last_closing_token(raw_type[idx:].strip(), "{", "}")
            if struct_close:
                idx += struct_close
            else:
                raise RuntimeError("struct element parsing error: " + raw_type)
        if c == "@" and idx < len(raw_type) - 1:
            token = raw_type[idx : idx + 2]
            if token == "@%":  # we have a named type
                type_close = find_last_closing_token(raw_type[idx:].strip(), "@%", "%@")
                if type_close:
                    idx += type_close + 1  # +1 for token length
                else:
                    raise RuntimeError("named type element parsing error: " + raw_type)

            elif token == "@$":  # we have a function type
                function_close = find_last_closing_token(
                    raw_type[idx:].strip(), "@$", "$@"
                )
                if function_close:
                    idx += function_close + 1  # +1 for token length
                else:
                    raise RuntimeError("function element parsing error: " + raw_type)

            elif token == "@U":  # we have an unknown type
                unknown_close = find_last_closing_token(
                    raw_type[idx:].strip(), "@U", "U@"
                )
                if unknown_close:
                    idx += unknown_close + 1  # +1 for token length
                else:
                    raise RuntimeError("uknown element parsing error: " + raw_type)

            else:
                raise RuntimeError("Token parsing error: " + raw_type)

        idx += 1

    # don't forget the last
    yield raw_type[start:]


def get_struct_name(serial_string: str) -> str:
    """Extract the struct name from a serialised struct representation"""
    # expected format:  @% /path/to/module.cpp::class.llvm::StringMapEntryBase %@
    pos = serial_string.find("::")
    if pos != -1:
        return serial_string[pos + 2 : -3]
    else:
        logger.error("Unexpected serial struct format: " + serial_string)
        return serial_string


class DeserialisationContext:
    def __init__(self, module_name):
        self.__module_name = module_name

    @property
    def module_name(self):
        return self.__module_name


class TypeDeserialiser:
    def __init__(self, named_struct_lookup: Mapping[str, NamedStructData]):
        # lookup table for named structs and their serialised types
        self.named_struct_lookup = named_struct_lookup
        # type cache to memoise deserialised typeDescs
        self.type_lookup: Mapping[str, TypeDesc] = dict()

    def deserialise_type(
        self, ctx: "DeserialisationContext", raw_type: str
    ) -> TypeDesc:
        """
        Expected type formats

        void: void
        integer: i<number>
        real: f<number>
        pointer: <type>*
        anonymous struct: { <type>, <type> }
        named struct: @% <name> %@, e.g. @% class.Node %@
        vector: <<type>> TODO
        array: [<type>]
        function: @$ <return ty>, <param 0 ty>, <param 1 ty>, ... $@, e.g @$ i32,i32,i32 $@
        unknown
        """

        raw_type = raw_type.strip()

        # if we have not cached this type before, deserialise it
        if raw_type not in self.type_lookup:
            if raw_type.endswith("*"):  # pointer (this check needs to come first)
                self.type_lookup[raw_type] = self.deserialise_type(
                    ctx, raw_type[:-1]
                ).pointer

            elif raw_type == "void":  # void
                self.type_lookup[raw_type] = void_t

            elif raw_type.startswith("i"):  # integer
                bytes = int(raw_type[1:])
                self.type_lookup[raw_type] = IntTypeDesc(bytes)

            elif raw_type.startswith("f"):  # real
                bytes = int(raw_type[1:])
                self.type_lookup[raw_type] = RealTypeDesc(bytes)

            elif raw_type.startswith("["):  # array
                stripped_type = raw_type[1:-1].strip()
                arr_separator = stripped_type.find("x")
                if arr_separator == -1:
                    raise RuntimeError(
                        "Unexpeced array serialisation format: " + raw_type
                    )
                num_elems = int(stripped_type[:arr_separator])
                elem_type = self.deserialise_type(
                    ctx, stripped_type[arr_separator + 1 :]
                )

                self.type_lookup[raw_type] = ArrayTypeDesc(elem_type, num_elems)

            elif raw_type.startswith("{"):  # unnamed struct
                elem_types = []
                for raw_elem in get_elements(raw_type[1:-1].strip()):
                    elem_types.append(self.deserialise_type(ctx, raw_elem))

                global next_unnamed_struct_id
                struct_name = f"struct.augmentum::unnamed_{next_unnamed_struct_id}"
                next_unnamed_struct_id += 1

                self.type_lookup[raw_type] = StructTypeDesc(
                    ctx.module_name, struct_name, False, False, *elem_types
                )

            elif raw_type.startswith("@%"):  # named struct
                if raw_type not in self.named_struct_lookup:
                    self.type_lookup[raw_type] = UnknownTypeDesc(raw_type)
                else:
                    # get packed parameter
                    is_packed = self.named_struct_lookup[raw_type].packed

                    # set forward struct
                    struct_name = get_struct_name(raw_type)

                    self.type_lookup[raw_type] = StructTypeDesc(
                        ctx.module_name, struct_name, True, is_packed
                    )

                    # parse elements
                    named_struct_type = self.named_struct_lookup[raw_type]
                    elem_types = []
                    for raw_elem in get_elements(
                        named_struct_type.serialised_type[1:-1].strip()
                    ):
                        elem_types.append(self.deserialise_type(ctx, raw_elem))

                    # set for forward struct
                    self.type_lookup[raw_type].set_element_types(*elem_types)

            elif raw_type.startswith("@$"):  # function
                function_types = []
                for raw_elem in get_elements(raw_type[2:-2].strip()):
                    function_types.append(self.deserialise_type(ctx, raw_elem))
                if len(function_types) == 1:
                    self.type_lookup[raw_type] = FunctionTypeDesc(function_types[0])
                elif len(function_types) > 1:
                    self.type_lookup[raw_type] = FunctionTypeDesc(
                        function_types[0], *function_types[1:]
                    )
                else:
                    raise RuntimeError("function parsing error: " + raw_type)

            elif raw_type.startswith("@U"):  # unknown type
                self.type_lookup[raw_type] = UnknownTypeDesc(raw_type[2:-2].strip())

            else:
                raise RuntimeError("Unknown serial format: " + raw_type)

        return self.type_lookup[raw_type]
