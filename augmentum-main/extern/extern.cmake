# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

include(ExternalProject)
include(FetchContent)

# === pybind ====

fetchcontent_declare(
    pybind11
    "${CMAKE_CURRENT_BINARY_DIR}/extern/pybind11"
    GIT_REPOSITORY "https://github.com/pybind/pybind11.git"
    GIT_TAG v2.10.1
)
fetchcontent_makeavailable(pybind11)
