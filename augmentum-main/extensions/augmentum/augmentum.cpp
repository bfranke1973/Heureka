/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "augmentum.h"

#include <vector>

using namespace augmentum;

namespace {
/**
 * Making my own list. Dealing with the circular references in std::list
 * refering to iteself, was driving me made. This is actually quicker to write
 * than working out the stl way. The erase function would be easier and faster
 * if this was a doubly linked list, but I don't think they should get called
 * very often, nor should the list ever be very deep, so I think it's better to
 * no pay the space cost.
 */
typedef void* Handle;
template <typename Function>
struct ListNode {
  Function function;
  AdviceId id;
  ListNode* next;
  ListNode(Function function, AdviceId id, ListNode* next)
      : function(function), id(id), next(next) {}
  operator Function&() { return function; }
};
template <typename Function>
struct ListIt {
  ListNode<Function>* node;
  ListIt& operator++() {
    node = node->next;
    return *this;
  }
  bool operator==(ListIt<Function> that) { return this->node == that.node; }
  Function& operator*() { return node->function; }
  operator Handle() { return node; }
};
template <typename Function>
struct List {
  ListNode<Function>* head = nullptr;

  ~List() {
    ListNode<Function>* curr = head;
    while (curr != nullptr) {
      ListNode<Function>* next = curr->next;
      delete curr;
      curr = next;
    }
  }
  void push_front(Function function, AdviceId id) { head = new ListNode(function, id, head); }
  bool empty() { return head == nullptr; }
  ListIt<Function> begin() { return {head}; }
  ListIt<Function> end() { return {nullptr}; }
  void erase(ListNode<Function>* node) {
    ListNode<Function>* prev = nullptr;
    ListNode<Function>* curr = head;
    while (curr != nullptr) {
      ListNode<Function>* next = curr->next;
      if (curr == node) {
        if (prev == nullptr) {
          head = next;
        } else {
          prev->next = next;
        }
        delete curr;
        break;
      }
      prev = curr;
      curr = next;
    }
  }
  void erase(Handle handle) {
    ListNode<Function>* node = reinterpret_cast<ListNode<Function>*>(handle);
    erase(node);
  }
  void remove(AdviceId id) {
    assert(id != 0);  // Should already have been checked in the
                      // FnExtensionPoint::remove functions.
    ListNode<Function>* prev = nullptr;
    ListNode<Function>* curr = head;

    while (curr != nullptr) {
      ListNode<Function>* next = curr->next;
      if (curr->id == id) {
        if (prev == nullptr) {
          head = next;
        } else {
          prev->next = next;
        }
        delete curr;
      }
      prev = curr;
      curr = next;
    }
  }
};

/**
 * Data stored in each extension point when it is extended.
 */
struct ExtensionData {
  List<BeforeAdvice> befores;
  List<AroundAdvice> arounds;
  List<AfterAdvice> afters;

  bool empty() { return befores.empty() && arounds.empty() && afters.empty(); }
};

/**
 * The listeners to extension point registration events.
 */
std::vector<Listener*>& listeners() {
  static std::vector<Listener*> list;
  return list;
}

/**
 * The extension points that have been registered.
 */
std::unordered_map<std::string, FnExtensionPoint*>& registry() {
  static auto* reg = new std::unordered_map<std::string, FnExtensionPoint*>();
  return *reg;
};
/**
 * At the end of the program, make sure to unregister all the extension points.
 */
__attribute__((destructor)) void empty_registry() {
  for (auto& [s, pt] : registry()) {
    for (auto listener : listeners()) {
      listener->on_extension_point_unregister(*pt);
    }
    pt->reset();
    delete pt;
    pt = nullptr;
  }
  registry().clear();
  delete &registry();
  // TODO: delete all types?
}

}  // namespace

std::string key_for_pt(const FnExtensionPoint& pt) {
  return pt.get_module_name() + "::" + pt.get_name();
}
FnExtensionPoint* FnExtensionPoint::get(const std::string& module_name, const std::string& name) {
  auto key = module_name + "::" + name;
  auto reg = registry();
  auto it = reg.find(key);
  if (it == reg.end()) {
    return nullptr;
  } else {
    return it->second;
  }
}

AdviceId augmentum::get_unique_advice_id() {
  static AdviceId next_id = 1;
  return next_id++;
}

void Listener::add(bool notify_existing_extension_points) {
  listeners().push_back(this);
  if (notify_existing_extension_points) {
    for (auto& [k, v] : registry()) {
      on_extension_point_register(*v);
    }
  }
  added = true;
}
void Listener::remove(bool notify_existing_extension_points) {
  if (added) {
    for (auto it = listeners().begin(); it != listeners().end();) {
      if (*it == this) {
        it = listeners().erase(it);
      } else {
        ++it;
      }
    }
    if (notify_existing_extension_points) {
      for (auto kv : registry()) {
        on_extension_point_unregister(*kv.second);
      }
    }
  }
  added = false;
}

void FnExtensionPoint::register_extension_point(FnExtensionPoint& pt) {
  registry()[key_for_pt(pt)] = &pt;
  for (auto listener : listeners()) {
    listener->on_extension_point_register(pt);
  }
}

