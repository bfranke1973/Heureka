/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <pybind11/embed.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include <cstdlib>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

#include "augmentum.h"

namespace py = pybind11;

namespace augmentum {
namespace python {
/**
 * This type will wrap Python side Listeners.
 */
struct __attribute__((visibility("hidden"))) PyListener : Listener {
  py::object py_object;
  PyListener(py::object py_object) : py_object(py_object) {}
  ~PyListener() { py_object.release().dec_ref(); }

  void on_extension_point_register(FnExtensionPoint& pt) override;
  void on_extension_point_unregister(FnExtensionPoint& pt) override;
};

struct Allocation {
  Allocation(size_t size) : address(reinterpret_cast<intptr_t>(new int8_t[size])) {}
  ~Allocation() { delete[] reinterpret_cast<int8_t*>(address); }
  intptr_t address;
};

// Some forward declarations of the functions that link the Python and C++ code.
namespace impl {
void extend_before(py::object py_pt, py::object py_advice, AdviceId id);
void extend_around(py::object py_pt, py::object py_advice, AdviceId id);
void extend_after(py::object py_pt, py::object py_advice, AdviceId id);
void remove(py::object py_pt, AdviceId id);
void call_previous(py::object py_pt, intptr_t handle, py::object ret_val, py::object args);
void add_listener(py::object py_pt);
py::object i32_type(std::string);
int32_t i32_get(intptr_t address);
void i32_set(intptr_t address, int32_t value);
}  // namespace impl

// Initialise the "augmentum.impl" Python module which links the Python and C++
// code.
PYBIND11_EMBEDDED_MODULE(augmentum, m) {
  auto impl = m.def_submodule("impl");
  impl.def("get_unique_advice_id",
           get_unique_advice_id)  // Note this one is already in the augmentum
                                  // namespace
      .def("extend_before", impl::extend_before)
      .def("extend_around", impl::extend_around)
      .def("extend_after", impl::extend_after)
      .def("remove", impl::remove)
      .def("call_previous", impl::call_previous)
      .def("add_listener", impl::add_listener)
      .def("i32_type", impl::i32_type)
      .def("i32_get", impl::i32_get)
      .def("i32_set", impl::i32_set);
  py::class_<Allocation>(impl, "Allocation")
      .def(py::init<size_t>())
      .def_readonly("address", &Allocation::address);
}
/**
 * This is the class that manages the Python lifecycle.
 * It looks for a module name to be passed in (from an envionment variable).
 * If there is a module, it runs it.
 */
struct __attribute__((visibility("hidden"))) PythonMain {
  /**
   * This script is the Python side for the augmentum objects
   */
  std::string augmentum_script =
#include "augmentum.input"

      /**
       * The module to hold code from augmentum_script
       */
      std::unique_ptr<py::module_> py_augmentum;
  /**
   * The user's module
   */
  std::unique_ptr<py::module_> py_user_module;

  /**
   * Map from type signatures to the Python objects representing the TypeDescs
   */
  std::unordered_map<std::string, py::object> py_type_descs;
  /**
   * Map from name to the Python objects representing the FnExtensionPoints
   */
  std::unordered_map<std::string, py::object> py_fn_extension_points;
  /**
   * PyListeners
   */
  std::vector<PyListener> listeners;

  /**
   * The Python class object for TypeDesc
   */
  py::object py_TypeDesc;
  /**
   * The Python class object for UnknownTypeDesc
   */
  py::object py_UnknownTypeDesc;
  /**
   * The Python class object for FnTypeDesc
   */
  py::object py_FnTypeDesc;
  /**
   * The Python class object for VoidTypeDesc
   */
  py::object py_VoidTypeDesc;
  /**
   * The Python class object for FnExtensionPoints
   */
  py::object py_FnExtensionPoint;

  py::object py_Value;
  py::object py_I32;

  /**
   * Flag to indicate if the user decided to extend with Python so we can clear
   * up later.
   */
  bool added = false;

