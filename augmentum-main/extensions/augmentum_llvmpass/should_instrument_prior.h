/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#ifndef __AUGMENTUM__SHOULD_INSTRUMENT_PRIOR__
#define __AUGMENTUM__SHOULD_INSTRUMENT_PRIOR

#include <string>

#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "should_instrument.h"

namespace augmentum {
namespace llvmpass {

/**
 *  Should-instrument rules for the augmentum project.
 */
struct HeuristicDetector : ShouldInstrument {
  bool module(Module& module) { return module_decision(module).should_instrument; }
  bool function(Function& function) { return function_decision(function).should_instrument; }

  std::string get_decision_info(Module& module, Function& function) override {
    auto md = module_decision(module);
    if (md.should_instrument) {
      auto fd = function_decision(function);
      return fd.info;
    } else {
      return md.info;
    }
  }

 private:
  struct InstrDecision {
    bool should_instrument;
    std::string info;  // additional information for the decision
  };

  InstrDecision module_decision(Module& module);
  InstrDecision function_decision(Function& function);
};
}  // namespace llvmpass
}  // namespace augmentum

#endif
