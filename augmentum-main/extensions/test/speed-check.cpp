/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <stdio.h>

extern int add(int a, int b);

int main(int argc, char* argv[]) {
  unsigned long long t0 = __builtin_readcyclecounter();
  int a = 0;
  while (a < 1000000000) a = add(a, 1);
  unsigned long long t1 = __builtin_readcyclecounter();
  printf("Cycles %lld. Result %d\n", t1 - t0, a);

  return 0;
}
