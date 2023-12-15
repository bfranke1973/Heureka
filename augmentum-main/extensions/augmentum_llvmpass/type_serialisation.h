/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#ifndef __AUGMENTUM_TYPE_SERIALISATION__
#define __AUGMENTUM_TYPE_SERIALISATION__

#include <string>
#include <unordered_map>

#include "llvm/ADT/iterator_range.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Type.h"

using namespace llvm;

// use this to hash Type* and SerialisationContext keys in type cache
template <typename A, typename B>
struct std::hash<std::pair<A, B>> {
  size_t operator()(const std::pair<A, B>& p) const {
    size_t h1 = hash<A>()(p.first);
    size_t h2 = hash<B>()(p.second);
    return h1 ^ (h2 << 1);
  }
};

namespace augmentum {
namespace llvmpass {
/**
 * This id is used to indicate a reason for the
 * instrumentation decision.
 */
enum SerialisationContext {
  NA,
  FUNCTION,  // the root function of the type tree
  BYVAL_ARG  // the type belongs to a function argument with byval parameter
};

/**
 * Encapsulates functionality for serialising functions and
 * corresponding types.
 */
struct TypeSerialiser {
 public:
  TypeSerialiser() : type_lookup(), named_structs_lookup() {}

  /**
   * Generate the string serialisation of a given llvm type.
   * Serialised types are cached and named structs are saved in a separate data
   * structure.
   */
  std::string serialise_type(const Module& module, const Function& function, Type* type,
                             SerialisationContext ctx = NA);

  /**
   * Constant range over cached named structs.
   */
  iterator_range<
      std::unordered_map<std::string, std::pair<std::string, StructType*>>::const_iterator>
  named_structs() const {
    return make_range(named_structs_lookup.begin(), named_structs_lookup.end());
  }

 private:
  /**
   * Cache serialised types.
   */
  std::unordered_map<std::pair<Type*, SerialisationContext>, std::string> type_lookup;

  /**
   * Cache for named struct serialisations. type_lookup only references the name
   * itself as serialisation while named_structs_lookup has the actual elements.
   */
  std::unordered_map<std::string, std::pair<std::string, StructType*>> named_structs_lookup;
};
}  // namespace llvmpass
}  // namespace augmentum

#endif
