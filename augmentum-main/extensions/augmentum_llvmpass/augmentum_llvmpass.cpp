/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Instrumentation pass for LLVM.
 */
#include <filesystem>
#include <fstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "instrumentation_stats.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/LegacyPassManager.h"
#include "llvm/IR/Module.h"
#include "llvm/Pass.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Transforms/IPO/PassManagerBuilder.h"
#include "llvm/Transforms/Utils/BasicBlockUtils.h"
#include "llvm/Transforms/Utils/Cloning.h"
#include "llvm/Transforms/Utils/ModuleUtils.h"
#include "should_instrument.h"
#include "should_instrument_prior.h"
#include "utils.h"

using namespace llvm;

namespace augmentum {
namespace llvmpass {
/**
 * Command line option to specify a python script for should_instrument.
 */
static cl::opt<std::string> PythonScript(
    "augmentum-python",
    cl::desc("Path to python script that provides a function 'should_instrument'"));

/**
 * Command line option to specify an output directory for instrumentation
 * statistics.
 */
static cl::opt<std::string> StatsDirectory(
    "instrumentation-stats-output",
    cl::desc("Specify an output directory for instrumentation statistics."
             "Collected statistics are appended already exisiting statistic files."),
    cl::init(""));

/**
 * Command line option to specify if only statistics should be collected and no
 * instrumentation performed.
 */
static cl::opt<bool> DryRun(
    "dry-run",
    cl::desc("If set, a comprehensive set of instrumentation statistics is collected"
             " but no transformations are performed."),
    cl::init(false));

/**
 * Command line option to specify an output folder for LLVM-IR code of
 * transformed modules.
 */
static cl::opt<std::string> EmitIRDirectory("emit-transformed-ir",
                                            cl::desc("Specify a folder where LLVM IR code of "
                                                     "transformed modules will be stored."),
                                            cl::init(""));

/**
 * Command line option to specify a file where target functions that should be
 * instrumented can be found.
 */
static cl::opt<std::string> TargetFunctions(
    "target-functions", cl::desc("Specify a csv file where target functions are listed that should "
                                 " be instrumented."));

/**
 * This id is used to indicate a reason for the
 * instrumentation decision.
 */
enum CanInstrumentID { CAN_NA, CAN_INSTRUMENT, CAN_NOT_DECL, CAN_NOT_VARARGS };

/**
 * See if the function can be instrumented.
 * It has to be defined, rather than just declared.
 * It must not have vararg parameters.
 *
 * Everything else is accepted and if we cannot deal with it ,
 * we mark it as unknown type later on.
 */
static CanInstrumentID can_be_instrumented(const Function& function) {
  // Only instrument definitions.
  if (function.isDeclaration()) {
    return CAN_NOT_DECL;
  }
  // Don't instrument vararg functions
  if (function.isVarArg()) {
    return CAN_NOT_VARARGS;
  }

  return CAN_INSTRUMENT;
}

/**
 * This class does most of the processing of a function.
 * AugmentumModule first sets up per module things and decides which functions
 * to instrument. Then it gets this class to do the work per function.
 */
struct AugmentumFunction {
  AugmentumFunction(Function& function, ShouldInstrument& should_instrument)
      : function(function), should_instrument(should_instrument) {}

  /**
   * Transform the function if needed.
   *
   * Returns true if function was transformed, false otherwise.
   */
  bool transform() {
    if (can_be_instrumented(function) == CAN_INSTRUMENT && should_instrument.function(function)) {
      // errs() << "DEBUG: instrumenting function " << function.getName() <<
      //           " with type " << type_to_string(function.getType()) << "\n";

      make_original_clone();
      declare_globals();
      make_reflect();
      make_extended();
      rewrite_function();
      make_init();

      return true;
    } else {
      // errs() << "DEBUG: function not instrumented " << function.getName() <<
      //           " with type " << type_to_string(function.getType()) << "\n";
      return false;
    }
  }

 private:
  Function& function;
  ShouldInstrument& should_instrument;
  Module& module = *function.getParent();
  LLVMContext& ctx = module.getContext();
  Function* original = nullptr;
  Function* extended = nullptr;
  Function* reflect = nullptr;
  GlobalVariable* fn_ptr = nullptr;
  GlobalVariable* extension_point_ptr = nullptr;

  /**
   * Oft used types
   */
  Type* void_type = Type::getVoidTy(ctx);
  PointerType* void_ptr_type = Type::getInt8PtrTy(ctx);
  PointerType* void_ptr_ptr_type = void_ptr_type->getPointerTo();

