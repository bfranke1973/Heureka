# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# CMakeLists.txt
add_library(stlwrapper SHARED stlwrapper.c)
set_property(TARGET stlwrapper PROPERTY POSITION_INDEPENDENT_CODE ON) # -fPIC
target_link_libraries(stlwrapper ${CMAKE_DL_LIBS})

install(TARGETS stlwrapper DESTINATION native)
