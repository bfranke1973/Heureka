# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
define HELP
Available targets:

Basic Commands
--------------

    make all
        Build the native compiled code and install Python dependencies.

    make test
        Run the unit tests.

Tidying up
-----------

    make clean
        Remove build artifacts.

endef
export HELP

.DEFAULT_GOAL := help

# This project name.
PROJECT := augmentum

# The path of the repository root.
SOURCE_ROOT := $(realpath $(dir $(realpath $(firstword $(MAKEFILE_LIST)))))

# Output and installation directories.
BUILD_DIR ?= /dev/shm/$(USER)/$(PROJECT)/build

# Configurable paths to binaries.
CMAKE ?= cmake
RM ?= rm
PYTHON ?= python

# Building the code.

all: $(BUILD_DIR)/requirements.txt
	$(CMAKE) \
		-S $(SOURCE_ROOT) \
		-B $(BUILD_DIR) \
		-DCMAKE_INSTALL_PREFIX=$(SOURCE_ROOT)/driver
	$(CMAKE) --build $(BUILD_DIR) --parallel $(shell nproc)
	$(CMAKE) --install $(BUILD_DIR) --config Release

clean:
	$(RM) -rf $(BUILD_DIR)
	$(RM) -rf $(SOURCE_ROOT)/driver/bin $(SOURCE_ROOT)/driver/native
	$(RM) -rf $(SOURCE_ROOT)/driver/test/native

# Tests.

test: install-test-requirements
	cd driver && $(PYTHON) -m unittest discover --start-directory test -v $(UNITTEST_ARGS)

install-test-requirements: $(BUILD_DIR)/requirements-test.txt

# Utility targets.

.PHONY: help

help:
	@echo "$$HELP"


# Install python dependencies.

$(BUILD_DIR)/requirements.txt: $(SOURCE_ROOT)/requirements.txt
	mkdir -pv $(BUILD_DIR)
	cp -v $< $@
	$(PYTHON) -m pip install -r $@

$(BUILD_DIR)/requirements-test.txt: $(SOURCE_ROOT)/driver/test/requirements.txt
	mkdir -pv $(BUILD_DIR)
	cp -v $< $@
	$(PYTHON) -m pip install -r $@