  /**
   * Some symbol names
   */
  static constexpr const char* symbol_Internal__get_unknown_type =
      "_ZN9augmentum8Internal16get_unknown_typeEPKcS2_";
  static constexpr const char* symbol_Internal__get_void_type =
      "_ZN9augmentum8Internal13get_void_typeEv";
  static constexpr const char* symbol_Internal__get_i1_type =
      "_ZN9augmentum8Internal11get_i1_typeEv";
  static constexpr const char* symbol_Internal__get_i8_type =
      "_ZN9augmentum8Internal11get_i8_typeEv";
  static constexpr const char* symbol_Internal__get_i16_type =
      "_ZN9augmentum8Internal12get_i16_typeEv";
  static constexpr const char* symbol_Internal__get_i32_type =
      "_ZN9augmentum8Internal12get_i32_typeEv";
  static constexpr const char* symbol_Internal__get_i64_type =
      "_ZN9augmentum8Internal12get_i64_typeEv";
  static constexpr const char* symbol_Internal__get_float_type =
      "_ZN9augmentum8Internal14get_float_typeEv";
  static constexpr const char* symbol_Internal__get_double_type =
      "_ZN9augmentum8Internal15get_double_typeEv";
  static constexpr const char* symbol_Internal__get_ptr_type =
      "_ZN9augmentum8Internal12get_ptr_typeEPNS_8TypeDescE";
  static constexpr const char* symbol_Internal__get_array_type =
      "_ZN9augmentum8Internal14get_array_typeEPNS_8TypeDescEm";
  static constexpr const char* symbol_Internal__get_anon_struct_type =
      "_ZN9augmentum8Internal20get_anon_struct_typeEmz";
  static constexpr const char* symbol_Internal__get_forward_struct_type =
      "_ZN9augmentum8Internal23get_forward_struct_typeEPKcS2_";
  static constexpr const char* symbol_Internal__set_struct_elem_types =
      "_ZN9augmentum8Internal21set_struct_elem_typesEPNS_8TypeDescEmz";
  static constexpr const char* symbol_Internal__get_function_type =
      "_ZN9augmentum8Internal17get_function_typeEPNS_8TypeDescEmz";
  static constexpr const char* symbol_Internal__create_extension_point =
      "_ZN9augmentum8Internal22create_extension_pointEPKcS2_PNS_"
      "8TypeDescEPPFvvES6_S6_PFvPvPS8_E";
  static constexpr const char* symbol_Internal__eval =
      "_ZN9augmentum8Internal4evalEPNS_16FnExtensionPointEPvPS3_";

  static constexpr const char* symbol_Internal__debug_print =
      "_ZN9augmentum8Internal11debug_printEPKc";
  static constexpr const char* symbol_Internal__debug_print_addr =
      "_ZN9augmentum8Internal16debug_print_addrEPKv";

  static constexpr const char* symbol_struct_augmentum__extension_point =
      "struct.augmentum::FnExtensionPoint";
  static constexpr const char* symbol_struct_augmentum__type_desc = "struct.augmentum::TypeDesc";

  /**
   * Supported integer bit widths
   */
  static const inline std::vector<int> supported_intBits{1, 8, 16, 32, 64};

  /**
   * Utility function to debug generated runtime code.
   *
   * This function generates instructions for printing a given string message to
   * standard out.
   */
  void gen_debug_print_instructions(IRBuilder<>& builder, StringRef message) {
    auto debug_msg_global_name = global_name("debug", "msg__" + std::string(message));
    auto debug_msg_data = ConstantDataArray::getString(ctx, message, true);
    auto debug_msg_global = module.getNamedGlobal(debug_msg_global_name);
    if (debug_msg_global == nullptr) {
      debug_msg_global =
          new GlobalVariable(module, debug_msg_data->getType(), true, GlobalValue::PrivateLinkage,
                             debug_msg_data, debug_msg_global_name);
    }
    auto zero = ConstantInt::getSigned(Type::getInt32Ty(ctx), 0);
    auto debug_msg_access = ConstantExpr::getInBoundsGetElementPtr(
        debug_msg_data->getType(), debug_msg_global, ArrayRef<Constant*>({zero, zero}));

    auto debug_print = module.getOrInsertFunction(symbol_Internal__debug_print, void_type,
                                                  Type::getInt8PtrTy(ctx));
    auto debug_print_call = builder.CreateCall(debug_print.getFunctionType(),
                                               debug_print.getCallee(), {debug_msg_access});
    debug_print_call->setTailCall();
  }

  /**
   * Utility function to debug generated runtime code.
   *
   * This function generates instructions for printing a given void pointer
   * to standard out.
   */
  void gen_debug_print_addr_instructions(IRBuilder<>& builder, Value* ptr) {
    Value* ptr_void = builder.CreateBitCast(ptr, void_ptr_type);
    FunctionCallee debug_print_addr =
        module.getOrInsertFunction(symbol_Internal__debug_print_addr, void_type, void_ptr_type);
    CallInst* debug_print_addr_call = builder.CreateCall(debug_print_addr.getFunctionType(),
                                                         debug_print_addr.getCallee(), {ptr_void});
    debug_print_addr_call->setTailCall();
  }

  /**
   * Make a global name.
   * The name will be augmentum::<mid><suffix>
   */
  static std::string global_name(std::string mid, std::string suffix) {
    auto s = "augmentum::" + mid + "__" + suffix + "__";
    return s;
  }

  /**
   * Make a global name.
   * The name will be augmentum::<function.name><suffix>
   */
  std::string global_name_fn_qualed(std::string suffix) const {
    return global_name(function.getName().str(), suffix);
  }

  /**
   * Add call attributes to a call of the fn pointer or the original if
   * required.
   */
  void add_call_attributes(CallInst* call) {
    for (int argIdx = 0; argIdx < function.arg_size(); ++argIdx) {
      Argument* arg = function.getArg(argIdx);
      if (arg->hasAttribute(Attribute::ByVal)) {
        call->addParamAttr(argIdx, arg->getAttribute(Attribute::ByVal));
      }
    }
  }

  /**
   * Add function attributes to a call of the fn pointer or the original if
   * required.
   */
  void add_function_attributes(Function* func) {
    for (int argIdx = 0; argIdx < function.arg_size(); ++argIdx) {
      Argument* arg = function.getArg(argIdx);
      if (arg->hasAttribute(Attribute::ByVal)) {
        func->addParamAttr(argIdx, arg->getAttribute(Attribute::ByVal));
      }
    }
  }

