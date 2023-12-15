/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// Implementation of things in internal.h
#include "internal.h"

#include <cstdarg>
#include <iostream>

#include "augmentum.h"

namespace augmentum {
void Internal::debug_print(const char* message) { std::cout << message; }

void Internal::debug_print_addr(const void* addr) { std::cout << addr; }

TypeDesc* Internal::get_unknown_type(const char* module, const char* signature) {
  return UnknownTypeDesc::get(module, signature);
}

TypeDesc* Internal::get_void_type() { return VoidTypeDesc::get(); }

TypeDesc* Internal::get_i1_type() { return IntTypeDesc::get_i1(); }
TypeDesc* Internal::get_i8_type() { return IntTypeDesc::get_i8(); }
TypeDesc* Internal::get_i16_type() { return IntTypeDesc::get_i16(); }
TypeDesc* Internal::get_i32_type() { return IntTypeDesc::get_i32(); }
TypeDesc* Internal::get_i64_type() { return IntTypeDesc::get_i64(); }

TypeDesc* Internal::get_float_type() { return FloatTypeDesc::get_float(); }
TypeDesc* Internal::get_double_type() { return FloatTypeDesc::get_double(); }

TypeDesc* Internal::get_ptr_type(TypeDesc* elem_type) { return PointerTypeDesc::get(elem_type); }

TypeDesc* Internal::get_array_type(TypeDesc* contained_type, size_t num_elems) {
  return ArrayTypeDesc::get(contained_type, num_elems);
}

static std::vector<TypeDesc*> va_to_type_vec(size_t n, std::va_list va) {
  std::vector<TypeDesc*> types;
  for (int i = 0; i < n; ++i) {
    types.push_back(va_arg(va, TypeDesc*));
  }
  return types;
}

TypeDesc* Internal::get_anon_struct_type(size_t num_elems, ...) {
  std::va_list va;
  va_start(va, num_elems);
  auto elem_types = va_to_type_vec(num_elems, va);
  va_end(va);

  return StructTypeDesc::get_anon(elem_types);
}
TypeDesc* Internal::get_forward_struct_type(const char* module, const char* name) {
  return StructTypeDesc::get_forward(module, name);
}
void Internal::set_struct_elem_types(TypeDesc* type, size_t num_elems, ...) {
  auto td = reinterpret_cast<StructTypeDesc*>(type);

  std::va_list va;
  va_start(va, num_elems);
  auto elem_types = va_to_type_vec(num_elems, va);
  va_end(va);

  td->set_elem_types(elem_types);
}

TypeDesc* Internal::get_function_type(TypeDesc* return_type, size_t num_args, ...) {
  std::va_list va;
  va_start(va, num_args);
  auto arg_types = va_to_type_vec(num_args, va);
  va_end(va);

  return FnTypeDesc::get(return_type, arg_types);
}

FnExtensionPoint* Internal::create_extension_point(const char* module, const char* name,
                                                   TypeDesc* type, Fn* fn, Fn original, Fn extended,
                                                   ReflectFn reflect) {
  FnExtensionPoint* pt = new FnExtensionPoint(module, name, reinterpret_cast<FnTypeDesc*>(type), fn,
                                              original, extended, reflect);
  FnExtensionPoint::register_extension_point(*pt);
  // Unregistering will be handled by empty_registry in augmentum.cpp
  return pt;
}

void Internal::eval(FnExtensionPoint* pt, RetVal ret, ArgVals args) {
  FnExtensionPoint::eval(*pt, ret, args);
}
}  // namespace augmentum
