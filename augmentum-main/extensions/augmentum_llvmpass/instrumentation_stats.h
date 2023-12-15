/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#ifndef __AUGMENTUM_INSTRUMENTATION_STATS__
#define __AUGMENTUM_INSTRUMENTATION_STATS__

#include <filesystem>
#include <fstream>
#include <string>
#include <unordered_map>

#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Type.h"
#include "llvm/Support/raw_ostream.h"
#include "type_serialisation.h"
#include "utils.h"

using namespace llvm;

namespace augmentum {
namespace llvmpass {
/**
 * Encapsulates functionality for collecting
 * statistics during instrumentation.
 */
struct InstrumentationStats {
 public:
  InstrumentationStats()
      : function_statistics(), named_struct_statistics(), type_serialiser(), full_stats(false) {}

  void collect_full_stats() { full_stats = true; }

  void collect_reduced_stats() { full_stats = false; }

  /**
   * Record function statistics.
   */
  void record_function_stats(
      const Module& module, const Function& function,
      const std::pair<std::string, std::string>& instr_info = instrumentation_info_NA);

  /**
   * Record names struct statistics.
   */
  void record_named_struct_stats(const Module& module);

  /**
   * Append name of module and functions instrumented in this
   * module to specified output file.
   */
  void emit_statistics(const std::string& outDir, const std::string& prefix) const;

 private:
  static const inline std::pair<std::string, std::string> instrumentation_info_NA = {"NA", "NA"};

  /**
   * Encapsulate statistics on a function in the module and
   * its transformation.
   */
  struct FunctionData {
    std::string module_name;
    std::string function_name;
    std::string function_name_demangled;
    int instruction_count;  // before instrumentation
    int parameter_count;
    std::string type_serialisation;
    std::string can_instr;
    std::string should_instr;
  };

  /**
   * Encapsulate statistics for named structs in the module.
   */
  struct NamedStructData {
    std::string module_name;
    std::string struct_name;
    std::string serialised_type;
    std::string llvm_name;
    std::string extra;
  };

  /**
   * Cache statistics on functions in the module and their transformations.
   */
  std::unordered_map<std::string, FunctionData> function_statistics;

  /**
   * Stastistics for named structs.
   */
  std::unordered_map<std::string, NamedStructData> named_struct_statistics;

  /**
   * Use this for serialising types and caching serialisations.
   */
  TypeSerialiser type_serialiser;

  bool full_stats;
};
}  // namespace llvmpass
}  // namespace augmentum

#endif
