/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "type.h"

#include <unordered_map>

using namespace augmentum;

///////////////////////////////////////////////////////////////////////////////
// Main API
///////////////////////////////////////////////////////////////////////////////

// This is needed vor building array type and vector type keys
template <typename A, typename B>
struct std::hash<std::pair<A, B>> {
  size_t operator()(const std::pair<A, B>& p) const {
    size_t h1 = std::hash<A>()(p.first);
    size_t h2 = std::hash<B>()(p.second);
    return h1 ^ (h2 << 1);
  }
};

VoidTypeDesc VoidTypeDesc::void_type;
IntTypeDesc IntTypeDesc::i1_type(1);
IntTypeDesc IntTypeDesc::i8_type(8);
IntTypeDesc IntTypeDesc::i16_type(16);
IntTypeDesc IntTypeDesc::i32_type(32);
IntTypeDesc IntTypeDesc::i64_type(64);
FloatTypeDesc FloatTypeDesc::float_type(32);
FloatTypeDesc FloatTypeDesc::double_type(64);

// UnknownTypeDesc
static std::unordered_map<std::string, UnknownTypeDesc*> unknowns;
UnknownTypeDesc* UnknownTypeDesc::get(std::string module, std::string signature) {
  std::string key = module + "::" + signature;
  auto it = unknowns.find(key);
  if (it == unknowns.end()) {
    auto td = new UnknownTypeDesc(module, signature);
    unknowns[key] = td;
    return td;
  } else {
    return it->second;
  }
}

// ArrayTypeDesc
static std::unordered_map<std::pair<TypeDesc*, size_t>, ArrayTypeDesc*> array_types;
ArrayTypeDesc* ArrayTypeDesc::get(TypeDesc* contained_type, size_t num_elems) {
  std::pair<TypeDesc*, size_t> key = std::make_pair(contained_type, num_elems);
  auto it = array_types.find(key);
  if (it == array_types.end()) {
    auto td = new ArrayTypeDesc(contained_type, num_elems);
    array_types[key] = td;
    return td;
  } else {
    return it->second;
  }
}

// VectorTypeDesc
static std::unordered_map<std::pair<TypeDesc*, size_t>, VectorTypeDesc*> vector_types;
VectorTypeDesc* VectorTypeDesc::get(TypeDesc* contained_type, size_t num_elems) {
  std::pair<TypeDesc*, size_t> key = std::make_pair(contained_type, num_elems);
  auto it = vector_types.find(key);
  if (it == vector_types.end()) {
    auto td = new VectorTypeDesc(contained_type, num_elems);
    vector_types[key] = td;
    return td;
  } else {
    return it->second;
  }
}

static std::unordered_map<std::string, StructTypeDesc*> anon_structs;
StructTypeDesc* StructTypeDesc::get_anon(std::vector<TypeDesc*> elem_types) {
  // Simplest thing (not efficient) - make the struct, use its signature as key,
  // throw struct away if we already have it.
  auto td = new StructTypeDesc("", "", elem_types, false);

  std::string key = td->get_signature();
  auto it = anon_structs.find(key);
  if (it == anon_structs.end()) {
    anon_structs[key] = td;
    return td;
  } else {
    delete td;
    return it->second;
  }
}

static std::unordered_map<std::string, StructTypeDesc*> named_structs;
StructTypeDesc* StructTypeDesc::get_named(std::string module, std::string name,
                                          std::vector<TypeDesc*> elem_types) {
  std::string key = module + "::" + name;
  auto it = named_structs.find(key);
  if (it == named_structs.end()) {
    auto td = new StructTypeDesc(module, name, elem_types, false);
    named_structs[key] = td;
    return td;
  } else {
    auto td = it->second;
    td->set_elem_types(elem_types);
    return td;
  }
}
StructTypeDesc* StructTypeDesc::get_forward(std::string module, std::string name) {
  std::string key = module + "::" + name;
  auto it = named_structs.find(key);
  if (it == named_structs.end()) {
    auto td = new StructTypeDesc(module, name, {}, true);
    named_structs[key] = td;
    return td;
  } else {
    auto td = it->second;
    return td;
  }
}

static std::unordered_map<std::string, FnTypeDesc*> function_types;
FnTypeDesc* FnTypeDesc::get(TypeDesc* return_type, std::vector<TypeDesc*> arg_types) {
  // Simplest thing (not efficient) - make the type, use its signature as key,
  // throw type away if we already have it.
  auto td = new FnTypeDesc(return_type, arg_types);

  std::string key = td->get_signature();
  auto it = function_types.find(key);
  if (it == function_types.end()) {
    function_types[key] = td;
    return td;
  } else {
    delete td;
    return it->second;
  }
}

__attribute__((destructor)) static void delete_types() {
  for (auto& [k, v] : unknowns) delete v;
  for (auto& [k, v] : array_types) delete v;
  for (auto& [k, v] : vector_types) delete v;
  for (auto& [k, v] : anon_structs) delete v;
  for (auto& [k, v] : named_structs) delete v;
  for (auto& [k, v] : function_types) delete v;
}