  /**
   * Declare the globals.
   * These will be for the extension point pointer and for the function pointer
   */
  void declare_globals() {
    assert(original);

    // ExtensionPoint pointer
    assert(extension_point_ptr == nullptr);
    std::string extension_point_ptr_id = global_name_fn_qualed("extension_point_ptr");
    auto extension_point_ptr_type =
        get_type_by_name_or_create(symbol_struct_augmentum__extension_point)->getPointerTo();
    extension_point_ptr = dyn_cast<GlobalVariable>(
        module.getOrInsertGlobal(extension_point_ptr_id, extension_point_ptr_type));
    extension_point_ptr->setLinkage(GlobalValue::PrivateLinkage);
    auto fun_extention_point_nullptr = ConstantPointerNull::get(extension_point_ptr_type);
    extension_point_ptr->setInitializer(fun_extention_point_nullptr);

    // Function pointer
    assert(fn_ptr == nullptr);
    std::string fn_ptr_id = global_name_fn_qualed("fn_ptr");
    auto fn_ptr_type = function.getFunctionType()->getPointerTo();
    fn_ptr = dyn_cast<GlobalVariable>(module.getOrInsertGlobal(fn_ptr_id, fn_ptr_type));
    fn_ptr->setLinkage(GlobalValue::PrivateLinkage);
    fn_ptr->setInitializer(original);
  }

  /**
   * Copy the function.
   * We are going to rewrite the innards of function so that it calls the
   * extension. This method keeps the original implementation around. 'original'
   * must be null on entry and will be non null on exit.
   *
   * To be clear - 'original' is a copy of the original function, not the
   * function.
   */
  void make_original_clone() {
    assert(original == nullptr);
    ValueToValueMapTy vmap;
    original = CloneFunction(&function, vmap);
    original->setName(global_name_fn_qualed("original"));
    original->setLinkage(GlobalValue::PrivateLinkage);
  }

  /**
   * Make the reflective function.
   * It essentially looks like this:
   *   void augmentum::<function.name>__reflect__(void* return_value, void*
   * arg_values[]) { ReturnType* ret = return_value; ArgType0* arg0 =
   * arg_values[0]; ArgType1* arg1 = arg_values[1];
   *       ...
   *       ArgTypeN* argN = arg_values[N];
   *       *ret = augmentum::<function.name>__original__(arg0, arg1, ..., argN);
   *   }
   * If the return type is void then return_value should be nullptr (but we
   * don't both to check) and nothing will be done with the return value.  I.e.
   * the last line above becomes: augmentum::<function.name>__original__(arg0,
   * arg1, ..., argN);
   */
  void make_reflect() {
    assert(original && reflect == nullptr);

    // Create the function
    auto name = global_name_fn_qualed("reflect");
    auto voidTy = Type::getVoidTy(ctx);
    auto voidPtrTy = Type::getInt8PtrTy(ctx);
    auto voidPtrPtrTy = voidPtrTy->getPointerTo();
    module.getOrInsertFunction(name, voidTy, voidPtrTy, voidPtrPtrTy);
    reflect = module.getFunction(name);
    reflect->setLinkage(GlobalValue::PrivateLinkage);

    // Build some code!
    auto bb = BasicBlock::Create(ctx, "", reflect);
    IRBuilder<> builder(ctx);
    builder.SetInsertPoint(bb);

    auto return_value_ptr_void = reflect->getArg(0);
    auto arg_values_ptr_ptr_void = reflect->getArg(1);
    auto function_type = original->getFunctionType();

    // Extract the args
    std::vector<Value*> arg_values;
    for (int i = 0; i < function_type->getNumParams(); ++i) {
      auto param_type = function_type->getParamType(i);
      auto arg_value_ptr_ptr_void = builder.CreateConstInBoundsGEP1_64(
          nullptr, arg_values_ptr_ptr_void, i, "arg" + std::to_string(i) + "PPV");

      Value* arg_value_ptr;
      Argument* arg = function.getArg(i);
      if (arg->hasAttribute(Attribute::ByVal)) {
        // if one of the arguments has a byval attribute, we do one pointer cast
        // less
        arg_value_ptr = builder.CreateBitCast(arg_value_ptr_ptr_void, param_type->getPointerTo(),
                                              "arg" + std::to_string(i) + "PT");
      } else {
        auto arg_value_ptr_ptr = builder.CreateBitCast(arg_value_ptr_ptr_void,
                                                       param_type->getPointerTo()->getPointerTo(),
                                                       "arg" + std::to_string(i) + "PPT");
        arg_value_ptr = builder.CreateLoad(arg_value_ptr_ptr, "arg" + std::to_string(i) + "PT");
      }

      auto arg_value = builder.CreateLoad(arg_value_ptr, "arg" + std::to_string(i) + "T");
      arg_values.push_back(arg_value);
    }
    // Cast the return value
    auto return_type = function_type->getReturnType();
    // Call and store
    if (return_type == Type::getVoidTy(ctx)) {
      auto call = builder.CreateCall(function_type, original, arg_values);
      add_call_attributes(call);
      call->setTailCall();
    } else {
      auto return_value_ptr =
          builder.CreateBitCast(return_value_ptr_void, return_type->getPointerTo(), "retPT");
      auto call = builder.CreateCall(function_type, original, arg_values, "retT");
      add_call_attributes(call);
      call->setTailCall();
      auto store = builder.CreateStore(call, return_value_ptr);
    }
    builder.CreateRetVoid();
  }

