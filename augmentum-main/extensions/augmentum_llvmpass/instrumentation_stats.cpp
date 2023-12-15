/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "instrumentation_stats.h"

#include <filesystem>
#include <fstream>
#include <string>
#include <unordered_map>

#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Type.h"
#include "llvm/Support/raw_ostream.h"
#include "utils.h"

using namespace llvm;
using namespace std;

namespace augmentum {
namespace llvmpass {

static const string fun_stats_out_file_name = "function_stats.csv";
static const string named_struct_out_file_name = "named_struct_stats.csv";

static const string stats_out_delim = ";";
static const string stats_out_arg_type_delim = "#";
static const string fun_stats_out_head =
    "MODULE" + stats_out_delim + "FNAME" + stats_out_delim + "FNAMED" + stats_out_delim + "ICOUNT" +
    stats_out_delim + "PCOUNT" + stats_out_delim + "FUNCTIONTY" + stats_out_delim + "CAN_INSTR" +
    stats_out_delim + "SHOULD_INSTR";
static const string named_struct_stats_out_head = "MODULE" + stats_out_delim + "STRUCT_NAME" +
                                                  stats_out_delim + "TYPE" + stats_out_delim +
                                                  "LLVM_NAME" + stats_out_delim + "EXTRA";

void InstrumentationStats::record_function_stats(
    const Module& module, const Function& function,
    const std::pair<std::string, std::string>& instr_info) {
  string fname = function.getName().str();
  if (function_statistics.find(fname) == function_statistics.end()) {
    if (full_stats) {
      vector<Type*> arg_types;
      for (auto& arg : function.args()) {
        arg_types.push_back(arg.getType());
      }

      FunctionData data{module.getName().str(),
                        fname,
                        demangle(fname),
                        static_cast<int>(count_instructions(function)),
                        static_cast<int>(function.arg_size()),
                        type_serialiser.serialise_type(module, function, function.getFunctionType(),
                                                       SerialisationContext::FUNCTION),
                        instr_info.first,
                        instr_info.second};
      function_statistics[fname] = data;

    } else {
      FunctionData data{module.getName(), fname, "NA", -1, -1, "NA", instr_info.first,
                        instr_info.second};
      function_statistics[fname] = data;
    }
  }
}

void InstrumentationStats::record_named_struct_stats(const Module& module) {
  auto bool_to_string = [](bool b) -> std::string { return b ? "true" : "false"; };

  for (auto& [name, type] : type_serialiser.named_structs()) {
    if (named_struct_statistics.find(name) == named_struct_statistics.end()) {
      std::string serialised_type = type.first;
      StructType* stype = type.second;
      std::string extra = "named:" + bool_to_string(stype->hasName()) + "#" +
                          "packed:" + bool_to_string(stype->isPacked()) + "#" +
                          "literal:" + bool_to_string(stype->isLiteral()) + "#" +
                          "opaque:" + bool_to_string(stype->isOpaque());

      named_struct_statistics[name] = {module.getName().str(), stype->getName().str(),
                                       serialised_type, type_to_string(stype), extra};
    }
  }
}

static void print_path_error(std::filesystem::path p) {
  errs() << "ERROR: [Augmentum] opening output stream to emit statistics failed."
            " Path invalid: "
         << p << "\n";
}

static std::string escape_and_delim(std::string s, bool delim = true) {
  std::string res = "";
  for (auto c : s) {
    res += c == '\"' ? '\'' : c;
  }
  res = "\"" + res + "\"";
  return delim ? res + stats_out_delim : res;
}

static void emit_stats(filesystem::path outputFile, const std::string& header,
                       const std::function<void(std::ofstream&)>& write_stats) {
  ofstream out(outputFile.c_str(), ios::out | ios::app);
  if (out.good()) {
    // Do we need to write a header?
    if (out.tellp() == 0) {
      out << header << "\n";
    }
    write_stats(out);
  } else {
    print_path_error(outputFile);
  }
  out.close();
}

void InstrumentationStats::emit_statistics(const string& outDir, const string& prefix) const {
  filesystem::path errorPath = "";
  filesystem::path outDirP = outDir;

  if (filesystem::exists(outDirP)) {
    // write function statistics
    emit_stats(
        outDirP / (prefix + "_" + fun_stats_out_file_name), fun_stats_out_head,
        [this](std::ofstream& out) {
          for (auto& [fname, entry] : function_statistics) {
            out << escape_and_delim(entry.module_name) << escape_and_delim(entry.function_name)
                << escape_and_delim(entry.function_name_demangled)
                << escape_and_delim(
                       entry.instruction_count >= 0 ? to_string(entry.instruction_count) : "NA")
                << escape_and_delim(entry.parameter_count >= 0 ? to_string(entry.parameter_count)
                                                               : "NA")
                << escape_and_delim(entry.type_serialisation) << escape_and_delim(entry.can_instr)
                << escape_and_delim(entry.should_instr, false) << "\n";
          }
        });

    // write named struct type statistics
    emit_stats(outDirP / (prefix + "_" + named_struct_out_file_name), named_struct_stats_out_head,
               [this](std::ofstream& out) {
                 for (auto& [name, entry] : named_struct_statistics) {
                   out << escape_and_delim(entry.module_name) << escape_and_delim(entry.struct_name)
                       << escape_and_delim(entry.serialised_type)
                       << escape_and_delim(entry.llvm_name) << escape_and_delim(entry.extra, false)
                       << "\n";
                 }
               });

  } else {
    print_path_error(outDirP);
  }
}
}  // namespace llvmpass
}  // namespace augmentum
