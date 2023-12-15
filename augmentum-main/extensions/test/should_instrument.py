# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


def should_instrument_module(module):
    name = module.get_name()
    print(f"{module} python calling should_instrument_module({name})")
    return True


def should_instrument_function(function):
    print(
        f"{function} python calling "
        f"should_instrument_function({function.get_parent().get_name()}"
        f"::{function.get_name()}: {function.get_signature()})"
    )
    return False