  /**
   * Make the extended function.
   * Next to the extension point, we have a function pointer, fn.
   * When the extension point isn't extended, this pointer points to the clone
   * of the original function. When the extension point is extended, it points
   * to a function which dispatches to the library. This way the cost of using
   * this system but only extending a couple of things is kept to a minimum. The
   * code for this function looks like: ReturnType
   * augmentum::<function.name>__extended__(ArgType0 arg0, ArgType1 arg1, ...,
   * ArgTypeN argN) { ReturnType ret; void* args[] = { &arg0, &arg1, ..., &argN
   * };
   *       augmentum::FnExtensionPoint::eval(augmentum::<function.name>__extension_point__,
   * &ret, args); return ret;
   *   }
   * If the return type is void, then the ret pointer is the nullptr.
   *   void augmentum::<function.name>__extended__(ArgType0 arg0, ArgType1 arg1,
   * ..., ArgTypeN argN) { void* args[] = { &arg0, &arg1, ..., &argN };
   *       augmentum::FnExtensionPoint::eval(augmentum::<function.name>__extension_point__,
   * nullptr, args);
   *   }
   */
  void make_extended() {
    assert(extended == nullptr);
    auto function_type = function.getFunctionType();

    // Create the function
    auto name = global_name_fn_qualed("extended");
    module.getOrInsertFunction(name, function.getFunctionType());
    extended = module.getFunction(name);
    extended->setLinkage(GlobalValue::PrivateLinkage);

    // add required attributes to extend header from original function header
    add_function_attributes(extended);

    // Build some code!
    auto bb = BasicBlock::Create(ctx, "", extended);
    IRBuilder<> builder(ctx);
    builder.SetInsertPoint(bb);

    // Do the allocs
    Type* ret_type = function_type->getReturnType();
    bool ret_void = ret_type == Type::getVoidTy(ctx);
    Value* ret_alloc = ret_void ? nullptr : builder.CreateAlloca(ret_type, nullptr, "ret_alloc");
    std::vector<Value*> arg_allocs(extended->arg_size(), nullptr);
    for (int i = 0; i < extended->arg_size(); ++i) {
      auto arg = extended->getArg(i);

      // we reference byvals directly from the function arguments
      if (!arg->hasAttribute(Attribute::ByVal)) {
        auto arg_alloc =
            builder.CreateAlloca(arg->getType(), nullptr, "arg_alloc" + std::to_string(i));
        arg_allocs[i] = arg_alloc;
      }
    }
    auto args_type = ArrayType::get(void_ptr_type, extended->arg_size());
    auto args_alloc = builder.CreateAlloca(args_type, nullptr, "argsAlloc");

    // Create stores for args
    for (int i = 0; i < extended->arg_size(); ++i) {
      auto arg = extended->getArg(i);
      auto arg_type = arg->getType();
      auto arg_void_ptr_ptr = builder.CreateConstInBoundsGEP2_64(
          nullptr, args_alloc, 0, i, "argVoidPtrPtr" + std::to_string(i));

      // we reference byvals directly from the function arguments
      if (arg->hasAttribute(Attribute::ByVal)) {
        auto arg_ptr = builder.CreateBitCast(arg_void_ptr_ptr, arg_type->getPointerTo(),
                                             "argPtrPtr" + std::to_string(i));
        builder.CreateStore(arg, arg_ptr);
      } else {
        auto arg_alloc = arg_allocs[i];
        builder.CreateStore(arg, arg_alloc);  // <-- XXX crashes here
        auto arg_ptr_ptr =
            builder.CreateBitCast(arg_void_ptr_ptr, arg_type->getPointerTo()->getPointerTo(),
                                  "argPtrPtr" + std::to_string(i));
        builder.CreateStore(arg_alloc, arg_ptr_ptr);
      }
    }

    // Make the call
    auto ret_void_ptr = ret_void ? ConstantPointerNull::get(void_ptr_type)
                                 : builder.CreateBitCast(ret_alloc, void_ptr_type, "retVoidPtr");
    auto args_void_ptr_ptr =
        builder.CreateConstInBoundsGEP2_64(nullptr, args_alloc, 0, 0, "argVoidPtrPtr");
    auto eval =
        module.getOrInsertFunction(symbol_Internal__eval,
                                   void_type,                                         // return
                                   extension_point_ptr->getType()->getElementType(),  // arg0
                                   void_ptr_type,                                     // arg1
                                   void_ptr_ptr_type                                  // arg2
        );
    // load to dereference
    auto extension_point = builder.CreateLoad(extension_point_ptr, "extension_point");
    auto call = builder.CreateCall(eval.getFunctionType(), eval.getCallee(),
                                   {extension_point, ret_void_ptr, args_void_ptr_ptr});

    // Load the result
    if (!ret_void) {
      auto ret_val = builder.CreateLoad(ret_alloc, "retVal");
      builder.CreateRet(ret_val);
    } else {
      builder.CreateRetVoid();
    }
  }
  /**
   * Clear all the basic blocks from the function.
   * "function.getBasicBlockList().clear();" does not cut it.
   */
  void clear_function() {
    SmallVector<BasicBlock*, 64> worklist;
    for (Function::iterator bb = function.begin(); bb != function.end(); ++bb) {
      worklist.push_back(&*bb);
    }
    // These blocks aren't dead yet, but this code works nicely to delete them
    // all anyway.
    DeleteDeadBlocks(worklist);
  }

  /**
   * Rewrite the function so that it calls the fn field on the extension point.
   * The function will have all its code removed, then replaced with something
   * like this: ReturnType <function.name>(ArgType0 arg0, ArgType1 arg1, ...,
   * ArgTypeN argN) { ReturnType (*fn)(ArgType0, ArgType1, ..., ArgTypeN) =
   * augmentum::<function.name>__extension_point__.fn; return fn(arg0, arg1,
   * ..., argN);
   *   }
   */
  void rewrite_function() {
    assert(fn_ptr);
    FunctionType* function_type = function.getFunctionType();

    // Get rid of the existing code
    clear_function();

    // Create code
    BasicBlock* bb = BasicBlock::Create(ctx, "", &function);
    IRBuilder<> builder(ctx);
    builder.SetInsertPoint(bb);

    // Get the fn pointer as the right type
    LoadInst* fn = builder.CreateLoad(fn_ptr, "fn");

    std::vector<Value*> args;
    for (auto& arg : function.args()) {
      args.push_back(&arg);
    }

    CallInst* call = builder.CreateCall(function_type, fn, args);
    add_call_attributes(call);
    call->setTailCall();

    // return the call result if this function has a return type
    if (function_type->getReturnType() == Type::getVoidTy(ctx))
      builder.CreateRetVoid();
    else
      builder.CreateRet(call);
  }