  /**
   * Initialise with the module name of the user's code.
   */
  PythonMain(const char* module_name) {
    if (module_name) {
      added = true;
      // Init the interpreter
      py::initialize_interpreter();

      // Get the augmentum script.
      // First make a module
      py_augmentum = std::make_unique<py::module_>(py::module_::import("augmentum"));
      // Then execute the script inside of it
      py::exec(augmentum_script,
               py::reinterpret_borrow<py::dict>(py_augmentum->attr("__dict__").ptr()));

      // Get the main classes from the augmentum module.
      py_TypeDesc = py_augmentum->attr("TypeDesc");
      py_UnknownTypeDesc = py_augmentum->attr("UnknownTypeDesc");
      py_FnTypeDesc = py_augmentum->attr("FnTypeDesc");
      py_VoidTypeDesc = py_augmentum->attr("VoidTypeDesc");
      py_FnExtensionPoint = py_augmentum->attr("FnExtensionPoint");
      py_Value = py_augmentum->attr("Value");
      py_I32 = py_augmentum->attr("I32");

      // Import the user's module.
      py_user_module = std::make_unique<py::module_>(py::module_::import(module_name));
    }
  }
  /**
   * Clean up
   */
  ~PythonMain() {
    if (added) {
      listeners.clear();
      // Release the FnExtensionPoint objects we've been holding
      for (auto& [k, v] : py_fn_extension_points) {
        v.release().dec_ref();
      }
      py_fn_extension_points.clear();
      // Release the type objects we've been holding
      for (auto& [k, v] : py_type_descs) {
        v.release().dec_ref();
      }
      py_type_descs.clear();
      // Release the class objects we've been holding
      py_I32.release().dec_ref();
      py_Value.release().dec_ref();
      py_FnExtensionPoint.release().dec_ref();
      py_VoidTypeDesc.release().dec_ref();
      py_FnTypeDesc.release().dec_ref();
      py_UnknownTypeDesc.release().dec_ref();
      py_TypeDesc.release().dec_ref();
      // Release the modules
      py_user_module.release();
      py_augmentum.release();
      // Finalise the interpreter
      py::finalize_interpreter();
    }
  }

  /**
   * Get the Python object for a TypeDesc.
   * We create them on demand and remember them until clean up.
   */
  py::object get_py_type(const TypeDesc* type_desc) {
    // py_type_descs is keyed on signature
    std::string sig = type_desc->get_signature();
    std::string& key = sig;
    auto it = py_type_descs.find(key);
    if (it == py_type_descs.end()) {
      // Do something different depending on the type.
      switch (type_desc->get_discriminator()) {
        // TODO implement missing types
        case TypeDesc::FLOAT:
        case TypeDesc::POINTER:
        case TypeDesc::STRUCT:
        case TypeDesc::ARRAY:
        case TypeDesc::VECTOR:
        case TypeDesc::UNKNOWN: {
          // Just create from the signature for now.
          py_type_descs[key] = py_UnknownTypeDesc(sig);
        } break;
        case TypeDesc::VOID: {
          py_type_descs[key] = py_VoidTypeDesc();
        } break;
        case TypeDesc::FUNCTION: {
          // Creat the function type
          const FnTypeDesc* fn_type_desc = reinterpret_cast<const FnTypeDesc*>(type_desc);
          std::vector<py::object> py_arg_types;
          for (auto arg_type : fn_type_desc->get_arg_types()) {
            py_arg_types.push_back(get_py_type(arg_type));
          }
          py_type_descs[key] =
              py_FnTypeDesc(sig, get_py_type(fn_type_desc->get_return_type()), py_arg_types);
        } break;
        case TypeDesc::INT: {
          if (sig != "int32") {
            std::cerr << "WARNING: int only implemented for 32 bits but used for: " << key
                      << std::endl;
            // Just create from the signature for now.
            py_type_descs[key] = py_UnknownTypeDesc(sig);
          } else {
            py_type_descs[key] = py_I32();
          }
        } break;
        default:
          std::cerr << "WARNING: unhandled type: " << type_desc->get_discriminator() << std::endl;
          break;
      }
    }
    return py_type_descs[key];
  }

  py::object get_py_fn_extension_point(const FnExtensionPoint& pt) {
    std::string module_name = pt.get_module_name();
    std::string name = pt.get_name();
    std::string key = module_name + "::" + name;
    auto it = py_fn_extension_points.find(key);
    if (it == py_fn_extension_points.end()) {
      auto type = get_py_type(&pt.get_type());
      py_fn_extension_points[key] = py_FnExtensionPoint(module_name, name, type);
    }
    return py_fn_extension_points[key];
  }

