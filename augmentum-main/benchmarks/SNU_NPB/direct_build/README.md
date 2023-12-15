The build process in this directory allows NAS benchmarks to be built in a way where object files are build for individual benchmarks. A different compiler can be used for object file generation and final linking.

The build process allows for verification files to be build using a vanilla compiler before being linked into the final binary. This way modifications will not affect verification code.

For test purposes, the ```build_all.sh``` script can be used to build all NAS benchmarks using the ```build.sh``` script. 
It builds a baseline using only the vanillla clang compiler and an augmentum version using a modified compiler for object file generation and a vanilla compiler for final linking. 

The vanilla and modified compilers must be specified in the env.config.

Extension libraries do not need to be loaded but can be configured using the EXTENSIONS variable in ```build_all.sh```.
