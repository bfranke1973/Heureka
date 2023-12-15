/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#ifndef __AUGMENTUM__
#define __AUGMENTUM__

#include <cstdint>
#include <functional>
#include <iostream>
#include <list>
#include <string>
#include <unordered_map>
#include <vector>

#include "type.h"

namespace augmentum {
struct FnExtensionPoint;
struct Listener;

typedef void (*Fn)();

typedef void* RetVal;
typedef void** ArgVals;

typedef void* BeforeHandle;
typedef void* AroundHandle;
typedef void* AfterHandle;

typedef uint32_t AdviceId;

typedef std::function<void(FnExtensionPoint&, ArgVals)> BeforeAdvice;
typedef std::function<void(FnExtensionPoint&, AroundHandle, RetVal, ArgVals)> AroundAdvice;
typedef std::function<void(FnExtensionPoint&, RetVal, ArgVals)> AfterAdvice;

/**
 * Extension Points for functions
 * The instrumenter will create one of these for every function it can
 * instrument. You can use this to change the behaviour of the function. If you
 * extend the function with the `extend` method, the extension will be called
 * instead of the original function, whenever anyone calls it.
 * The extension is provided with a reference to the extension point it extends,
 * a pointer to space to put the return value (if any), and an array of pointers
 * to the arguments of the function. In your extension, you can still call the
 * original by the `call_original` and `original_direct` methods.
 * `call_original` is a reflection like interface.
 * `original_direct` returns a direct pointer to the original function, but you
 * must cast to the appropriate type yourself. It is faster, but requires
 * knowing the function's type ahead of time to do the casting. You should not
 * try to construct any `FnExtensionPoint`s. The instrumenter should do that for
 * you. Extending and unextending may not be thread safe, so best done at the
 * start and end of the program.
 */
struct FnExtensionPoint {
  /**
   * Get an extension point.
   */
  static FnExtensionPoint* get(const std::string& module_name, const std::string& name);
  /**
   * Get the type of the function.
   */
  const FnTypeDesc& get_type() const { return *type_desc; }
  /**
   * Get the name of the extension point.
   * Typically, this will be whatever LLVM thinks the name is.
   *   e.g. if the C++ prototype is "int add(int, int)", then this name will be
   * "_Z3addii"
   */
  const std::string get_name() const { return name; }
  /**
   * Get the name of the module that defines this function.
   */
  const std::string get_module_name() const { return module_name; }
  /**
   * Check if this extension point has not been extended or replaced.
   */
  bool is_original() const { return *fn == original; }
  /**
   * Check if this extension point is extended.
   */
  bool is_extended() const { return *fn == extended; }
  /**
   * Check if this extension point has not been replaced.
   */
  bool is_replaced() const { return !is_original() && !is_extended(); }
  /**
   * Get the currently set function.
   * This method is for quite low-level uses, so this is expected to rarely be
   * useful.
   */
  Fn get_function() const { return *fn; }
  /**
   * Replace the function.
   * This takes a function which should have the same type as the original
   * function. It fully replaces the function. Any extensions will be removed.
   * This method is for quite low-level uses, so this is expected to rarely be
   * useful.
   */
  void replace(Fn f) {
    reset();
    *fn = f;
  }
  /**
   * Extend this point with the given function to be executed before the
   * function is called. The advice is provided with a reference to the
   * extension point it extends and an array of pointers to the arguments of the
   * function. In your extension, you can still call the original by the
   * `call_original` and `original_direct` methods.
   */
  BeforeHandle extend_before(BeforeAdvice advice, AdviceId id = 0);
  /**
   * Remove a before advice.
   */
  void remove_before(BeforeHandle handle);
  /**
   * Remove before advice by id. Must match the id given in a previous call to
   * extend_before.
   * Has no effect if id is 0.
   */
  void remove_before(AdviceId id);
  /**
   * Extend this point with the given function to be executed before the
   * function is called. The advice is provided with a reference to the
   * extension point it extends, a pointer to space to put the return value (if
   * any), and an array of pointers to the arguments of the function. In your
   * advice, you can still call the original by the `call_original` and
   * `original_direct` methods.
   */
  AroundHandle extend_around(AroundAdvice advice, AdviceId id = 0);
  /**
   * Remove an around advice.
   */
  void remove_around(AroundHandle handle);
  /**
   * Remove around advice by id. Must match the id given in a previous call to
   * extend_around.
   * Has no effect if id is 0.
   */
  void remove_around(AdviceId id);
  /**
   * Extend this point with the given function to be executed after the function
   * is called. The advice is provided with a reference to the extension point
   * it extends, a pointer to space to put the return value (if any), and an
   * array of pointers to the arguments of the function. In your advice, you can
   * still call the original by the `call_original` and `original_direct`
   * methods.
   */
  AfterHandle extend_after(AfterAdvice advice, AdviceId id = 0);
  /**
   * Remove after advice.
   */
  void remove_after(AfterHandle handle);
  /**
   * Remove after advice by id. Must match the id given in a previous call to
   * extend_after.
   * Has no effect if id is 0.
   */
  void remove_after(AdviceId id);
  /**
   * Remove advice by id. Removes from before, around, and after.
   * Has no effect if id is 0.
   */
  void remove(AdviceId id);

