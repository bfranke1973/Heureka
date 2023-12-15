# STL Wrapper Library

This library is used to wrap around standard library functions for c++ programs in order to manipulate them or trace their calls.

To use, preload library when running your binary.

```bash
$ LD_PRELOAD=${AUGMENTUM_BUILD}/tools/stlwrapper/libstlwrapper.so ./my_command.out
```
