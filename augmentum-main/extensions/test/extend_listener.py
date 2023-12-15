# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import augmentum
from augmentum import I32

print("The extend_listener script is running!")


class BumpListener(augmentum.Listener):
    """
    This class is intended to demonstrate the API.
    It prints values and mmodifies the results,
    also it calls the original functions
    """

    def __init__(self):
        super().__init__()

    # This method is called when a new extension point is found
    def on_extension_point_register(self, pt):
        print("py on_extension_point_register", pt)

        # We'll just stick to 32 bit int types
        if pt.return_type.signature == "i32":
            # Print arguments before
            def before(pt, args):
                print("before", pt, list(map(str, args)))

            pt.extend_before(before)

            # Show a couple of ways to
            def around(pt, handle, ret, args):
                # Typical use
                pt.call_previous(handle, ret, *args)
                ret.value += 1

                # Atypical use - putting in new values for everything
                # This time, we have to know the types
                if pt.signature == "i32 (i32, i32)":
                    r = pt.call_previous(handle, I32(), I32(101), I32(10))
                    ret.value += r.value

            pt.extend_around(around)

            # Print the result and change the value
            def after(pt, ret, args):
                ret.value += 1
                print("after", pt, ret, list(map(str, args)))

            pt.extend_after(after)

    def on_extension_point_unregister(self, pt):
        print("py on_extension_point_unregister", pt)


BumpListener()
