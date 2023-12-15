/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <stdio.h>

#include <cassert>

#include "to-instrument.h"

// TODO use this std::numeric_limits<double>::epsilon()
// https://en.cppreference.com/w/cpp/types/numeric_limits/epsilon
#define EPSILON 0.0001

void testBase() {
  int resA = add(10, 20);
  int resB = add(100, 200);

  printf("add(10, 20) = %d\n", resA);
  printf("add(100, 200) = %d\n", resB);

#ifdef INSTRUMENTED
  assert(resA == 32);
  assert(resB == 302);
#else
  assert(resA == 30);
  assert(resB == 300);
#endif
}

void testIntTypes() {
  long resA = intTypeTest(true, 10, 20, 30);
  long resB = intTypeTest(false, 30, 20, 10);

  printf("testIntType(true,10,20,30) = %ld\n", resA);
  printf("testIntType(false,30,20,10) = %ld\n", resB);

#ifdef INSTRUMENTED
  assert(resA == 62);
  assert(resB == 2);
#else
  assert(resA == 60);
  assert(resB == 0);
#endif
}

void testFloatTypes() {
  double resA = floatTypeTest(0.5, 5.5);
  double resB = floatTypeTest(0.34, 0.16);

  printf("floatTypeTest(0.5,5.5) = %f\n", resA);
  printf("floatTypeTest(0.34,0.16) = %f\n", resB);

#ifdef INSTRUMENTED
  assert(resA > 8.0 - EPSILON && resA < 8.0 + EPSILON);
  assert(resB > 2.5 - EPSILON && resB < 2.5 + EPSILON);
#else
  assert(resA > 6.0 - EPSILON && resA < 6.0 + EPSILON);
  assert(resB > 0.5 - EPSILON && resB < 0.5 + EPSILON);
#endif
}

void testPointerTypes() {
  int i = 5;
  double d = 3.0;
  int* ri;
  ri = pointerTypeTest(&i, &d);

  printf("pointerTypeTest(&5,&3.0) = %d, i: %d, d: %f\n", *ri, i, d);

#ifdef INSTRUMENTED
  assert(*ri == 8);  // one from AddOnePointer and one from AddOneFirstParameter
  assert(i == 8);
  assert(d > 2.0 - EPSILON && d < 2.0 + EPSILON);
#else
  assert(*ri == 6);
  assert(i == 6);
  assert(d > 2.0 - EPSILON && d < 2.0 + EPSILON);
#endif
}

void testVoidTypes() {
  int i = 10;
  voidTypeTest(&i);
  printf("voidTypeTest(&10), i: %d\n", i);

#ifdef INSTRUMENTED
  assert(i == 12);
#else
  assert(i == 11);
#endif
}

void testStructTypes() {
  Result r = structTypeTest(10, 20);
  printf("structTypeTest(10, 20) = {%ld,%f}\n", r.resl, r.resd);

#ifdef INSTRUMENTED
  assert(r.resl == 11);
  assert(r.resd > 30.0 - EPSILON && r.resd < 30.0 + EPSILON);
#else
  assert(r.resl == 10);
  assert(r.resd > 30.0 - EPSILON && r.resd < 30.0 + EPSILON);
#endif
}

void testForwardStructTypes() {
  Node* head = new Node(1);
  Node* res = namedStructTypeTest(head, 2);
  printf("namedStructTypeTest(Node{1}, 2) = Node{%d}\n", res->data);

#ifdef INSTRUMENTED
  assert(res->data == 3);
#else
  assert(res->data == 2);
#endif

  delete head;
}

void testUnknownTypes() {
  arrStruct a{"This is a test", 3};
  int res = unknownTypeTest(a);
  printf("unknownTypeTest({\"This is a test\",3}) = %d\n", res);

#ifdef INSTRUMENTED
  assert(res == 117);
#else
  assert(res == 115);
#endif
}

void testByVal() { byValTest(0, 1, 2, 3, 4, 5, {"byvaltest", 9}); }

void testArrayType() {
  Container c{2, {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}};
  arrayTypeTest(&c);
  printf("testArrayType({2,{1,2,3,4,5,6,7,8,9,10}) --> {%d, ...}\n", c.factor);

#ifdef INSTRUMENTED
  int expected[10] = {3, 6, 9, 12, 15, 18, 21, 24, 27, 30};
  for (int i = 0; i < 10; i++) {
    assert(c.data[i] == expected[i]);
  }
#else
  int expected[10] = {2, 4, 6, 8, 10, 12, 14, 16, 18, 20};
  for (int i = 0; i < 10; i++) {
    assert(c.data[i] == expected[i]);
  }
#endif
}

int main(int argc, char* argv[]) {
#ifdef INSTRUMENTED
  printf("Driver for instrumented functions ...\n");
#else
  printf("Driver for uninstrumented functions ...\n");
#endif

  testBase();
  testIntTypes();
  testFloatTypes();
  testPointerTypes();
  testVoidTypes();
  testStructTypes();
  testForwardStructTypes();
  testUnknownTypes();
  testByVal();
  testArrayType();
  return 0;
}
