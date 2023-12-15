# Augmentum Function Instrumentation

The Augmentum function instrumentation library constist in the following modules:

- ```extension```: contains extension library and source instrumentation pass
- ```driver```: contains driver framework to interact with instrumented software
- ```extern```: contains required external projects


## Extension Framework and Instrumenter

This is a framework and compiler pass to instrument functions of a software project with extension points when building with an llvm toolchain. They can be found in the ```extensions``` directory.

See ```INSTALL.md``` on how to build library and dependencies.

## Instrumentation Driver

The Driver is an example setup of how the instrumentation can be used in a compiler system software to evaluate individual compiler functions. It can be found in the ```driver``` directory.

See how to setup the driver software packages using a Conda environment in ```INSTALL.md```.

### Configuration

A configuration file is used to specify which system program to analyse and where required tools and benchmarks can be found. ```driver/config/evaluation_config.json.template``` is provided as an example.

This config file has four parts:

1. General options (copy program sources upon driver startup or use configured path)
2. Tool options (configuration of llvm binaries and augmentum library)
3. System program to be evaluated
4. Benchmarks to be used

The system program section has different preconfigured sections to chose from which can be activated with the ```active``` parameter.

The benchmarks also have different preconfigured sections which can be activated in the same way.

### Execution

The ```scripts``` folder contains contains ```run_evaluation.sh``` as an example on how to execute the driver.

### Tests

A range of unit tests are provided for some modules. They can be executed with ```driver/run_tests.sh```.

### Additional Tools

```benchmark_profiler.py``` is a tool to evaluate a given benchmark against an instrumented system program in order to gather a trace of instrumented functions which are executed by the tested benchmarks.

## Benchmarks

The ```benchmarks``` folder provides three benchmarks to test against the instrumented compiler:

1. llvm-test is a selection of llvm unit tests taken from the llvm test suite.
2. SNU_NPB is the NAS Parallel Benchmark Suit implemented in C.
3. POLYBENCH contains all benchmarks from the polybench benchmark suite.

To include new benchmarks [benchmarks.py](driver/augmentum/benchmarks.py) and the ```evaluation_config.json``` need to be modified accordingly.
