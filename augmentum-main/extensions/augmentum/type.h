/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#ifndef __AUGMENTUM_TYPE__
#define __AUGMENTUM_TYPE__

#include <cassert>
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace augmentum {
struct PointerTypeDesc;

struct TypeDesc {
  TypeDesc(const TypeDesc&) = delete;
  TypeDesc& operator=(const TypeDesc&) = delete;
  virtual ~TypeDesc();
  virtual std::string get_signature() const = 0;
  operator std::string() const { return get_signature(); }
  enum Discriminator { UNKNOWN, VOID, INT, FLOAT, POINTER, STRUCT, FUNCTION, ARRAY, VECTOR };
  virtual Discriminator get_discriminator() const = 0;

  PointerTypeDesc* get_ptr();

 protected:
  TypeDesc() = default;

 private:
  friend class PointerTypeDesc;
  PointerTypeDesc* ptr = nullptr;
};

struct UnknownTypeDesc : TypeDesc {
  std::string get_module() const { return module; }
  std::string get_signature() const { return signature; }
  Discriminator get_discriminator() const { return UNKNOWN; }
  static UnknownTypeDesc* get(std::string module, std::string signature);

 private:
  UnknownTypeDesc(std::string module, std::string signature)
      : module(module), signature(signature) {}
  std::string module;
  std::string signature;
};

struct VoidTypeDesc : TypeDesc {
  std::string get_signature() const { return "void"; }
  Discriminator get_discriminator() const { return VOID; }
  static VoidTypeDesc* get() { return &void_type; }

 private:
  static VoidTypeDesc void_type;
};

struct IntTypeDesc : TypeDesc {
  std::string get_signature() const { return "int" + std::to_string(bits); }
  Discriminator get_discriminator() const { return INT; }
  size_t get_bits() const { return bits; }
  static IntTypeDesc* get_i1() { return &i1_type; }
  static IntTypeDesc* get_i8() { return &i8_type; }
  static IntTypeDesc* get_i16() { return &i16_type; }
  static IntTypeDesc* get_i32() { return &i32_type; }
  static IntTypeDesc* get_i64() { return &i64_type; }

 private:
  IntTypeDesc(size_t bits) : bits(bits) {}
  size_t bits;

  static IntTypeDesc i1_type;
  static IntTypeDesc i8_type;
  static IntTypeDesc i16_type;
  static IntTypeDesc i32_type;
  static IntTypeDesc i64_type;
};

struct FloatTypeDesc : TypeDesc {
  std::string get_signature() const { return bits == 32 ? "float" : "double"; }
  Discriminator get_discriminator() const { return FLOAT; }
  size_t get_bits() const { return bits; }
  static FloatTypeDesc* get_float() { return &float_type; }
  static FloatTypeDesc* get_double() { return &double_type; }

 private:
  FloatTypeDesc(size_t bits) : bits(bits) {}
  size_t bits;

  static FloatTypeDesc float_type;
  static FloatTypeDesc double_type;
};

struct PointerTypeDesc : TypeDesc {
  std::string get_signature() const { return element_type->get_signature() + "*"; }
  Discriminator get_discriminator() const { return POINTER; }
  TypeDesc* get_element_type() const { return element_type; }
  static PointerTypeDesc* get(TypeDesc* element_type);

 private:
  PointerTypeDesc(TypeDesc* element_type) : element_type(element_type) {}
  TypeDesc* element_type;
};

struct SequentialTypeDesc : TypeDesc {
  TypeDesc* get_contained_type() const { return contained_type; }
  size_t get_num_elems() const { return num_elems; }

 protected:
  SequentialTypeDesc(TypeDesc* contained_type, size_t num_elems)
      : contained_type(contained_type), num_elems(num_elems) {}

 private:
  size_t num_elems;
  TypeDesc* contained_type;
};

struct ArrayTypeDesc : SequentialTypeDesc {
  std::string get_signature() const {
    return "[" + std::to_string(get_num_elems()) + " x " + get_contained_type()->get_signature() +
           "]";
  }
  Discriminator get_discriminator() const { return ARRAY; }
  static ArrayTypeDesc* get(TypeDesc* element_type, size_t num_elems);

 private:
  ArrayTypeDesc(TypeDesc* contained_type, size_t num_elems)
      : SequentialTypeDesc::SequentialTypeDesc(contained_type, num_elems) {}
};

struct VectorTypeDesc : SequentialTypeDesc {
  std::string get_signature() const {
    return "<" + std::to_string(get_num_elems()) + " x " + get_contained_type()->get_signature() +
           ">";
  }
  Discriminator get_discriminator() const { return VECTOR; }
  static VectorTypeDesc* get(TypeDesc* contained_type, size_t num_elems);

 private:
  VectorTypeDesc(TypeDesc* contained_type, size_t num_elems)
      : SequentialTypeDesc::SequentialTypeDesc(contained_type, num_elems) {}
};

struct StructTypeDesc : TypeDesc {
  std::string get_signature() const {
    std::string sig;
    if (is_anonymous()) {
      sig += "{";
      for (int i = 0; i < get_num_elems(); ++i) {
        if (i > 0)
          sig += ", ";
        sig += elems[i]->get_signature();
      }
      sig += "}";
    } else {
      sig += "'" + module + "::" + name + "' ";
    }
    return sig;
  }
  Discriminator get_discriminator() const { return STRUCT; }
  std::optional<std::string> get_name() const {
    if (is_anonymous()) {
      return {};
    } else {
      return {name};
    }
  }
  size_t get_num_elems() const { return elems.size(); }
  TypeDesc* get_elem_type(size_t i) const { return elems[i]; }
  const std::vector<TypeDesc*> get_elem_types() const { return elems; }
  /**
   * Determine if this is currently a forward declaration - i.e. that the
   * element types have not been set.
   */
  bool is_forward() const { return forward; }
  /**
   * Determine if this is an anonymous struct.
   */
  bool is_anonymous() const { return name == ""; }
  /**
   * Set the element types.
   * If the struct is forward, then set the element types.
   * Otherwise the new element types must match the old ones.
   */
  void set_elem_types(std::vector<TypeDesc*> elem_types) {
    if (is_forward()) {
      elems = elem_types;
      forward = false;
    } else {
      assert(elems == elem_types && "Cannot set element types to a different value");
    }
  }
  /**
   * Get an anonymous struct
   */
  static StructTypeDesc* get_anon(std::vector<TypeDesc*> elem_types);
  /**
   * Get the named struct.
   * If the struct already exists and is not forward, then the element types
   * must match. If the struct already exists and is forward, it will be defined
   * and no longer be forward.
   */
  static StructTypeDesc* get_named(std::string module, std::string name,
                                   std::vector<TypeDesc*> elem_types);
  /**
   * Get a forward declaration struct.
   */
  static StructTypeDesc* get_forward(std::string module, std::string name);

 private:
  StructTypeDesc(std::string module, std::string name, std::vector<TypeDesc*> elems, bool forward)
      : module(module), name(name), elems(elems), forward(forward) {}
  std::string module;
  std::string name;
  std::vector<TypeDesc*> elems;
  bool forward;
};

struct FnTypeDesc : TypeDesc {
  std::string get_signature() const {
    std::string sig = return_type->get_signature() + " (";
    for (int i = 0; i < get_num_args(); ++i) {
      if (i > 0)
        sig += ", ";
      sig += args[i]->get_signature();
    }
    sig += ")";
    return sig;
  }
  Discriminator get_discriminator() const { return FUNCTION; }
  TypeDesc* get_return_type() const { return return_type; }
  size_t get_num_args() const { return args.size(); }
  TypeDesc* get_arg_type(size_t i) const { return args[i]; }
  const std::vector<TypeDesc*> get_arg_types() const { return args; }
  static FnTypeDesc* get(TypeDesc* return_type, std::vector<TypeDesc*> arg_types);

 private:
  FnTypeDesc(TypeDesc* return_type, std::vector<TypeDesc*> args)
      : return_type(return_type), args(args) {}
  TypeDesc* return_type;
  std::vector<TypeDesc*> args;
};

inline TypeDesc::~TypeDesc() {
  if (ptr) {
    delete ptr;
  }
}

inline PointerTypeDesc* TypeDesc::get_ptr() { return PointerTypeDesc::get(this); }

inline PointerTypeDesc* PointerTypeDesc::get(TypeDesc* element_type) {
  assert(element_type);
  if (element_type->ptr == nullptr) {
    element_type->ptr = new PointerTypeDesc(element_type);
  }
  return element_type->ptr;
}
}  // namespace augmentum

#endif
