/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <functional>
#include <iostream>

#include "augmentum.h"
#include "to-instrument.h"

#define VERBOSE_REGISTRATION
#ifdef VERBOSE_REGISTRATION
#define REG_LOG(msg) std::cout << msg << std::endl;
#else
#define REG_LOG(msg)
#endif

using namespace augmentum;

struct AddOneListener : Listener {
  AroundAdvice add_one = [this](FnExtensionPoint& pt, AroundHandle handle, RetVal ret_value,
                                ArgVals arg_values) {
    std::cout << "AddOne Advice call ..." << std::endl;

    pt.call_previous(handle, ret_value, arg_values);

    const TypeDesc* type = pt.get_return_type();
    if (type == IntTypeDesc::get_i1()) {
      bool* r = reinterpret_cast<bool*>(ret_value);
      *r *= -1;
    } else if (type == IntTypeDesc::get_i8()) {
      char* r = reinterpret_cast<char*>(ret_value);
      *r += 1;
    } else if (type == IntTypeDesc::get_i16()) {
      short* r = reinterpret_cast<short*>(ret_value);
      *r += 1;
    } else if (type == IntTypeDesc::get_i32()) {
      int* r = reinterpret_cast<int*>(ret_value);
      *r += 1;
    } else if (type == IntTypeDesc::get_i64()) {
      long* r = reinterpret_cast<long*>(ret_value);
      *r += 1;
    } else if (type == FloatTypeDesc::get_float()) {
      float* r = reinterpret_cast<float*>(ret_value);
      *r += 1.0;
    } else if (type == FloatTypeDesc::get_double()) {
      double* r = reinterpret_cast<double*>(ret_value);
      *r += 1.0;
    } else {
      std::cerr << "ERROR: extended for invalid type: " << std::string(*type) << std::endl;
    }
  };

  void on_extension_point_register(FnExtensionPoint& pt) {
    if (pt.get_return_type()->get_discriminator() == TypeDesc::INT ||
        pt.get_return_type()->get_discriminator() == TypeDesc::FLOAT) {
      REG_LOG("AddOneListener extending " << pt.get_name() << " " << pt.get_signature());

      pt.extend_around(add_one, id);
    }
  }
  void on_extension_point_unregister(FnExtensionPoint& pt) {
    REG_LOG("AddOneListener unextending " << pt.get_name() << " " << pt.get_signature());

    pt.remove_around(id);
  }

  AdviceId id = get_unique_advice_id();
};
ListenerLifeCycle<AddOneListener> addOneListener;
ListenerLifeCycle<AddOneListener> addAnotherListener;

struct AddOnePointerListener : Listener {
  AroundAdvice add_one = [this](FnExtensionPoint& pt, AroundHandle handle, RetVal ret_value,
                                ArgVals arg_values) {
    std::cout << "AddOnePointer Advice call ..." << std::endl;

    pt.call_previous(handle, ret_value, arg_values);

    const TypeDesc* type =
        reinterpret_cast<const PointerTypeDesc*>(pt.get_return_type())->get_element_type();
    if (type->get_discriminator() == TypeDesc::INT) {
      long** r = reinterpret_cast<long**>(ret_value);
      **r += 1;
    } else if (type->get_discriminator() == TypeDesc::FLOAT) {
      double** r = reinterpret_cast<double**>(ret_value);
      **r += 1.0;
    } else {
      std::cerr << "ERROR: extended for invalid type: " << std::string(*type) << std::endl;
    }
  };

  void on_extension_point_register(FnExtensionPoint& pt) {
    if (pt.get_return_type()->get_discriminator() == TypeDesc::POINTER) {
      const TypeDesc* elem_type =
          reinterpret_cast<const PointerTypeDesc*>(pt.get_return_type())->get_element_type();

      if (elem_type->get_discriminator() == TypeDesc::INT ||
          elem_type->get_discriminator() == TypeDesc::FLOAT) {
        REG_LOG("AddOnePointerListener extending " << pt.get_name() << " " << pt.get_signature());

        pt.extend_around(add_one, id);
      }
    }
  }
  void on_extension_point_unregister(FnExtensionPoint& pt) {
    REG_LOG("AddOnePointerListener unextending " << pt.get_name() << " " << pt.get_signature());

    pt.remove_around(id);
  }

