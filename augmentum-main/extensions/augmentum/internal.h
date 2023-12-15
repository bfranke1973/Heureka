/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Internal API, essentially this is what is used by the instrumenter.
// It is used only because it is a slightly simpler API to manually construct in
// LLVM.
#ifndef __AUGMENTUM_INTERNAL__
#define __AUGMENTUM_INTERNAL__

#include <cstdint>

namespace augmentum {
struct TypeDesc;
typedef void* RetVal;
typedef void** ArgVals;
typedef void (*Fn)();
typedef void (*ReflectFn)(RetVal, ArgVals);
struct FnExtensionPoint;

struct Internal {
  static void debug_print(const char* message);
  static void debug_print_addr(const void* addr);

  static TypeDesc* get_unknown_type(const char* module, const char* signature);
  static TypeDesc* get_void_type();
  static TypeDesc* get_i1_type();
  static TypeDesc* get_i8_type();
  static TypeDesc* get_i16_type();
  static TypeDesc* get_i32_type();
  static TypeDesc* get_i64_type();
  static TypeDesc* get_float_type();
  static TypeDesc* get_double_type();
  static TypeDesc* get_ptr_type(TypeDesc* elem_type);
  static TypeDesc* get_array_type(TypeDesc* contained_type, std::size_t num_elems);
  static TypeDesc* get_anon_struct_type(std::size_t num_elems, ...);
  static TypeDesc* get_forward_struct_type(const char* module, const char* name);
  static void set_struct_elem_types(TypeDesc* type, std::size_t num_elems, ...);
  static TypeDesc* get_function_type(TypeDesc* return_type, std::size_t num_args, ...);
  static FnExtensionPoint* create_extension_point(const char* module, const char* name,
                                                  TypeDesc* type, Fn* fn, Fn original, Fn extended,
                                                  ReflectFn reflect);
  static void eval(FnExtensionPoint* pt, RetVal, ArgVals);
};
}  // namespace augmentum

#endif
