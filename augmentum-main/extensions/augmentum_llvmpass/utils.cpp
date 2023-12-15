/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "utils.h"

#include <cxxabi.h>

#include <string>

#include "llvm/IR/Function.h"
#include "llvm/IR/Type.h"
#include "llvm/Support/raw_ostream.h"

using namespace llvm;

namespace augmentum {
namespace llvmpass {
std::string type_to_string(const Type* type) {
  std::string string;
  llvm::raw_string_ostream rso(string);
  type->print(rso);
  return rso.str();
}

std::string demangle(const std::string& funName) {
  int status;
  std::unique_ptr<char> funName_demangle{abi::__cxa_demangle(funName.c_str(), 0, 0, &status)};
  if (!status && funName_demangle) {
    std::string name_dem(funName_demangle.get());
    return name_dem;
  } else {
    return "NA";
  }
}

size_t count_instructions(const Function& function) {
  size_t instCount = 0;
  for (const BasicBlock& bb : function) {
    instCount += bb.size();
  }
  return instCount;
}

void print_attribute_list(llvm::raw_ostream& O, const llvm::AttributeList& attrs) {
  O << "AttributeList[\n";

  for (unsigned i = attrs.index_begin(), e = attrs.index_end(); i != e; ++i) {
    if (!attrs.getAttributes(i).hasAttributes())
      continue;
    O << "  { ";
    switch (i) {
      case AttributeList::AttrIndex::ReturnIndex:
        O << "return";
        break;
      case AttributeList::AttrIndex::FunctionIndex:
        O << "function";
        break;
      default:
        O << "arg(" << i - AttributeList::AttrIndex::FirstArgIndex << ")";
    }
    O << " => " << attrs.getAsString(i) << " }\n";
  }

  O << "]\n";
}
}  // namespace llvmpass
}  // namespace augmentum