  py::object value_to_py(void* val, const TypeDesc* type) {
    intptr_t ptr = reinterpret_cast<intptr_t>(val);
    // Not a great implementation right now.
    if (type->get_signature() == "int32") {
      return py_I32(nullptr, ptr);
    } else {
      throw "Unknown value type.";
    }
  }
  std::vector<py::object> args_to_py(void** args, const FnExtensionPoint& pt) {
    std::vector<py::object> py;
    for (int i = 0; i < pt.get_num_args(); ++i) {
      py.push_back(value_to_py(args[i], pt.get_arg_type(i)));
    }
    return py;
  }
};
/**
 * The main Python control
 */
PythonMain python_main(std::getenv("AUGMENTUM_PYTHON"));

// Implementation of PyListener functions
void PyListener::on_extension_point_register(FnExtensionPoint& pt) {
  auto py_pt = python_main.get_py_fn_extension_point(pt);
  py_object.attr("on_extension_point_register")(py_pt);
}
void PyListener::on_extension_point_unregister(FnExtensionPoint& pt) {
  auto py_pt = python_main.get_py_fn_extension_point(pt);
  py_object.attr("on_extension_point_unregister")(py_pt);
}

// Definition of the impl functions
namespace impl {
FnExtensionPoint* get_pt(py::object py_pt) {
  auto module_name = py_pt.attr("_module_name").cast<std::string>();
  auto name = py_pt.attr("_name").cast<std::string>();
  auto pt = FnExtensionPoint::get(module_name, name);
  assert(pt);
  return pt;
}

void extend_before(py::object py_pt, py::object py_advice, AdviceId id) {
  // Really not sure about this, I think I should put these things into a
  // table somewhere for later deletion.
  auto& pt = *get_pt(py_pt);
  auto advice = [py_advice, py_pt](FnExtensionPoint& pt, ArgVals arg_vals) {
    auto args = python_main.args_to_py(arg_vals, pt);
    py_advice(py_pt, args);
  };
  pt.extend_before(advice, id);
}

void extend_around(py::object py_pt, py::object py_advice, AdviceId id) {
  auto& pt = *get_pt(py_pt);
  auto advice = [py_advice, py_pt](FnExtensionPoint& pt, AroundHandle handle, RetVal ret_val,
                                   ArgVals arg_vals) {
    auto h = reinterpret_cast<intptr_t>(handle);
    auto ret = python_main.value_to_py(ret_val, pt.get_return_type());
    auto args = python_main.args_to_py(arg_vals, pt);
    py_advice(py_pt, h, ret, args);
  };
  pt.extend_around(advice, id);
}

void extend_after(py::object py_pt, py::object py_advice, AdviceId id) {
  auto& pt = *get_pt(py_pt);
  auto advice = [py_advice, py_pt](FnExtensionPoint& pt, RetVal ret_val, ArgVals arg_vals) {
    auto ret = python_main.value_to_py(ret_val, pt.get_return_type());
    auto args = python_main.args_to_py(arg_vals, pt);
    py_advice(py_pt, ret, args);
  };
  pt.extend_after(advice, id);
}

void remove(py::object py_pt, AdviceId id) {
  auto& pt = *get_pt(py_pt);
  pt.remove(id);
}

void call_previous(py::object py_pt, intptr_t py_handle, py::object ret_val, py::object arg_vals) {
  auto& pt = *get_pt(py_pt);
  auto handle = reinterpret_cast<AroundHandle>(py_handle);
  auto ret = reinterpret_cast<void*>(ret_val.attr("_address").cast<intptr_t>());
  auto py_args = arg_vals.cast<std::vector<py::object>>();
  int num_args = pt.get_num_args();
  if (py_args.size() != num_args) {
    throw "Bad Juju!";
  }
  void* args[num_args];
  for (int i = 0; i < num_args; i++) {
    args[i] = reinterpret_cast<void*>(py_args[i].attr("_address").cast<intptr_t>());
  }
  pt.call_previous(handle, ret, args);
}

/**
 * Add a listener
 */
void add_listener(py::object pt) {
  // Wrap the Python side object
  PyListener& listener = python_main.listeners.emplace_back(pt);
  listener.add();
}

py::object i32_type(std::string sig) {
  // FIXME - this isn't good. What if the type hasn't been created yet.
  // The type system is already due an overhaul, so I'll leave this for
  // the moment.
  return python_main.py_type_descs[sig];
}
int32_t i32_get(intptr_t address) {
  int32_t* p = reinterpret_cast<int32_t*>(address);
  return *p;
}
void i32_set(intptr_t address, int32_t value) {
  int32_t* p = reinterpret_cast<int32_t*>(address);
  *p = value;
}
}  // namespace impl
}  // namespace python
}  // namespace augmentum
