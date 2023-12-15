#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

rm -rf augmentum_bins vanilla_bins build
rm -rf ../NPB3.3-SER-C/sys/setparams

cd ../NPB3.3-SER-C
./clean.sh