  /**
   * Get the given type by its specified name. Add to module if it
   * does not exist yet.
   */
  Type* get_type_by_name_or_create(const char* type_name) {
    assert(type_name);

    Type* t = module.getTypeByName(type_name);
    if (!t)
      t = StructType::create(ctx, type_name);
    return t;
  }

  /**
   * Get typeDesc pointer type. Add to module if it does not exist yet.
   */
  Type* get_typeDesc_ptr_type() {
    return get_type_by_name_or_create(symbol_struct_augmentum__type_desc)->getPointerTo();
  }

  /**
   * Generate instructions to get typeDesc pointer for unknown type.
   */
  Value* get_unknown_type_desc(Type* type, IRBuilder<>& builder) {
    assert(type);

    Type* typeDesc_ptr_type = get_typeDesc_ptr_type();

    // Module Name
    auto module_name_global_name = global_name("module", "name");
    auto module_name_data = ConstantDataArray::getString(ctx, module.getName(), true);
    auto module_name_global = module.getNamedGlobal(module_name_global_name);
    if (module_name_global == nullptr) {
      module_name_global =
          new GlobalVariable(module, module_name_data->getType(), true, GlobalValue::PrivateLinkage,
                             module_name_data, module_name_global_name);
    }
    auto zero = ConstantInt::getSigned(Type::getInt32Ty(ctx), 0);
    auto module_name_access = ConstantExpr::getInBoundsGetElementPtr(
        module_name_data->getType(), module_name_global, ArrayRef<Constant*>({zero, zero}));

    // Unknown Type Name, i.e. type signature
    auto unknown_name_global_name = global_name("unknown", type_to_string(type));
    auto unknown_name_data = ConstantDataArray::getString(ctx, type_to_string(type), true);
    auto unknown_name_global = module.getNamedGlobal(unknown_name_global_name);
    if (unknown_name_global == nullptr) {
      unknown_name_global = new GlobalVariable(module, unknown_name_data->getType(), true,
                                               GlobalValue::PrivateLinkage, unknown_name_data,
                                               unknown_name_global_name);
    }
    auto unknown_name_access = ConstantExpr::getInBoundsGetElementPtr(
        unknown_name_data->getType(), unknown_name_global, ArrayRef<Constant*>({zero, zero}));

    // get unknown type desc value
    auto get_unknown_type =
        module.getOrInsertFunction(symbol_Internal__get_unknown_type,
                                   typeDesc_ptr_type,        // return type
                                   Type::getInt8PtrTy(ctx),  // arg0 char* module_name
                                   Type::getInt8PtrTy(ctx)   // arg1 char* unknown type signature
        );

    auto get_unknown_type_call =
        builder.CreateCall(get_unknown_type.getFunctionType(), get_unknown_type.getCallee(),
                           {module_name_access, unknown_name_access});
    get_unknown_type_call->setTailCall();

    return get_unknown_type_call;
  }

  /**
   * Generate instructions to get typeDesc pointer for base type
   * (void,i1,i8,i16,i32,i64,float,double) using internal function calll.
   * Add internal method prototype to module if it does not exist yet.
   */
  Value* get_base_type_desc(IRBuilder<>& builder, StringRef get_base_type_call_symbol) {
    Type* typeDesc_ptr_type = get_typeDesc_ptr_type();

    auto get_base_type = module.getOrInsertFunction(get_base_type_call_symbol, typeDesc_ptr_type);
    auto base_typeDesc_call =
        builder.CreateCall(get_base_type.getFunctionType(), get_base_type.getCallee());
    base_typeDesc_call->setTailCall();
    return base_typeDesc_call;
  }

  /**
   * Generate instructions to get typeDesc pointer for given pointer type
   * depending on referenced element type.
   * Add internal method prototype to module if it does not exist yet.
   */
  Value* get_pointer_type_desc(PointerType* ptype, IRBuilder<>& builder,
                               std::unordered_map<Type*, Value*>& type_map) {
    assert(ptype);

    auto element_value = get_type_desc(ptype->getElementType(), builder, type_map);

    Type* typeDesc_ptr_type = get_typeDesc_ptr_type();

    auto get_ptr_typeDesc = module.getOrInsertFunction(symbol_Internal__get_ptr_type,
                                                       typeDesc_ptr_type, typeDesc_ptr_type);
    auto get_ptr_typeDesc_call = builder.CreateCall(get_ptr_typeDesc.getFunctionType(),
                                                    get_ptr_typeDesc.getCallee(), {element_value});
    get_ptr_typeDesc_call->setTailCall();
    return get_ptr_typeDesc_call;
  }

  Value* get_array_type_desc(ArrayType* atype, IRBuilder<>& builder,
                             std::unordered_map<Type*, Value*>& type_map) {
    assert(atype);

    auto element_value = get_type_desc(atype->getElementType(), builder, type_map);
    auto num_elems = ConstantInt::get(Type::getInt64Ty(ctx), atype->getNumElements());

    Type* typeDesc_ptr_type = get_typeDesc_ptr_type();

    auto get_array_typeDesc =
        module.getOrInsertFunction(symbol_Internal__get_array_type, typeDesc_ptr_type,
                                   typeDesc_ptr_type, Type::getInt64Ty(ctx));
    auto get_array_typeDesc_call =
        builder.CreateCall(get_array_typeDesc.getFunctionType(), get_array_typeDesc.getCallee(),
                           {element_value, num_elems});
    get_array_typeDesc_call->setTailCall();
    return get_array_typeDesc_call;
  }

