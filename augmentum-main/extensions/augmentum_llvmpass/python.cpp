/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <pybind11/embed.h>

#include <iostream>
#include <string>

#include "llvm/Support/raw_ostream.h"
#include "should_instrument.h"
#include "utils.h"

namespace py = pybind11;

/**
 * Lots of LLVM types aren't copyable, and if the Python interpreter goes around
 * deleting them, bad things happen. So we wrap them in a smart pointer that
 * doesn't delete.
 */
namespace pybind11 {
namespace detail {
template <typename T>
struct NoDel {
  T* data;
  NoDel(T* data) : data(data) {}
  T* get() const { return data; }
};
}  // namespace detail
}  // namespace pybind11
PYBIND11_DECLARE_HOLDER_TYPE(T, NoDel<T>);

namespace augmentum {
namespace llvmpass {
using py::detail::NoDel;
// Python bindings for types
PYBIND11_EMBEDDED_MODULE(llvm, m) {
  py::class_<Module, NoDel<Module>>(m, "Module")
      .def("get_name", [](const Module& module) { return module.getName().str(); })
      .def("__repr__", [](const Module& module) {
        return "<llvm.Module named '" + module.getName().str() + "'>";
      });
  py::class_<Function, NoDel<Function>>(m, "Function")
      .def("get_name", [](const Function& function) { return function.getName().str(); })
      .def("get_instruction_count", &Function::getInstructionCount)
      .def("get_parent", [](const Function& function) { return function.getParent(); })
      .def("__repr__",
           [](const Function& function) {
             const Module* mod = function.getParent();
             auto mod_name = mod ? mod->getName().str() : "[none]";
             return "<llvm.Function named '" + function.getName().str() + "' in module '" +
                    mod_name + "'>";
           })
      .def("get_signature", [](const Function& function) {
        auto fType = function.getFunctionType();
        return type_to_string(fType);
      });
  // py::class_<Type, NoDel<Type>>(m, "Type")
  //.de
}

// Callbacks from C++
// VS: The visibility attribute fixes a visibility warning where
// ShouldInstrument had lower visibility in the final library than
// PythonShouldInstrument see here:
// https://stackoverflow.com/questions/2828738/c-warning-declared-with-greater-visibility-than-the-type-of-its-field
struct __attribute__((visibility("hidden"))) PythonShouldInstrument : ShouldInstrument {
  static constexpr auto module_attr_name = "should_instrument_module";
  static constexpr auto function_attr_name = "should_instrument_function";

  std::unique_ptr<py::module_> py_llvm;
  std::unique_ptr<py::module_> py_script;
  PythonShouldInstrument(std::string script) {
    py::initialize_interpreter();
    py_llvm = std::make_unique<py::module_>(py::module_::import("llvm"));
    py_script = std::make_unique<py::module_>(py::module_::import(script.c_str()));
  }
  ~PythonShouldInstrument() {
    py_script.release();
    py_llvm.release();
    py::finalize_interpreter();
  }
  bool module(Module& mod) {
    if (py::hasattr(*py_script, module_attr_name)) {
      py::object pyfun = py_script->attr(module_attr_name);
      py::object pybool = pyfun(&mod);
      bool val = pybool.cast<bool>();
      return val;
    } else {
      return true;
    }
  }
  bool function(Function& fun) {
    if (py::hasattr(*py_script, function_attr_name)) {
      py::object pyfun = py_script->attr(function_attr_name);
      py::object pybool = pyfun(&fun);
      bool val = pybool.cast<bool>();
      return val;
    } else {
      return true;
    }
  }
};

std::unique_ptr<ShouldInstrument> get_python_should_instrument(std::string script) {
  return std::make_unique<PythonShouldInstrument>(script);
}

}  // namespace llvmpass
}  // namespace augmentum