  AdviceId id = get_unique_advice_id();
};
ListenerLifeCycle<AddOnePointerListener> addOnePointerListener;

struct AddOneFirstParameterListener : Listener {
  AroundAdvice add_one = [this](FnExtensionPoint& pt, AroundHandle handle, RetVal ret_value,
                                ArgVals arg_values) {
    std::cout << "AddOneFirstParameter Advice call ..." << std::endl;

    pt.call_previous(handle, ret_value, arg_values);

    long** r = reinterpret_cast<long**>(arg_values[0]);
    **r += 1;
  };

  void on_extension_point_register(FnExtensionPoint& pt) {
    // has at least one arg which is a pointer
    if (pt.get_num_args() >= 1 && pt.get_arg_type(0)->get_discriminator() == TypeDesc::POINTER) {
      const TypeDesc* elem_type =
          reinterpret_cast<const PointerTypeDesc*>(pt.get_arg_type(0))->get_element_type();
      // first arg is pointer to integer type
      if (elem_type->get_discriminator() == TypeDesc::INT) {
        REG_LOG("AddOneFirstParameterListener extending " << pt.get_name() << " "
                                                          << pt.get_signature());
        pt.extend_around(add_one, id);
      }
    }
  }
  void on_extension_point_unregister(FnExtensionPoint& pt) {
    REG_LOG("AddOneFirstParameterListener unextending " << pt.get_name() << " "
                                                        << pt.get_signature());

    pt.remove_around(id);
  }

  AdviceId id = get_unique_advice_id();
};
ListenerLifeCycle<AddOneFirstParameterListener> addOneFirstParameterListener;

struct AddOneStructListener : Listener {
  AroundAdvice add_one = [this](FnExtensionPoint& pt, AroundHandle handle, RetVal ret_value,
                                ArgVals arg_values) {
    std::cout << "AddOneStruct Advice call ..." << std::endl;

    pt.call_previous(handle, ret_value, arg_values);

    Result* r = reinterpret_cast<Result*>(ret_value);
    r->resl += 1;
  };

  void on_extension_point_register(FnExtensionPoint& pt) {
    // is struct type
    if (pt.get_return_type()->get_discriminator() == TypeDesc::STRUCT) {
      const StructTypeDesc* struct_type =
          reinterpret_cast<const StructTypeDesc*>(pt.get_return_type());

      // first member in struct is integet type
      if (struct_type->get_num_elems() >= 1 &&
          struct_type->get_elem_type(0)->get_discriminator() == TypeDesc::INT) {
        REG_LOG("AddOneStructListener extending " << pt.get_name() << " " << pt.get_signature());

        pt.extend_around(add_one, id);
      }
    }
  }
  void on_extension_point_unregister(FnExtensionPoint& pt) {
    REG_LOG("AddOneStructListener unextending " << pt.get_name() << " " << pt.get_signature());

    pt.remove_around(id);
  }

  AdviceId id = get_unique_advice_id();
};
ListenerLifeCycle<AddOneStructListener> addOneStructListener;

struct AddOneNamedStructListener : Listener {
  AroundAdvice add_one = [this](FnExtensionPoint& pt, AroundHandle handle, RetVal ret_value,
                                ArgVals arg_values) {
    std::cout << "AddOneNamedStruct Advice call ..." << std::endl;

    pt.call_previous(handle, ret_value, arg_values);

    Node** r = reinterpret_cast<Node**>(ret_value);
    (*r)->data += 1;
  };