  Value* get_named_struct_type_desc(StructType* struct_type, IRBuilder<>& builder,
                                    std::unordered_map<Type*, Value*>& type_map) {
    assert(struct_type);

    Type* typeDesc_ptr_type = get_typeDesc_ptr_type();

    // Module Name
    auto module_name_global_name = global_name("module", "name");
    auto module_name_data = ConstantDataArray::getString(ctx, module.getName(), true);
    auto module_name_global = module.getNamedGlobal(module_name_global_name);
    if (module_name_global == nullptr) {
      module_name_global =
          new GlobalVariable(module, module_name_data->getType(), true, GlobalValue::PrivateLinkage,
                             module_name_data, module_name_global_name);
    }
    auto zero = ConstantInt::getSigned(Type::getInt32Ty(ctx), 0);
    auto module_name_access = ConstantExpr::getInBoundsGetElementPtr(
        module_name_data->getType(), module_name_global, ArrayRef<Constant*>({zero, zero}));

    // Struct Name
    auto struct_name_global_name = global_name("struct", struct_type->getName());
    auto struct_name_data = ConstantDataArray::getString(ctx, struct_type->getName(), true);
    auto struct_name_global = module.getNamedGlobal(struct_name_global_name);
    if (struct_name_global == nullptr) {
      struct_name_global =
          new GlobalVariable(module, struct_name_data->getType(), true, GlobalValue::PrivateLinkage,
                             struct_name_data, struct_name_global_name);
    }
    auto struct_name_access = ConstantExpr::getInBoundsGetElementPtr(
        struct_name_data->getType(), struct_name_global, ArrayRef<Constant*>({zero, zero}));

    // get struct type desc value
    auto get_forward_struct_type =
        module.getOrInsertFunction(symbol_Internal__get_forward_struct_type,
                                   typeDesc_ptr_type,        // return type
                                   Type::getInt8PtrTy(ctx),  // arg0 char* module_name
                                   Type::getInt8PtrTy(ctx)   // arg1 char* name
        );

    auto get_forward_struct_type_call = builder.CreateCall(
        get_forward_struct_type.getFunctionType(), get_forward_struct_type.getCallee(),
        {module_name_access, struct_name_access});
    get_forward_struct_type_call->setTailCall();

    // save to type map in case of recursive calls
    type_map[struct_type] = get_forward_struct_type_call;

    auto num_elems = ConstantInt::get(Type::getInt64Ty(ctx), struct_type->getNumElements());

    // get element type descriptor values
    std::vector<Value*> args{get_forward_struct_type_call, num_elems};
    for (int i = 0; i < struct_type->getNumElements(); ++i) {
      auto elem_type = struct_type->getElementType(i);
      auto elem_value = get_type_desc(elem_type, builder, type_map);
      args.push_back(elem_value);
    }

    // set struct element types
    auto set_struct_elem_types = module.getOrInsertFunction(
        // TODO make size_t int64 architecture dependent
        symbol_Internal__set_struct_elem_types,
        FunctionType::get(Type::getVoidTy(ctx), {typeDesc_ptr_type, Type::getInt64Ty(ctx)}, true));

    auto set_struct_elem_types_call = builder.CreateCall(set_struct_elem_types.getFunctionType(),
                                                         set_struct_elem_types.getCallee(), args);
    set_struct_elem_types_call->setTailCall();

    // TODO is this necessary now that we save to the type map already after
    // calling get_forward_struct
    return get_forward_struct_type_call;
  }

  Value* get_unnamed_struct_type_desc(StructType* struct_type, IRBuilder<>& builder,
                                      std::unordered_map<Type*, Value*>& type_map) {
    assert(struct_type);

    Type* typeDesc_ptr_type = get_typeDesc_ptr_type();

    auto num_elems = ConstantInt::get(Type::getInt64Ty(ctx), struct_type->getNumElements());

    // get element type descriptor values
    std::vector<Value*> args{num_elems};
    for (int i = 0; i < struct_type->getNumElements(); ++i) {
      auto elem_type = struct_type->getElementType(i);
      auto elem_value = get_type_desc(elem_type, builder, type_map);
      args.push_back(elem_value);
    }

    // set struct element types
    auto get_anon_struct_type = module.getOrInsertFunction(
        // TODO make size_t int64 architecture dependent
        symbol_Internal__get_anon_struct_type,
        FunctionType::get(typeDesc_ptr_type, {Type::getInt64Ty(ctx)}, true));

    auto get_anon_struct_type_call = builder.CreateCall(get_anon_struct_type.getFunctionType(),
                                                        get_anon_struct_type.getCallee(), args);
    get_anon_struct_type_call->setTailCall();

    return get_anon_struct_type_call;
  }

  /**
   * Generate instructions to get typeDesc pointer for given struct type
   * based on it being a named or unnamed version.
   * Add internal method prototype to module if it does not exist yet.
   */
  Value* get_struct_type_desc(StructType* struct_type, IRBuilder<>& builder,
                              std::unordered_map<Type*, Value*>& type_map) {
    assert(struct_type);
    if (struct_type->hasName()) {
      return get_named_struct_type_desc(struct_type, builder, type_map);
    } else {
      return get_unnamed_struct_type_desc(struct_type, builder, type_map);
    }
  }

