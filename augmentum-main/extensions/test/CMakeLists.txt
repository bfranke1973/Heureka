# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

set(clang++ ${LLVM_DIR}/../../../bin/clang++)
set(opt ${LLVM_DIR}/../../../bin/opt)
set(opt-augmentum
    ${opt}
    -load
    ${CMAKE_BINARY_DIR}/extensions/augmentum_llvmpass/libaugmentum_llvmpass.so
    -augmentum
)

# set RPATH for installed augmentum library so installed test binaries can find it
set(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_PREFIX}/native")

# Build extension implementations as dynamic library
add_library(extend SHARED extend.cpp)
target_link_libraries(extend PRIVATE augmentum)

# Build instrumented versions using instrumenter pass
add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/uninstrumented.ll
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/to-instrument.cpp
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMAND ${clang++} -fPIE -O3 -emit-llvm -S $< -o $@
)
add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/uninstrumented.o
    DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/uninstrumented.ll
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMAND ${clang++} -fPIE -c $< -o $@
)

add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/instrumented.ll
    DEPENDS augmentum_llvmpass
    DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/uninstrumented.ll
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMAND ${opt-augmentum} -S $< -o $@
)
add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/instrumented.o
    DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/instrumented.ll
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMAND ${clang++} -fPIE -c $< -o $@
)

add_executable(
    uninstrumented
    driver.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/uninstrumented.o
)

add_executable(
    instrumented-with-none
    driver.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/instrumented.o
)
target_link_libraries(instrumented-with-none PRIVATE augmentum)

# TODO link in extend library instead of including source here
add_executable(
    instrumented-with-c
    driver-instrumented.cpp
    extend.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/instrumented.o
)
target_link_libraries(instrumented-with-c PRIVATE augmentum)

add_executable(
    instrumented-with-python
    driver-instrumented.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/instrumented.o
)
target_link_libraries(instrumented-with-python PRIVATE augmentum)

# Explicit is supposed to do the same thing without using the instrumenter.
if(APPLE)
    add_custom_command(
        OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/explicit.ll
        DEPENDS ${CMAKE_SOURCE_DIR}/extensions/augmentum/augmentum.h
        DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/explicit.cpp
        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
        COMMAND
            /Library/Developer/CommandLineTools/usr/bin/c++ -O3 -std=c++17
            -emit-llvm -S -I${CMAKE_SOURCE_DIR}/extensions/augmentum -isysroot
            /Library/Developer/CommandLineTools/SDKs/MacOSX10.15.sdk $< -o $@
    )
else()
    add_custom_command(
        OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/explicit.ll
        DEPENDS ${CMAKE_SOURCE_DIR}/extensions/augmentum/augmentum.h
        DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/explicit.cpp
        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
        COMMAND
            ${clang++} -fPIE -O3 -std=c++17 -emit-llvm -S
            -I${CMAKE_SOURCE_DIR}/extensions/augmentum $< -o $@
    )
endif()

add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/explicit.o
    DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/explicit.ll
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMAND ${clang++} -fPIE -c $< -o $@
)
# TODO link in extend library instead of including source here
add_executable(
    explicit
    driver-instrumented.cpp
    extend.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/explicit.o
)
target_link_libraries(explicit PRIVATE augmentum)

# Copy test executables to test directory.
install(
    TARGETS
        uninstrumented
        instrumented-with-none
        instrumented-with-c
        instrumented-with-python
        explicit
        extend
    DESTINATION test/native
)
# Copy extension files for python interface
install(FILES extend.py extend_listener.py DESTINATION test/native)
