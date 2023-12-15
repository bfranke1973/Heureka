This folder contains scripts and data files added to support the augmentum project. They are not part of the original polybench project.

create env.config as required and specify at least vanilla compiler binary

use ```./build_all.sh``` to build all polybench benchmarks

use ```./generate_verification.sh <path/to/polybench/binaries> <path/to/stl_wrapper.so>``` script to generate verification strings for polybench output
ATTENTION: lots of files generated, execute in separate directory

use ```./clean.sh``` to clean up
