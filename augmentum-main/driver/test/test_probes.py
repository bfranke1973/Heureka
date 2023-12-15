# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest

from augmentum.probes import get_struct_definitions_from_fntype
from augmentum.type_descs import (
    ArrayTypeDesc,
    FunctionTypeDesc,
    StructTypeDesc,
    i8_t,
    i32_t,
    void_t,
)


class TestStructDefinitionGeneration(unittest.TestCase):
    def setUp(self) -> None:
        StructTypeDesc.next_augmentum_struct_id = 0

    def test_single_struct(self):
        my_struct_td = StructTypeDesc(
            "mymod.cpp", "MyStruct", False, False, i32_t, i32_t
        )
        fn_type = FunctionTypeDesc(void_t, my_struct_td)

        expected_code = """
struct  __augmentum__struct_0 { // MyStruct
   int32_t e0 ;
   int32_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )

    def test_dependent_struct(self):
        my_inner_struct_td = StructTypeDesc(
            "mymod.cpp", "MyInnerStruct", False, False, i32_t, i32_t
        )
        my_struct_td = StructTypeDesc(
            "mymod.cpp", "MyStruct", False, False, my_inner_struct_td, i32_t
        )
        fn_type = FunctionTypeDesc(void_t, my_struct_td)

        expected_code = """
struct  __augmentum__struct_0 { // MyInnerStruct
   int32_t e0 ;
   int32_t e1 ;
};

struct  __augmentum__struct_1 { // MyStruct
   __augmentum__struct_0 e0 ;
   int32_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )

    def test_self_dependent_struct(self):
        my_struct_td = StructTypeDesc("mymod.cpp", "MyStruct", True, False)
        my_struct_td.set_element_types(my_struct_td.pointer, i32_t)
        fn_type = FunctionTypeDesc(void_t, my_struct_td)

        expected_code = """
struct  __augmentum__struct_0; // MyStruct
struct  __augmentum__struct_0 { // MyStruct
   __augmentum__struct_0* e0 ;
   int32_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )

    def test_circular_dependency_A(self):
        my_struct_A_td = StructTypeDesc("mymod.cpp", "MyStructA", True, False)
        my_struct_B_td = StructTypeDesc("mymod.cpp", "MyStructB", True, False)
        my_struct_A_td.set_element_types(my_struct_B_td, i32_t)
        my_struct_B_td.set_element_types(my_struct_A_td.pointer, i8_t)

        fn_type = FunctionTypeDesc(void_t, my_struct_A_td)

        expected_code = """
struct  __augmentum__struct_0; // MyStructA
struct  __augmentum__struct_1 { // MyStructB
   __augmentum__struct_0* e0 ;
   int8_t e1 ;
};

struct  __augmentum__struct_0 { // MyStructA
   __augmentum__struct_1 e0 ;
   int32_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )

    def test_circular_dependency_B(self):
        my_struct_A_td = StructTypeDesc("mymod.cpp", "MyStructA", True, False)
        my_struct_B_td = StructTypeDesc("mymod.cpp", "MyStructB", True, False)
        my_struct_A_td.set_element_types(my_struct_B_td.pointer, i32_t)
        my_struct_B_td.set_element_types(my_struct_A_td.pointer, i8_t)

        fn_type = FunctionTypeDesc(void_t, my_struct_A_td)

        # expected the second pointer to be void
        # because we consider only a single dereference
        expected_code = """
struct  __augmentum__struct_1; // MyStructB
struct  __augmentum__struct_0 { // MyStructA
   __augmentum__struct_1* e0 ;
   int32_t e1 ;
};

struct  __augmentum__struct_1 { // MyStructB
   void* e0 ;
   int8_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )

    def test_circular_dependency_C(self):
        my_struct_A_td = StructTypeDesc("mymod.cpp", "MyStructA", True, False)
        my_struct_B_td = StructTypeDesc("mymod.cpp", "MyStructB", True, False)
        my_struct_C_td = StructTypeDesc("mymod.cpp", "MyStructC", True, False)

        my_struct_A_td.set_element_types(my_struct_B_td, i32_t)
        my_struct_B_td.set_element_types(my_struct_C_td, i8_t)
        my_struct_C_td.set_element_types(my_struct_A_td.pointer, i8_t.pointer)

        fn_type = FunctionTypeDesc(void_t, my_struct_A_td)

        expected_code = """
struct  __augmentum__struct_0; // MyStructA
struct  __augmentum__struct_2 { // MyStructC
   __augmentum__struct_0* e0 ;
   int8_t* e1 ;
};

struct  __augmentum__struct_1 { // MyStructB
   __augmentum__struct_2 e0 ;
   int8_t e1 ;
};

struct  __augmentum__struct_0 { // MyStructA
   __augmentum__struct_1 e0 ;
   int32_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )

    def test_circular_array_dependency_A(self):
        my_struct_A_td = StructTypeDesc("mymod.cpp", "MyStructA", True, False)
        my_struct_B_td = StructTypeDesc("mymod.cpp", "MyStructB", True, False)
        array_my_struct_B = ArrayTypeDesc(my_struct_B_td, 5)

        my_struct_A_td.set_element_types(array_my_struct_B, i32_t)
        my_struct_B_td.set_element_types(my_struct_A_td.pointer, i8_t)

        fn_type = FunctionTypeDesc(void_t, my_struct_A_td)

        expected_code = """
struct  __augmentum__struct_0; // MyStructA
struct  __augmentum__struct_1 { // MyStructB
   __augmentum__struct_0* e0 ;
   int8_t e1 ;
};

struct  __augmentum__struct_0 { // MyStructA
   __augmentum__struct_1 e0 [5];
   int32_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )

    def test_circular_array_dependency_B(self):
        my_struct_A_td = StructTypeDesc("mymod.cpp", "MyStructA", True, False)
        my_struct_B_td = StructTypeDesc("mymod.cpp", "MyStructB", True, False)
        array_my_struct_B = ArrayTypeDesc(my_struct_B_td.pointer, 5)

        my_struct_A_td.set_element_types(array_my_struct_B, i32_t)
        my_struct_B_td.set_element_types(my_struct_A_td.pointer, i8_t)

        fn_type = FunctionTypeDesc(void_t, my_struct_A_td)

        # expected the second pointer to be void
        # because we consider only a single dereference
        expected_code = """
struct  __augmentum__struct_1 { // MyStructB
   void* e0 ;
   int8_t e1 ;
};

struct  __augmentum__struct_0 { // MyStructA
   __augmentum__struct_1* e0 [5];
   int32_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )

    def test_circular_array_dependency_C(self):
        my_struct_A_td = StructTypeDesc("mymod.cpp", "MyStructA", True, False)
        my_struct_B_td = StructTypeDesc("mymod.cpp", "MyStructB", True, False)
        array_my_struct_A = ArrayTypeDesc(my_struct_A_td.pointer, 5)

        my_struct_A_td.set_element_types(my_struct_B_td, i32_t)
        my_struct_B_td.set_element_types(array_my_struct_A.pointer, i8_t)

        fn_type = FunctionTypeDesc(void_t, my_struct_A_td)

        # expected the second pointer to be void
        # because we consider only a single dereference
        expected_code = """
struct  __augmentum__struct_1 { // MyStructB
   void** e0 [5];
   int8_t e1 ;
};

struct  __augmentum__struct_0 { // MyStructA
   __augmentum__struct_1 e0 ;
   int32_t e1 ;
};
        """

        self.assertEqual(
            get_struct_definitions_from_fntype(fn_type).strip(),
            expected_code.strip(),
            "Generated code not as expected.",
        )
