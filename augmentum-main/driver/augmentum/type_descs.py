# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Iterable

import augmentum.paths


class CppType:
    """
    A cpp type can have a head part and a tail part. Those bracket a potential identifier,
    for example, for an array:
    int* id[3]

    The type can also have only a head part which preceed an identifier:
    size_t id
    """

    def __init__(self, head: str, tail: str = ""):
        self.head = head
        self.tail = tail

    def get_type_string(self, identifier=None):
        if identifier:
            return f"{self.head} {identifier} {self.tail}"
        else:
            return f"{self.head}{self.tail}"


class TypeDesc:
    def get_paths(
        self, ctx: "augmentum.paths.PathContext"
    ) -> Iterable["augmentum.paths.Path"]:
        raise NotImplementedError

    @property
    def pointer(self):
        return PointerTypeDesc(self)

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        """Returns a cpp representation of this type.
        The is_dereffed flag prevents recursion past a single dereference. Anything deeper than a single
        dereference will be resolved as void*.
        """
        raise NotImplementedError


class VoidTypeDesc(TypeDesc):
    def get_paths(
        self, ctx: "augmentum.paths.PathContext"
    ) -> Iterable["augmentum.paths.Path"]:
        return []

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        return CppType("void")

    def __str__(self) -> str:
        return "void"


class PrimitiveTypeDesc(TypeDesc):
    def get_paths(
        self, ctx: "augmentum.paths.PathContext"
    ) -> Iterable["augmentum.paths.Path"]:
        if ctx == augmentum.paths.PathContext.ARG:
            return []
        return [augmentum.paths.LeafPath(self)]