  void on_extension_point_register(FnExtensionPoint& pt) {
    // is struct type
    auto return_type = pt.get_return_type();
    if (return_type->get_discriminator() == TypeDesc::POINTER &&
        reinterpret_cast<const PointerTypeDesc*>(return_type)
                ->get_element_type()
                ->get_discriminator() == TypeDesc::STRUCT) {
      const StructTypeDesc* struct_type = reinterpret_cast<const StructTypeDesc*>(
          reinterpret_cast<const PointerTypeDesc*>(return_type)->get_element_type());

      // first member in struct is integet type
      if (struct_type->get_num_elems() >= 1 &&
          struct_type->get_elem_type(0)->get_discriminator() == TypeDesc::INT) {
        REG_LOG("AddOneNamedStructListener extending " << pt.get_name() << " "
                                                       << pt.get_signature());

        pt.extend_around(add_one, id);
      }
    }
  }
  void on_extension_point_unregister(FnExtensionPoint& pt) {
    REG_LOG("AddOneNamedStructListener unextending " << pt.get_name() << " " << pt.get_signature());

    pt.remove_around(id);
  }

  AdviceId id = get_unique_advice_id();
};
ListenerLifeCycle<AddOneNamedStructListener> addOneNamedStructListener;

struct AddOneArrayStructListener : Listener {
  AroundAdvice add_one = [this](FnExtensionPoint& pt, AroundHandle handle, RetVal ret_value,
                                ArgVals arg_values) {
    std::cout << "AddOneArrayStruct Advice call ..." << std::endl;

    Container** c = reinterpret_cast<Container**>(arg_values[0]);
    (*c)->factor += 1;

    pt.call_previous(handle, ret_value, arg_values);
  };

  void on_extension_point_register(FnExtensionPoint& pt) {
    if (pt.get_name() == "_Z13arrayTypeTestP9Container") {
      REG_LOG("AddOneArrayStructListener extending " << pt.get_name() << " " << pt.get_signature());
      pt.extend_around(add_one, id);
    }
  }
  void on_extension_point_unregister(FnExtensionPoint& pt) {
    REG_LOG("AddOneArrayStructListener unextending " << pt.get_name() << " " << pt.get_signature());

    pt.remove_around(id);
  }

  AdviceId id = get_unique_advice_id();
};
ListenerLifeCycle<AddOneArrayStructListener> addOneArrayStructListener;

struct PrintListener : Listener {
  void before(FnExtensionPoint& pt, ArgVals arg_values) {
    std::cout << "Entering " << pt.get_name() << ":[" << pt.get_signature() << "](";
    for (int i = 0; i < pt.get_num_args(); ++i) {
      auto type = pt.get_arg_type(i);
      if (i > 0)
        std::cout << ", ";
      // TODO update this
      if (type == IntTypeDesc::get_i32()) {
        std::cout << *(int*)arg_values[i];
      } else {
        std::cout << "-";
      }
    }
    std::cout << ")\n";
  }
  void after(FnExtensionPoint& pt, RetVal ret_value, ArgVals arg_values) {
    std::cout << "Exiting " << pt.get_name() << ":[" << pt.get_signature() << "](";
    for (int i = 0; i < pt.get_num_args(); ++i) {
      auto type = pt.get_arg_type(i);
      if (i > 0)
        std::cout << ", ";
      // TODO update this
      if (type == IntTypeDesc::get_i32()) {
        std::cout << *(int*)arg_values[i];
      } else {
        std::cout << "-";
      }
    }
    std::cout << ") = ";
    auto type = pt.get_return_type();
    // TODO update this
    if (type == IntTypeDesc::get_i32()) {
      std::cout << *(int*)ret_value;
    } else {
      std::cout << "-";
    }
    std::cout << '\n';
  }

  void on_extension_point_register(FnExtensionPoint& pt) {
    REG_LOG("PrintListener extending " << pt.get_name() << " " << pt.get_signature());

    using namespace std::placeholders;
    pt.extend_before(std::bind(&PrintListener::before, this, _1, _2), id);
    pt.extend_after(std::bind(&PrintListener::after, this, _1, _2, _3), id);
  }
  void on_extension_point_unregister(FnExtensionPoint& pt) {
    REG_LOG("PrintListener unextending " << pt.get_name() << " " << pt.get_signature());
    pt.remove(id);
  }

  AdviceId id = get_unique_advice_id();
};
ListenerLifeCycle<PrintListener> printListener;
