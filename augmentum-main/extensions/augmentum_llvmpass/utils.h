/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#ifndef __AUGMENTUM_UTILS__
#define __AUGMENTUM_UTILS__

#include <string>

#include "llvm/IR/Function.h"
#include "llvm/IR/Type.h"
#include "llvm/Support/raw_ostream.h"

namespace augmentum {
namespace llvmpass {
/**
 * Utility function to get the name for an LLVM type.
 */
std::string type_to_string(const llvm::Type* type);

/**
 * Demangle given function name.
 *
 * Returns demangled function name as string or NA if unsuccessful.
 */
std::string demangle(const std::string& funName);

/**
 * Count instructions of a given function.
 */
size_t count_instructions(const llvm::Function& function);

/**
 * Print attributes from given list.
 */
void print_attribute_list(llvm::raw_ostream& O, const llvm::AttributeList& attrs);
}  // namespace llvmpass
}  // namespace augmentum

#endif