  /**
   * Generate instructions to get typeDesc pointer for given function type
   * depending on return and parameter types.
   * Add internal method prototype to module if it does not exist yet.
   */
  Value* get_function_type_desc(FunctionType* function_type, IRBuilder<>& builder,
                                std::unordered_map<Type*, Value*>& type_map) {
    assert(function_type);
    Type* typeDesc_ptr_type = get_typeDesc_ptr_type();

    // get return type value
    auto return_type = function_type->getReturnType();
    auto return_value = get_type_desc(return_type, builder, type_map);

    auto num_args = ConstantInt::get(Type::getInt64Ty(ctx), function_type->getNumParams());

    // get arg type values
    std::vector<Value*> args{return_value, num_args};
    for (int i = 0; i < function_type->getNumParams(); ++i) {
      auto param_type = function_type->getParamType(i);
      auto arg_value = get_type_desc(param_type, builder, type_map);
      args.push_back(arg_value);
    }

    auto get_function_type = module.getOrInsertFunction(
        // TODO make size_t int64 architecture dependent
        symbol_Internal__get_function_type,
        FunctionType::get(typeDesc_ptr_type, {typeDesc_ptr_type, Type::getInt64Ty(ctx)}, true));

    auto function_desc_type_call = builder.CreateCall(get_function_type.getFunctionType(),
                                                      get_function_type.getCallee(), args);
    function_desc_type_call->setTailCall();
    return function_desc_type_call;
  }

  /**
   * Generate instructions to get typeDesc pointer for given type.
   */
  Value* get_type_desc(Type* type, IRBuilder<>& builder,
                       std::unordered_map<Type*, Value*>& type_map) {
    assert(type);

    if (type_map.find(type) == type_map.end()) {
      if (type->isVoidTy()) {
        type_map[type] = get_base_type_desc(builder, symbol_Internal__get_void_type);

      } else if (type->isIntegerTy(1)) {
        type_map[type] = get_base_type_desc(builder, symbol_Internal__get_i1_type);

      } else if (type->isIntegerTy(8)) {
        type_map[type] = get_base_type_desc(builder, symbol_Internal__get_i8_type);

      } else if (type->isIntegerTy(16)) {
        type_map[type] = get_base_type_desc(builder, symbol_Internal__get_i16_type);

      } else if (type->isIntegerTy(32)) {
        type_map[type] = get_base_type_desc(builder, symbol_Internal__get_i32_type);

      } else if (type->isIntegerTy(64)) {
        type_map[type] = get_base_type_desc(builder, symbol_Internal__get_i64_type);

      } else if (type->isFloatTy()) {
        type_map[type] = get_base_type_desc(builder, symbol_Internal__get_float_type);

      } else if (type->isDoubleTy()) {
        type_map[type] = get_base_type_desc(builder, symbol_Internal__get_double_type);

      } else if (type->isPointerTy()) {
        type_map[type] = get_pointer_type_desc(cast<PointerType>(type), builder, type_map);

      } else if (type->isArrayTy()) {
        type_map[type] = get_array_type_desc(cast<ArrayType>(type), builder, type_map);

      } else if (type->isStructTy()) {
        type_map[type] = get_struct_type_desc(cast<StructType>(type), builder, type_map);

      } else if (type->isFunctionTy()) {
        type_map[type] = get_function_type_desc(cast<FunctionType>(type), builder, type_map);

      } else {
        type_map[type] = get_unknown_type_desc(type, builder);
      }
    }

    return type_map[type];
  }

  /**
   * Initialise the extension point.
   * We need to write this out:
   *   __attribute__((constructor))
   *   void augmentum::<function.name>__init__() {
   *       extension_point = Internal::create_extension_point(
   *           module_name,
   *           function_name,
   *           function_type,
   *           fn_ptr,
   *           original,
   *           extended,
   *           reflect
   *       );
   *   }
   */
  void make_init() {
    assert(extension_point_ptr && fn_ptr && reflect && original && extended);

    // Create the function
    auto name = global_name_fn_qualed("init");
    module.getOrInsertFunction(name, FunctionType::get(Type::getVoidTy(ctx), false));
    auto global_ctor = module.getFunction(name);
    global_ctor->setLinkage(GlobalValue::PrivateLinkage);

    // Create code
    auto bb = BasicBlock::Create(ctx, "", global_ctor);
    IRBuilder<> builder(ctx);
    builder.SetInsertPoint(bb);

    // register global ctor
    appendToGlobalCtors(module, global_ctor, 0, nullptr);

    // Module Name
    auto module_name_global_name = global_name("module", "name");
    auto module_name_data = ConstantDataArray::getString(ctx, module.getName(), true);
    auto module_name_global = module.getNamedGlobal(module_name_global_name);
    if (module_name_global == nullptr) {
      module_name_global =
          new GlobalVariable(module, module_name_data->getType(), true, GlobalValue::PrivateLinkage,
                             module_name_data, module_name_global_name);
    }
    auto zero = ConstantInt::getSigned(Type::getInt32Ty(ctx), 0);
    auto module_name_access = ConstantExpr::getInBoundsGetElementPtr(
        module_name_data->getType(), module_name_global, ArrayRef<Constant*>({zero, zero}));

    // Name
    auto name_data = ConstantDataArray::getString(ctx, function.getName(), true);
    auto name_global = new GlobalVariable(module, name_data->getType(), true,
                                          GlobalValue::PrivateLinkage, name_data);
    auto name_access = ConstantExpr::getInBoundsGetElementPtr(name_data->getType(), name_global,
                                                              ArrayRef<Constant*>({zero, zero}));

    // TypeDesc
    std::unordered_map<Type*, Value*> type_map;
    auto function_type = function.getFunctionType();
    auto function_type_desc = get_type_desc(function_type, builder, type_map);

    // Cast original and extended to their 'typeless forms', i.e. void(*)()
    auto fn_ptr_type = FunctionType::get(void_type, false)->getPointerTo();
    auto original_erased = ConstantExpr::getBitCast(original, fn_ptr_type);
    auto extended_erased = ConstantExpr::getBitCast(extended, fn_ptr_type);

    // Create the extension point
    auto create_extension_point =
        module.getOrInsertFunction(symbol_Internal__create_extension_point,  // function name
                                   extension_point_ptr->getType()->getElementType(),  // return type
                                   Type::getInt8PtrTy(ctx),        // arg0 char* module_name
                                   Type::getInt8PtrTy(ctx),        // arg1 char* name
                                   function_type_desc->getType(),  // arg2
                                   fn_ptr->getType(),              // arg3
                                   original_erased->getType(),     // arg4
                                   extended_erased->getType(),     // arg5
                                   reflect->getType()              // arg6
        );
    auto call = builder.CreateCall(create_extension_point.getFunctionType(),
                                   create_extension_point.getCallee(),
                                   {module_name_access, name_access, function_type_desc, fn_ptr,
                                    original_erased, extended_erased, reflect},  // args
                                   "extension_point"                             // result_name
    );
    call->setTailCall();
    builder.CreateStore(call, extension_point_ptr);
    builder.CreateRetVoid();
  }
};

/**
 * The pass
 */
struct Augmentum : public ModulePass {
  static char ID;
  Augmentum()
      : ModulePass(ID),
        stats(),
        record_stats(StatsDirectory != ""),
        emit_llvm(EmitIRDirectory != "") {
    should_instrument = get_should_instrument();

    if (DryRun) {
      stats.collect_full_stats();
    }
  }

