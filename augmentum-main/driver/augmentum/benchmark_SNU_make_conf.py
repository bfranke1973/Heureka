# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from pathlib import Path

def get_SNU_make_conf(clang_bin : Path, compiler_flags : str, linker_flags : str) -> str:
    return \
f"""
#---------------------------------------------------------------------------
#
#                SITE- AND/OR PLATFORM-SPECIFIC DEFINITIONS. 
#
#---------------------------------------------------------------------------

#---------------------------------------------------------------------------
# Items in this file will need to be changed for each platform.
#---------------------------------------------------------------------------

#---------------------------------------------------------------------------
# Parallel Fortran:
#
# For CG, EP, FT, MG, LU, SP, BT and UA, which are in Fortran, the following 
# must be defined:
#
# F77        - Fortran compiler
# FFLAGS     - Fortran compilation arguments
# F_INC      - any -I arguments required for compiling Fortran 
# FLINK      - Fortran linker
# FLINKFLAGS - Fortran linker arguments
# F_LIB      - any -L and -l arguments required for linking Fortran 
# 
# compilations are done with $(F77) $(F_INC) $(FFLAGS) or
#                            $(F77) $(FFLAGS)
# linking is done with       $(FLINK) $(F_LIB) $(FLINKFLAGS)
#---------------------------------------------------------------------------

#---------------------------------------------------------------------------
# This is the fortran compiler used for Fortran programs
#---------------------------------------------------------------------------
F77 = gfortran

#---------------------------------------------------------------------------
# This links fortran programs; usually the same as ${{F77}}
#---------------------------------------------------------------------------
FLINK	= $(F77)

#---------------------------------------------------------------------------
# These macros are passed to the linker 
#---------------------------------------------------------------------------
F_LIB  =

#---------------------------------------------------------------------------
# These macros are passed to the compiler 
#---------------------------------------------------------------------------
F_INC =

#---------------------------------------------------------------------------
# Global *compile time* flags for Fortran programs
#---------------------------------------------------------------------------
FFLAGS	= -O3 -mcmodel=medium

#---------------------------------------------------------------------------
# Global *link time* flags. Flags for increasing maximum executable 
# size usually go here. 
#---------------------------------------------------------------------------
FLINKFLAGS = -O3 -mcmodel=medium


#---------------------------------------------------------------------------
# Parallel C:
#
# For IS and DC, which are in C, the following must be defined:
#
# CC         - C compiler 
# CFLAGS     - C compilation arguments
# C_INC      - any -I arguments required for compiling C 
# CLINK      - C linker
# CLINKFLAGS - C linker flags
# C_LIB      - any -L and -l arguments required for linking C 
#
# compilations are done with $(CC) $(C_INC) $(CFLAGS) or
#                            $(CC) $(CFLAGS)
# linking is done with       $(CLINK) $(C_LIB) $(CLINKFLAGS)
#---------------------------------------------------------------------------

#---------------------------------------------------------------------------
# This is the C compiler used for C programs
#---------------------------------------------------------------------------
CC = {clang_bin}

#---------------------------------------------------------------------------
# This links C programs; usually the same as ${{CC}}
#---------------------------------------------------------------------------
CLINK	= $(CC)

#---------------------------------------------------------------------------
# These macros are passed to the linker 
#---------------------------------------------------------------------------
C_LIB  = -lm

#---------------------------------------------------------------------------
# These macros are passed to the compiler 
#---------------------------------------------------------------------------
C_INC = -I../common

#---------------------------------------------------------------------------
# Global *compile time* flags for C programs
# DC inspects the following flags (preceded by "-D"):
#
# IN_CORE - computes all views and checksums in main memory (if there is 
# enough memory)
#
# VIEW_FILE_OUTPUT - forces DC to write the generated views to disk
#
# OPTIMIZATION - turns on some nonstandard DC optimizations
#
# _FILE_OFFSET_BITS=64 
# _LARGEFILE64_SOURCE - are standard compiler flags which allow to work with 
# files larger than 2GB.
#---------------------------------------------------------------------------
CFLAGS	= -Wall -mcmodel=medium {compiler_flags}

#---------------------------------------------------------------------------
# Global *link time* flags. Flags for increasing maximum executable 
# size usually go here. 
#---------------------------------------------------------------------------
CLINKFLAGS = -mcmodel=medium {linker_flags}


#---------------------------------------------------------------------------
# Utilities C:
#
# This is the C compiler used to compile C utilities.  Flags required by 
# this compiler go here also; typically there are few flags required; hence 
# there are no separate macros provided for such flags.
#---------------------------------------------------------------------------
UCC	= gcc


#---------------------------------------------------------------------------
# Destination of executables, relative to subdirs of the main directory. . 
#---------------------------------------------------------------------------
BINDIR	= ../bin


#---------------------------------------------------------------------------
# The variable RAND controls which random number generator 
# is used. It is described in detail in README.install. 
# Use "randi8" unless there is a reason to use another one. 
# Other allowed values are "randi8_safe", "randdp" and "randdpvec"
#---------------------------------------------------------------------------
#RAND   = randi8
# The following is highly reliable but may be slow:
RAND   = randdp


#---------------------------------------------------------------------------
# The variable WTIME is the name of the wtime source code module in the
# common directory.  
# For most machines,       use wtime.c
# For SGI power challenge: use wtime_sgi64.c
#---------------------------------------------------------------------------
WTIME  = wtime.c


#---------------------------------------------------------------------------
# Enable if either Cray or IBM: 
# (no such flag for most machines: see common/wtime.h)
# This is used by the C compiler to pass the machine name to common/wtime.h,
# where the C/Fortran binding interface format is determined
#---------------------------------------------------------------------------
# MACHINE	=	-DCRAY
# MACHINE	=	-DIBM
"""