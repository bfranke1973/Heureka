/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "should_instrument_prior.h"

#include <cxxabi.h>

#include <regex>
#include <string>
#include <unordered_set>
#include <vector>

#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "should_instrument.h"
#include "utils.h"

namespace augmentum {
namespace llvmpass {

static constexpr const char* function_name__main = "main";

static constexpr const char* instrumentation_decision__instrument = "instrument";
static constexpr const char* instrumentation_decision__not_module = "not_module";
static constexpr const char* instrumentation_decision__not_fun_main = "not_fun_main";
static constexpr const char* instrumentation_decision__not_fun_std = "not_fun_std";
static constexpr const char* instrumentation_decision__not_fun_c = "not_fun_c";
static constexpr const char* instrumentation_decision__not_fun_dtor = "not_fun_dtor";
static constexpr const char* instrumentation_decision__not_no_interesting_types =
    "not_no_interesting_types";
static constexpr const char* instrumentation_decision__not_readonly_function =
    "not_readonly_function";

/**
 * Types we are not interested in for this project
 */
static const inline std::unordered_set<std::string> type_deny_list{
    // TODO fill me up
};

/**
 * Types we are interested in for this project
 */
static const inline std::unordered_set<std::string> type_allow_list{
    // TODO fill me up
};

HeuristicDetector::InstrDecision HeuristicDetector::module_decision(Module& module) {
  return {true, instrumentation_decision__instrument};
}

// see spec for details
// https://itanium-cxx-abi.github.io/cxx-abi/abi.html#mangling
// TODO consider other gnu namespaces not just cxx
// https://gcc.gnu.org/onlinedocs/libstdc++/latest-doxygen/namespaces.html
// TODO consider abi namespace
static bool is_std_function(StringRef function_name) {
  return regex_search(function_name.str(), std::regex("^_Z+(St|NS|NKSt|NVKS|NVS|N9__gnu_cxx)"));
}

/**
 * Check of individual elements of the given struct are interesting.
 * For now only primitives are interesting.
 */
static bool has_interesting_element_types(StructType* stype) {
  bool interesting = false;
  for (int i = 0; i < stype->getNumElements(); ++i) {
    auto elem_type = stype->getElementType(i);
    interesting |= elem_type->isIntegerTy() || elem_type->isDoubleTy() || elem_type->isFloatTy();
  }
  return interesting;
}

/**
 * a return type is interesting if
 *  - it is not void
 *  - it is not a pointer to a pointer
 *  - its element type is not on our deny list
 *  - it is not a named struct
 *  - it is not a function pointer
 *  - is is not an array or vector type
 *
 * a parameter type is interesting if
 *  - it is a pointer
 *  - it is not a pointer to a pointer
 *  - it is not readonly
 *  - its element type is not on our deny list
 *  - it is not a named struct
 *  - it is not a function pointer
 *  - is is not an array or vector type
 *
 */
static bool is_interesting_type(LLVMContext& ctx, Type* type, bool is_return, bool is_readonly) {
  bool is_ptr = type->isPointerTy();
  bool is_ptr_ptr = false;
  Type* element_type = type;
  if (is_ptr) {  // if pointer, get element type
    element_type = cast<PointerType>(type)->getElementType();
    is_ptr_ptr = element_type->isPointerTy();
  }
  bool on_deny_list = type_deny_list.find(type_to_string(element_type)) != type_deny_list.end();
  bool on_allow_list = type_allow_list.find(type_to_string(element_type)) != type_allow_list.end();

  bool is_named_struct = element_type->isStructTy() && cast<StructType>(element_type)->hasName();
  bool is_not_interesting_unnamed = element_type->isStructTy() && !is_named_struct &&
                                    has_interesting_element_types(cast<StructType>(element_type));

  bool is_function = element_type->isFunctionTy();

  bool is_array_type = element_type->isArrayTy();
  bool is_vector_type = element_type->isVectorTy();

  if (is_return) {
    bool is_void = type == Type::getVoidTy(ctx);
    return on_allow_list || (!is_void && !is_ptr_ptr && !on_deny_list && !is_named_struct &&
                             !is_not_interesting_unnamed && !is_ptr && !is_function &&
                             !is_array_type && !is_vector_type);

  } else {
    return is_ptr && (on_allow_list || (!is_readonly && !is_ptr_ptr && !on_deny_list &&
                                        !is_named_struct && !is_not_interesting_unnamed &&
                                        !is_function && !is_array_type && !is_vector_type));
  }
}

/**
 * Check if any of the parameters or the return type are interesting for
 * prior evaluation.
 */
static bool has_interesting_types(const Function& function) {
  bool return_is_interesting =
      is_interesting_type(function.getContext(), function.getReturnType(), true, false);
  bool param_is_interesting = false;
  for (auto& arg : function.args()) {
    bool is_readonly = arg.hasAttribute(Attribute::ReadOnly);
    param_is_interesting |=
        is_interesting_type(function.getContext(), arg.getType(), false, is_readonly);
  }
  return return_is_interesting || param_is_interesting;
}

/**
 * if has void return type and function is readonly, we are not interested
 * according to LLVM spec such a function does not write out through its pointer
 * parameters
 */
static bool is_readonly_function(const Function& function) {
  return function.getReturnType() == Type::getVoidTy(function.getContext()) &&
         function.hasFnAttribute(Attribute::ReadOnly);
}

HeuristicDetector::InstrDecision HeuristicDetector::function_decision(Function& function) {
  // do not instrument main functions
  if (function.getName() == function_name__main) {
    return {false, instrumentation_decision__not_fun_main};
  }

  // do not instrument std namespace functions
  if (is_std_function(function.getName())) {
    return {false, instrumentation_decision__not_fun_std};
  }

  // do not instrument c functions
  // those are not mangled and therefore don't start with "_Z"
  //
  // TODO this is mainly to avoid c library functions but might be
  // a bit harsh for the entire LLVM project
  if (function.getName().str().rfind("_Z", 0) == std::string::npos) {
    return {false, instrumentation_decision__not_fun_c};
  }

  // do not instrument destructors
  if (std::regex_match(function.getName().str(), std::regex("(_ZN)(.*)(D[0,1,2]Ev)"))) {
    return {false, instrumentation_decision__not_fun_dtor};
  }

  if (!has_interesting_types(function)) {
    return {false, instrumentation_decision__not_no_interesting_types};
  }

  if (is_readonly_function(function)) {
    return {false, instrumentation_decision__not_readonly_function};
  }

  // instrument everything else
  return {true, instrumentation_decision__instrument};
}
}  // namespace llvmpass
}  // namespace augmentum