  bool runOnModule(Module& module) override {
    bool transformed;
    if (DryRun) {
      transformed = collect_function_stats(module);
    } else {
      transformed = run_instrumentation(module);
    }

    if (record_stats) {
      std::string prefix = module.getName().str();
      std::replace(prefix.begin(), prefix.end(), '/', '_');
      std::replace(prefix.begin(), prefix.end(), '.', '_');

      stats.emit_statistics(StatsDirectory, prefix);
    }

    if (emit_llvm && transformed) {
      emit_IR(module, EmitIRDirectory);
    }

    return transformed;
  }

 private:
  InstrumentationStats stats;
  bool record_stats;
  bool emit_llvm;
  std::unique_ptr<ShouldInstrument> should_instrument;

  /**
   * Get the ShouldInstrument call back
   */
  std::unique_ptr<ShouldInstrument> get_should_instrument() {
    std::unique_ptr<ShouldInstrument> ptr;
    if (PythonScript != "") {
      ptr = get_python_should_instrument(PythonScript);
    } else {
      if (TargetFunctions != "") {
        ptr = std::make_unique<TargetedInstrument>(TargetFunctions);
      } else {
        ptr = std::make_unique<AlwaysInstrument>();
      }

      // XXX project specific should instrument heuristic
      // ptr = std::make_unique<HeuristicDetector>();
    }
    return ptr;
  }

  bool run_instrumentation(Module& module) {
    // errs() << "DEBUG: checking module " << module.getName() << "\n";

    int transformed_functions = 0;
    if (should_instrument->module(module)) {
      // clone module functions before instrumentation
      // to avoid instrumenting generated functions
      // TODO use vector ctor and iterators begin and end
      std::vector<Function*> funs_cpy;
      for (Function& function : module.getFunctionList()) {
        funs_cpy.push_back(&function);
      }

      // instrument module functions
      for (Function* function_ptr : funs_cpy) {
        // errs() << "DEBUG: checking function " << function_ptr->getName() <<
        // "\n";

        AugmentumFunction auto_function(*function_ptr, *should_instrument);
        if (auto_function.transform()) {
          transformed_functions++;

          if (record_stats) {
            stats.record_function_stats(module, *function_ptr);
          }
        }
      }
    }
    return transformed_functions > 0;
  }

  /**
   * This function is meant for debug purposes. It gathers
   * statistics on instrumented and not instrumented functions
   * as well as corresponding types.
   *
   * It does not perform any transformations to the module
   * or its functions.
   */
  bool collect_function_stats(Module& module) {
    if (record_stats) {
      // collect module function stats
      for (Function& function : module.getFunctionList()) {
        // get decision information on whether we can and should instument this
        // module and function
        auto can_id = can_be_instrumented(function);
        auto should_info = should_instrument->get_decision_info(module, function);
        auto instr_info = std::make_pair(can_id_to_string(can_id), should_info);
        stats.record_function_stats(module, function, instr_info);
      }

      // record named struct stats based on the structs you have serialised for
      // all recorded functions
      stats.record_named_struct_stats(module);
    }
    return false;
  }

  std::string can_id_to_string(CanInstrumentID can_id) {
    switch (can_id) {
      case CAN_NA:
        return "NA";
      case CAN_INSTRUMENT:
        return "instrument";
      case CAN_NOT_DECL:
        return "not_decl";
      case CAN_NOT_VARARGS:
        return "not_varargs";
      default:
        return "NA";
    }
  }

  /**
   * Emit llvm IR of the current module to specified directory.
   */
  void emit_IR(const Module& module, const std::string& outDir) const {
    std::filesystem::path outDirP = outDir;
    if (std::filesystem::exists(outDirP)) {
      std::error_code EC;
      std::string mname = module.getName().str();
      std::replace(mname.begin(), mname.end(), '/', '_');
      std::string moduleOutFile = (outDirP / mname).string() + ".ll";
      llvm::raw_fd_ostream moduleOut(moduleOutFile, EC);
      module.print(moduleOut, nullptr);
    } else {
      errs() << "ERROR: [augmentum] opening output stream to emit module IR "
                "code failed. Path not found: "
             << outDirP << "\n";
    }
  }
};

// Telling LLVM about the pass.
char Augmentum::ID = 0;
static RegisterPass<Augmentum> X("augmentum", "Augmentum Pass");

static RegisterStandardPasses Y(PassManagerBuilder::EP_ModuleOptimizerEarly,
                                [](const PassManagerBuilder& builder,
                                   legacy::PassManagerBase& pass_manager) {
                                  pass_manager.add(new Augmentum());
                                });
}  // namespace llvmpass
}  // namespace augmentum
