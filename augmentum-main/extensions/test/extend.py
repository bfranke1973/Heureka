# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import augmentum

print("The extend script is running!")


def add_two(pt, ret, *args):
    print("AddTwo Advice call ...")
    ret.value += 2


augmentum.extend_after(add_two, name_pred="_Z3addii")
