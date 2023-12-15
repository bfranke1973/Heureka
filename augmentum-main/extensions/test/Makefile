# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

BUILD_DIR=../../build
LLVM_DIR=/Users/${USER}/Documents/code/AutoSquared/llvm-project/install
CLANG=${LLVM_DIR}/bin/clang++
OPT=${LLVM_DIR}/bin/opt
LLC=${LLVM_DIR}/bin/llc
AUGMENTUM=../augmentum
AUGMENTUM_LLVMPASS=${BUILD_DIR}/extensions/augmentum_llvmpass/libaugmentum_llvmpass.so

run: run-instrumented-with-python # run-explicit run-instrumented-with-none

pass:
	(cd ${BUILD_DIR} && make)

run-explicit:
	(cd ${BUILD_DIR} && make explicit)
	echo ************************************************
	echo RUNNING explicit
	${BUILD_DIR}/extensions/test/explicit
	echo ************************************************

run-instrumented-with-none:
	(cd ${BUILD_DIR} && make instrumented-with-none
	echo ************************************************
	echo RUNNING instrumented-with-none
	${BUILD_DIR}/extensions/test/instrumented-with-none
	echo ************************************************

run-instrumented-with-python:
	(cd ${BUILD_DIR} && make instrumented-with-python)
	echo ************************************************
	echo RUNNING instrumented-with-python
	AUGMENTUM_PYTHON=extend ${BUILD_DIR}/extensions/test/instrumented-with-python
	echo ************************************************


#instrumented-python: instrumented.o ${AUGMENTUM}/augmentum.cpp ${AUGMENTUM}/python.cpp driver.cpp
#	clang++ -g -std=c++17 -I${AUGMENTUM} -I../../extern/pybind11/include -I/opt/homebrew/Cellar/python38/3.8.3_1/Frameworks/Python.framework/Versions/3.8/include/python3.8/ $^ -o $@
#
#instrumentation.ll: instrumentation.cpp
#	clang++ -std=c++17 -I${AUGMENTUM} -emit-llvm -S -O3 -fno-inline $< -o $@
#
#speed-check-uninstrumented: speed-check.cpp uninstrumented.ll
#	clang++ -std=c++17 -O3 $^ -o $@
#
#speed-check-instrumented: speed-check.cpp instrumented.ll ${AUGMENTUM}/augmentum.cpp
#	clang++ -std=c++17 -O3 -std=c++17 -I${AUGMENTUM} $^ -o $@
#
#speed-check: speed-check-uninstrumented speed-check-instrumented
#	echo 'Uninstrumented: \c'
#	./speed-check-uninstrumented
#	echo 'Instrumented: \c'
#	./speed-check-instrumented
#
#python-instrumented.ll: uninstrumented.ll
#	${OPT} -load ${AUGMENTUM_LLVMPASS} -augmentum -augmentum-python should_instrument -S $< -o $@


clean:
	(cd ${BUILD_DIR} && make clean)

.PHONY: clean make_pass
