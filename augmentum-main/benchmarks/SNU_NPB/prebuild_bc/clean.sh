#!/bin/bash
# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

rm -rf bc_out build augmentum_bins vanilla_bins
rm -rf ../NPB3.3-SER-C/sys/setparams

for i in `find ../NPB3.3-SER-C -name "npbparams.h"`; do 
    rm $i
done
