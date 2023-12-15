/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "type_serialisation.h"

#include <string>

#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Type.h"
#include "llvm/Support/raw_ostream.h"
#include "utils.h"

using namespace llvm;

namespace augmentum {
namespace llvmpass {

std::string TypeSerialiser::serialise_type(const Module& module, const Function& function,
                                           Type* type, SerialisationContext ctx) {
  std::pair<Type*, SerialisationContext> ctx_type = std::make_pair(type, ctx);
  // we have not seen this type yet or we are on function level
  if (ctx == FUNCTION || type_lookup.find(ctx_type) == type_lookup.end()) {
    if (type->isVoidTy()) {
      type_lookup[ctx_type] = "void";

    } else if (type->isIntegerTy(1)) {
      type_lookup[ctx_type] = "i1";

    } else if (type->isIntegerTy(8)) {
      type_lookup[ctx_type] = "i8";

    } else if (type->isIntegerTy(16)) {
      type_lookup[ctx_type] = "i16";

    } else if (type->isIntegerTy(32)) {
      type_lookup[ctx_type] = "i32";

    } else if (type->isIntegerTy(64)) {
      type_lookup[ctx_type] = "i64";

    } else if (type->isFloatTy()) {
      type_lookup[ctx_type] = "f32";

    } else if (type->isDoubleTy()) {
      type_lookup[ctx_type] = "f64";

    } else if (type->isPointerTy()) {
      std::string serial_element_type =
          serialise_type(module, function, cast<PointerType>(type)->getElementType());
      if (ctx != BYVAL_ARG) {
        serial_element_type += "*";
      }
      type_lookup[ctx_type] = serial_element_type;

    } else if (type->isArrayTy()) {
      ArrayType* artype = cast<ArrayType>(type);
      std::string serialisation = "[ ";
      serialisation += std::to_string(artype->getNumElements());
      serialisation += " x ";
      serialisation += serialise_type(module, function, artype->getElementType());
      return serialisation + " ]";

    } else if (type->isStructTy()) {
      StructType* stype = cast<StructType>(type);

      auto serialise_struct_elements = [this, stype](const Module& module,
                                                     const Function& function) -> std::string {
        std::string serialisation = "{ ";
        for (int i = 0; i < stype->getNumElements(); ++i) {
          serialisation += serialise_type(module, function, stype->getElementType(i));
          if (i < stype->getNumElements() - 1) {
            serialisation += ", ";
          }
        }
        return serialisation + " }";
      };

      if (stype->hasName()) {
        std::string struct_name =
            "@% " + module.getName().str() + "::" + stype->getName().str() + " %@";
        type_lookup[ctx_type] = struct_name;
        named_structs_lookup[struct_name] = {serialise_struct_elements(module, function), stype};

      } else {
        type_lookup[ctx_type] = serialise_struct_elements(module, function);
      }

    } else if (type->isFunctionTy()) {
      FunctionType* ftype = cast<FunctionType>(type);
      std::string serialisation = "@$ " + serialise_type(module, function, ftype->getReturnType());

      // DEBUG: look for readonly and readnone attributes
      // if (ctx == FUNCTION) {
      //     bool print = false;
      //     for (int i = 0; i < ftype->getNumParams(); ++i) {
      //         if (function.getArg(i)->hasAttribute(Attribute::ReadNone) ||
      //             function.getArg(i)->hasAttribute(Attribute::ReadOnly)) {
      //             print = true;
      //             break;
      //         }
      //     }
      //     if (print) {
      //         errs() << function.getName() << "\n";
      //         print_attribute_list(errs(), function.getAttributes());
      //     }
      // }

      for (int i = 0; i < ftype->getNumParams(); ++i) {
        SerialisationContext arg_ctx = NA;
        if (ctx == FUNCTION && function.getArg(i)->hasAttribute(Attribute::ByVal)) {
          arg_ctx = BYVAL_ARG;
        }
        serialisation += ", " + serialise_type(module, function, ftype->getParamType(i), arg_ctx);
      }
      type_lookup[ctx_type] = serialisation + " $@";

    } else {
      type_lookup[ctx_type] = "@U" + type_to_string(type) + "U@";
    }
  }

  return type_lookup[ctx_type];
}
}  // namespace llvmpass
}  // namespace augmentum
