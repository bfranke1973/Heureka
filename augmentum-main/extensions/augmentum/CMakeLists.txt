# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# extensions/augmentum/CMakeLists.txt
add_library(augmentum SHARED augmentum.cpp type.cpp internal.cpp python.cpp)

target_include_directories(augmentum PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(augmentum PRIVATE pybind11::embed)

set_target_properties(augmentum PROPERTIES PUBLIC_HEADER "augmentum.h;type.h")
install(
    TARGETS augmentum
    LIBRARY
    DESTINATION native
    PUBLIC_HEADER
    DESTINATION native/include
)