void FnExtensionPoint::unregister_extension_point(FnExtensionPoint& pt) {
  for (auto listener : listeners()) {
    listener->on_extension_point_unregister(pt);
  }
  pt.reset();
  registry().erase(key_for_pt(pt));
}

void FnExtensionPoint::reset() {
  auto extension_data = reinterpret_cast<ExtensionData*>(data);
  delete extension_data;
  data = nullptr;
  *fn = original;
}

BeforeHandle FnExtensionPoint::extend_before(BeforeAdvice advice, AdviceId id) {
  prepare_for_extend();
  auto extension_data = reinterpret_cast<ExtensionData*>(data);
  extension_data->befores.push_front(advice, id);
  return extension_data->befores.begin();
}

void FnExtensionPoint::remove_before(BeforeHandle handle) {
  if (is_extended()) {
    assert(data != nullptr);
    auto extension_data = reinterpret_cast<ExtensionData*>(data);
    extension_data->befores.erase(handle);
    if (extension_data->empty()) {
      reset();
    }
  }
}

void FnExtensionPoint::remove_before(AdviceId id) {
  if (id != 0 && is_extended()) {
    assert(data != nullptr);
    auto extension_data = reinterpret_cast<ExtensionData*>(data);
    extension_data->befores.remove(id);
    if (extension_data->empty()) {
      reset();
    }
  }
}

AroundHandle FnExtensionPoint::extend_around(AroundAdvice advice, AdviceId id) {
  prepare_for_extend();
  auto extension_data = reinterpret_cast<ExtensionData*>(data);
  extension_data->arounds.push_front(advice, id);
  return extension_data->arounds.begin();
}

void FnExtensionPoint::remove_around(AroundHandle handle) {
  if (is_extended()) {
    assert(data != nullptr);
    auto extension_data = reinterpret_cast<ExtensionData*>(data);
    extension_data->arounds.erase(handle);
    if (extension_data->empty()) {
      reset();
    }
  }
}
void FnExtensionPoint::remove_around(AdviceId id) {
  if (id != 0 && is_extended()) {
    assert(data != nullptr);
    auto extension_data = reinterpret_cast<ExtensionData*>(data);
    extension_data->arounds.remove(id);
    if (extension_data->empty()) {
      reset();
    }
  }
}

AfterHandle FnExtensionPoint::extend_after(AfterAdvice advice, AdviceId id) {
  prepare_for_extend();
  auto extension_data = reinterpret_cast<ExtensionData*>(data);
  extension_data->afters.push_front(advice, id);
  return extension_data->afters.begin();
}

void FnExtensionPoint::remove_after(AfterHandle handle) {
  if (is_extended()) {
    assert(data != nullptr);
    auto extension_data = reinterpret_cast<ExtensionData*>(data);
    extension_data->afters.erase(handle);
    if (extension_data->empty()) {
      reset();
    }
  }
}
void FnExtensionPoint::remove_after(AdviceId id) {
  if (id != 0 && is_extended()) {
    assert(data != nullptr);
    auto extension_data = reinterpret_cast<ExtensionData*>(data);
    extension_data->afters.remove(id);
    if (extension_data->empty()) {
      reset();
    }
  }
}

void FnExtensionPoint::remove(AdviceId id) {
  if (id != 0 && is_extended()) {
    assert(data != nullptr);
    auto extension_data = reinterpret_cast<ExtensionData*>(data);
    assert(!extension_data->empty());
    extension_data->befores.remove(id);
    extension_data->arounds.remove(id);
    extension_data->afters.remove(id);
    if (extension_data->empty()) {
      reset();
    }
  }
}

void FnExtensionPoint::prepare_for_extend() {
  if (data == nullptr) {
    data = new ExtensionData();
    *fn = extended;
  } else {
    assert(*fn == extended);
  }
}

void FnExtensionPoint::call_previous(AroundHandle handle, RetVal ret_value, ArgVals arg_values) {
  assert(handle != nullptr);
  auto node = reinterpret_cast<ListNode<AroundAdvice>*>(handle);
  call_current(node->next, ret_value, arg_values);
}
void FnExtensionPoint::call_current(AroundHandle handle, RetVal ret_value, ArgVals arg_values) {
  if (handle != nullptr) {
    auto node = reinterpret_cast<ListNode<AroundAdvice>*>(handle);
    AroundAdvice& f = node->function;
    f(*this, handle, ret_value, arg_values);
  } else {
    call_original(ret_value, arg_values);
  }
}

void FnExtensionPoint::eval(FnExtensionPoint& pt, RetVal r_val, ArgVals arg_vals) {
  assert(pt.is_extended());
  assert(pt.data != nullptr);
  auto extension_data = reinterpret_cast<ExtensionData*>(pt.data);

  for (auto& before : extension_data->befores) {
    before(pt, arg_vals);
  }
  pt.call_current(extension_data->arounds.begin(), r_val, arg_vals);
  for (auto& after : extension_data->afters) {
    after(pt, r_val, arg_vals);
  }
}
