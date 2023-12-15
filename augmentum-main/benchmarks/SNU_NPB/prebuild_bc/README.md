The build process in this directory allows NAS benchmarks to be built in a way where all object files are compiled into bitcode and linked into one big bitcode file using a vanilla clang compiler without optimisations.

The vanilla compiler can be specified in the env.config which is needed for both scripts.

For test purposes, the binaries can be build as well which can be done with a vanilla optimiser or an instrumented one. Extension libraries do not need to be loaded but can be configured using the OPT_FLAGS variable.