class IntTypeDesc(PrimitiveTypeDesc):
    def __init__(self, bits: int):
        self.bits = bits

    def get_paths(
        self, ctx: "augmentum.paths.PathContext"
    ) -> Iterable["augmentum.paths.Path"]:
        if ctx == augmentum.paths.PathContext.ARG:
            return []

        ps = [augmentum.paths.LeafPath(self)]
        if self.bits == 64 or self.bits == 32 or self.bits == 16:
            half_type = IntTypeDesc(self.bits // 2)
            ps.extend(
                [augmentum.paths.SplitIntLeftPath(p) for p in half_type.get_paths(ctx)]
            )
            ps.extend(
                [augmentum.paths.SplitIntRightPath(p) for p in half_type.get_paths(ctx)]
            )
        # TODO currently deactivated until better understood
        # if self.bits == 32:
        #     # Sometimes an i32 can be a float
        #     ps.extend(RealTypeDesc(32).get_paths(ctx))

        return ps

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        if self.bits == 1:
            cpp_type = CppType("bool")
        elif self.bits in [8, 16, 32, 64]:
            cpp_type = CppType(f"int{self.bits}_t")
        else:
            raise NotImplementedError(
                f"Integer type with {self.bits} not implemented yet."
            )

        return cpp_type

    def __str__(self) -> str:
        return f"i{self.bits}"


class RealTypeDesc(PrimitiveTypeDesc):
    def __init__(self, bits: int):
        self.bits = bits

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        if self.bits == 32:
            cpp_type = CppType("float")
        elif self.bits == 64:
            cpp_type = CppType("double")
        else:
            raise NotImplementedError(
                f"Real type with {self.bits} not implemented yet."
            )

        return cpp_type

    def __str__(self) -> str:
        return f"f{self.bits}"


class PointerTypeDesc(TypeDesc):
    def __init__(self, pointee: TypeDesc):
        self.pointee = pointee

    def get_paths(
        self, ctx: "augmentum.paths.PathContext"
    ) -> Iterable["augmentum.paths.Path"]:
        if ctx == augmentum.paths.PathContext.ARG:
            return [
                augmentum.paths.DerefPath(p)
                for p in self.pointee.get_paths(augmentum.paths.PathContext.DEREFFED)
            ]
        return []

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        if is_dereffed:
            cpp_type = CppType("void*")  # do not recurse deeper if already dereffed
        else:
            cpp_type = self.pointee.get_cpp_type(is_dereffed=True)
            cpp_type.head += "*"

        return cpp_type

    def __str__(self) -> str:
        return f"{self.pointee}*"


class SequentialTypeDesc(TypeDesc):
    def __init__(self, contained_type: TypeDesc, num_elems: int):
        self.contained_type = contained_type
        self.num_elems = num_elems

    def get_paths(
        self, ctx: "augmentum.paths.PathContext"
    ) -> Iterable["augmentum.paths.Path"]:
        raise NotImplementedError

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        raise NotImplementedError


class ArrayTypeDesc(SequentialTypeDesc):
    def __init__(self, contained_type: TypeDesc, num_elems: int):
        super().__init__(contained_type, num_elems)

    def get_paths(
        self, ctx: "augmentum.paths.PathContext"
    ) -> Iterable["augmentum.paths.Path"]:
        # TODO PATHS (first three or all if short)
        return []

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        cpp_type = self.contained_type.get_cpp_type(is_dereffed=is_dereffed)
        cpp_type.tail += f"[{self.num_elems}]"
        return cpp_type

    def __str__(self) -> str:
        return f"[{self.num_elems} x {self.contained_type}]"


# TODO VectorTypeDesc
#  don't forget to add VectorTypeDesc to collect_required_structs in probes


STRUCT_NAME_REX = r"^(?P<kind>class|struct|union)\.(?P<type>.+)"


class StructTypeDesc(TypeDesc):
    # ids used internally for extension code to avoid naming conflicts
    next_augmentum_struct_id = 0

    def __init__(
        self,
        module: str,
        name: str,
        forward: bool = False,
        packed: bool = False,
        *elem_types: TypeDesc,
    ):
        self.__module = module
        self.__name = name
        self.__augmentum_name = (
            f"__augmentum__struct_{StructTypeDesc.next_augmentum_struct_id}"
        )
        StructTypeDesc.next_augmentum_struct_id += 1
        self.__forward = forward
        self.__packed = packed
        self.elem_types = elem_types

    def get_paths(
        self, ctx: "augmentum.paths.PathContext"
    ) -> Iterable["augmentum.paths.Path"]:
        return [
            augmentum.paths.StructElementPath(i, p)
            for i, t in enumerate(self.elem_types)
            for p in t.get_paths(ctx)
        ]

    @property
    def name(self) -> str:
        return self.__name

    @property
    def augmentum_name(self) -> str:
        return self.__augmentum_name

    @property
    def module(self) -> str:
        return self.__module

    def is_forward(self) -> bool:
        """
        Determine if this is currently a forward declaration -
        i.e. that the element types have not been set.
        """
        return self.__forward

    def is_packed(self) -> bool:
        return self.__packed

    def set_element_types(self, *elem_types: TypeDesc):
        """
        Set the element types.
        If the struct is forward, then set the element types.
        Otherwise the new element types must match the old ones.
        """
        if self.is_forward():
            self.elem_types = elem_types
            self.__forward = False
        else:
            assert (
                self.elem_types == elem_types
            ), "Cannot set element types to a different value"

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        return CppType(self.augmentum_name)

    def generate_forward_decl_code(self) -> str:
        return self.__generate_def_internal(True, False)

    def generate_definition_code(self, is_dereffed: bool = False) -> str:
        return self.__generate_def_internal(self.is_forward(), is_dereffed)

    def __generate_def_internal(self, is_forward: bool, is_dereffed: bool) -> str:
        packed = "__attribute__ ((packed))" if self.is_packed() else ""

        struct_header = f"struct {packed} {self.augmentum_name}"
        name_comment = f"// {self.name}"

        if is_forward:
            return f"{struct_header}; {name_comment}"
        else:
            definition = f"{struct_header} {{ {name_comment}" + "\n"

            for idx, elem in enumerate(self.elem_types):
                ident = f"e{idx}"
                cpp_type = elem.get_cpp_type(is_dereffed)
                definition += f"   {cpp_type.get_type_string(identifier=ident)};"
                if isinstance(elem, UnknownTypeDesc):
                    definition += f" // {elem}"
                definition += "\n"
            definition += "};\n"
            return definition

    def __str__(self) -> str:
        return str(self.name)


class FunctionTypeDesc(TypeDesc):
    def __init__(self, return_type: TypeDesc, *arg_types: TypeDesc):
        self.return_type = return_type
        self.arg_types = arg_types

    def get_paths(
        self, ctx: "augmentum.paths.PathContext" = None
    ) -> Iterable["augmentum.paths.Path"]:
        # only get paths for function context
        if ctx == augmentum.paths.PathContext.FUNCTION:
            ps = []
            ps.extend(
                [
                    augmentum.paths.ResultPath(p)
                    for p in self.return_type.get_paths(
                        augmentum.paths.PathContext.RESULT
                    )
                ]
            )
            for i, t in enumerate(self.arg_types):
                ps.extend(
                    [
                        augmentum.paths.ArgumentPath(i, p)
                        for p in t.get_paths(augmentum.paths.PathContext.ARG)
                    ]
                )
            return ps
        else:
            return []

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        """This is a special case which we do not expect to be used. Hence a simple void is returned."""
        return CppType("void")

    def __str__(self) -> str:
        return str(self.return_type) + "(" + ",".join(map(str, self.arg_types)) + ")"


class UnknownTypeDesc(TypeDesc):
    def __init__(self, descriptor: str = "no descriptor"):
        self.__descriptor = descriptor

    def get_paths(
        self, ctx: "augmentum.paths.PathContext" = None
    ) -> Iterable["augmentum.paths.Path"]:
        return []

    @property
    def descriptor(self):
        return self.__descriptor

    def get_cpp_type(self, is_dereffed: bool = False) -> CppType:
        return CppType("__augmentum__UNKNOWN_TYPE")

    def __str__(self) -> str:
        return f"unknown {self.descriptor}"


void_t = VoidTypeDesc()
i1_t = IntTypeDesc(1)
i8_t = IntTypeDesc(8)
i16_t = IntTypeDesc(16)
i32_t = IntTypeDesc(32)
i64_t = IntTypeDesc(64)
half_t = RealTypeDesc(16)
float_t = RealTypeDesc(32)
double_t = RealTypeDesc(64)