  /**
   * Return to original implementation.
   */
  void reset();
  /**
   * Call the previous function in a reflective manner for around extensions.
   * Space for the return value need to be allocated and pointed to by
   * `ret_value`. Likewise, the arguments should be pointed to by `arg_values`.
   */
  void call_previous(AroundHandle handle, RetVal ret_value, ArgVals arg_values);
  /**
   * Call the current around handle.
   */
  void call_current(AroundHandle handle, RetVal ret_value, ArgVals arg_values);
  /**
   * Call the original function in a reflective manner.
   * Space for the return value need to be allocated and pointed to by
   * `ret_value`. Likewise, the arguments should be pointed to by `arg_values`.
   * This is very low level and subverts the around stack.
   */
  void call_original(RetVal ret_value, ArgVals arg_values) const { reflect(ret_value, arg_values); }
  /**
   * Get a direct pointer to the original implementation of the function.
   * It is up to you to cast it properly. Consider using the reflexive version
   * instead (`call_original`).
   * This is very low level and subverts the around stack.
   */
  Fn original_direct() const { return original; }

  /**
   * Convenience methods to directly access the type.
   */
  std::string get_signature() const { return type_desc->get_signature(); }
  const TypeDesc* get_return_type() const { return type_desc->get_return_type(); }
  const size_t get_num_args() const { return type_desc->get_num_args(); }
  const TypeDesc* get_arg_type(size_t i) const { return type_desc->get_arg_type(i); }
  const std::vector<TypeDesc*> get_arg_types() const { return type_desc->get_arg_types(); }

  /**
   * Cast to a string, getting the name
   */
  operator std::string() const { return get_name(); }

 private:
  friend struct Internal;
  typedef void (*ReflectFn)(RetVal ret_value, ArgVals arg_values);

  // Only Internal can create these.  It will register them and unregister them,
  // too.
  FnExtensionPoint(std::string module_name, std::string name, FnTypeDesc* type_desc, Fn* fn,
                   Fn original, Fn extended, ReflectFn reflect)
      : module_name(module_name),
        name(name),
        type_desc(type_desc),
        fn(fn),
        original(original),
        extended(extended),
        reflect(reflect),
        data(nullptr) {
    // fn should have been initialised before we call this
    assert(*fn == original);
  }

  FnTypeDesc* type_desc;
  std::string module_name;
  std::string name;
  Fn* fn;
  Fn original;
  Fn extended;
  ReflectFn reflect;
  void* data;

  /**
   * Prepare for extension.
   */
  void prepare_for_extend();

  static void eval(FnExtensionPoint& pt, RetVal r_val, ArgVals arg_vals);
  static void register_extension_point(FnExtensionPoint& pt);
  static void unregister_extension_point(FnExtensionPoint& pt);
  static void empty_registry();
};

/**
 * A listener to various lifecycle events for extension points becoming
 * available.
 */
struct Listener {
  Listener() {}
  virtual ~Listener() {
    if (added) {
      remove();
    }
  };
  /**
   * Called when an extension point is registered.
   */
  virtual void on_extension_point_register(FnExtensionPoint& pt) {}
  /**
   * Called when an extension point is unregistered.
   */
  virtual void on_extension_point_unregister(FnExtensionPoint& pt) {}

  /**
   * Add this listener to listen for events.
   * If `notify_existing_extension_points` is true, then a registration
   * event will be notified for each already registered extension point.
   * I.e. `on_extension_point_register` will be called for each point.
   */
  void add(bool notify_existing_extension_points = true);
  /**
   * Stop listening to events.
   * If `notify_existing_extension_points` is true, then a unregistration
   * event will be notified for each already registered extension point.
   * This allows simple clean up from any extension points that have been
   * extended by this listener.
   */
  void remove(bool notify_existing_extension_points = true);

 private:
  bool added = false;
};

/**
 * An object to make managing the lifecycle of listeners a little easier.
 * The constructor will call add on the listener, the destructor will call
 * remove.
 *
 * Why not just put this in the constructor and destructor of a derived class of
 * Listener? I think that the vtable isn't guaranteed to be set up in the
 * constructor, so it may seg fault.
 */
template <typename L>
struct ListenerLifeCycle {
  /*
   *The listener object.
   */
  L listener;
  /**
   * Construct the listener and call add.
   */
  template <typename... Args>
  ListenerLifeCycle(Args... args) : listener(args...) {
    listener.add();
  }
  /**
   * Call remove on the listener.
   */
  ~ListenerLifeCycle() { listener.remove(); }
};

/**
 * Get a unique advice id.
 * Advice can be removed by using the handle returned from extending. This,
 * however, is sometimes inconvenient, since to clean up you need to remember
 * which handles you got from each extension point. To make things easier, you
 * can give an id to any of the extend methods. This allows you to remove the
 * extension later by that id. To ensure you get a unique id for you extension,
 * you can call this method.
 *
 * It may not always be necessary to remove extensions. Typically, they will be
 * in use until just before the end of the program, so it is probably fine to
 * let them leak. However, if you are making general extensions for other people
 * to use, it is probably good practice to clean up after yourself, just in
 * case.
 */
extern AdviceId get_unique_advice_id();
}  // namespace augmentum
#endif
