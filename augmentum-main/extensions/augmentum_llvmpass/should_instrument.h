/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#ifndef __AUGMENTUM__SHOULD_INSTRUMENT__
#define __AUGMENTUM__SHOULD_INSTRUMENT__

#include <filesystem>
#include <string>
#include <unordered_set>

#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "llvm/Support/raw_ostream.h"

using namespace llvm;

namespace augmentum {
namespace llvmpass {
/**
 * Call back class for determining whether to instrument modules and functions.
 */
struct ShouldInstrument {
  virtual ~ShouldInstrument() {}
  virtual bool module(Module& module) = 0;
  virtual bool function(Function& function) = 0;

  /**
   * Override this function to return information on the instrumentation
   * decision.
   */
  virtual std::string get_decision_info(Module& module, Function& function) { return "NA"; }
};

/**
 * Always instrument if possible.
 */
struct AlwaysInstrument : ShouldInstrument {
  virtual bool module(Module& module) { return true; }
  virtual bool function(Function& function) { return true; }
};

/**
 * Instrument for a given list of specified functions or modules.
 */
struct TargetedInstrument : ShouldInstrument {
  TargetedInstrument(std::string target_spec) : target_functions(), target_modules() {
    parse_targets(target_spec);
  }

  virtual bool module(Module& module) {
    return target_modules.find(module.getName().str()) != target_modules.end();
  }
  virtual bool function(Function& function) {
    return target_functions.find(function.getName().str()) != target_functions.end();
    ;
  }

 private:
  static const inline std::string delimiter = ";";

  // mangled names of target functions
  std::unordered_set<std::string> target_functions;
  // paths to target modules
  std::unordered_set<std::string> target_modules;

  /**
   * Parse target functions and modules from given file path
   * and populate lookups.
   */
  void parse_targets(std::filesystem::path target_spec);
};

std::unique_ptr<ShouldInstrument> get_python_should_instrument(std::string script);
}  // namespace llvmpass
}  // namespace augmentum
#endif
