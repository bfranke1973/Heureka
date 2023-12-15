# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# extensions/augmentum/CMakeLists.txt
find_package(LLVM 10.0.1 REQUIRED CONFIG)
include_directories(${LLVM_INCLUDE_DIRS})

execute_process(
    COMMAND bash -c "echo LLVM include director used: ${LLVM_INCLUDE_DIRS}"
)

if(NOT LLVM_ENABLE_RTTI)
    message(
        FATAL_ERROR
        "LLVM_ENABLE_RTTI is No. Pybind will need it. Please rebuild LLVM with RTTI and Exceptions"
    )
    # set_target_properties(augmentum_llvmpass PROPERTIES COMPILE_FLAGS "-fno-rtti")
endif()
if(NOT LLVM_ENABLE_EH)
    message(
        FATAL_ERROR
        "LLVM_ENABLE_EH is No. Pybind will need it. Please rebuild LLVM with RTTI and Exceptions."
    )
endif()

add_library(
    augmentum_llvmpass
    MODULE
    augmentum_llvmpass.cpp
    python.cpp
    utils.cpp
    instrumentation_stats.cpp
    should_instrument.cpp
    should_instrument_prior.cpp
    type_serialisation.cpp
)
target_link_libraries(augmentum_llvmpass PRIVATE pybind11::embed)
if(APPLE)
    set_target_properties(
        augmentum_llvmpass
        PROPERTIES LINK_FLAGS "-undefined dynamic_lookup"
    )
endif(APPLE)

install(TARGETS augmentum_llvmpass DESTINATION native)
