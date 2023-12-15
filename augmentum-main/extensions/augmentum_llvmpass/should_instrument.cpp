/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "should_instrument.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

#include "llvm/Support/raw_ostream.h"

using namespace llvm;
using namespace std;

namespace augmentum {
namespace llvmpass {

void rstrip(string& s) {
  if (!s.empty() && s[s.size() - 1] == '\r') {
    s.erase(s.size() - 1);
  }
}

void TargetedInstrument::parse_targets(filesystem::path target_spec) {
  if (filesystem::exists(target_spec)) {
    ifstream in(target_spec.c_str(), ios::in);
    if (in.good()) {
      bool header = true;
      std::string line;
      while (std::getline(in, line)) {
        if (header) {
          header = false;
          continue;
        }

        rstrip(line);

        auto process_token = [this](int tid, string token) {
          if (tid == 0)
            target_modules.insert(token);
          else if (tid == 1)
            target_functions.insert(token);
        };

        size_t start = 0;
        size_t pos = 0;
        string token;
        int token_id = 0;
        while ((pos = line.find(delimiter, start)) != string::npos) {
          token = line.substr(start, pos - start);
          process_token(token_id++, token);
          start = pos + delimiter.length();
        }

        // get the last one
        token = line.substr(start);
        process_token(token_id, token);
      }

    } else {
      errs() << "ERROR: [Augmentum] opening input stream to read target "
                "functions failed."
                " Path invalid: "
             << target_spec << "\n";
    }
    in.close();

  } else {
    errs() << "WARNING: [Augmentum] Specified target function file not found: " << target_spec
           << "\n";
  }
}
}  // namespace llvmpass
}  // namespace augmentum
