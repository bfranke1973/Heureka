/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#ifndef __TO_INSTRUMENT_H__
#define __TO_INSTRUMENT_H__

#include <iostream>
#include <string>

int add(int, int);

long intTypeTest(bool sign, char c, short s, int i);

double floatTypeTest(float f, double d);

int* pointerTypeTest(int* ip, double* dp);

void voidTypeTest(int* ip);

struct Result {
  long resl;
  double resd;
};

Result structTypeTest(int a, int b);

struct Node {
  int data;
  Node* next;

  Node(int data) : data(data), next(nullptr) {}
  ~Node() { delete next; }
};

Node* namedStructTypeTest(Node* head, int data);

struct arrStruct {
  char ptr[50];
  int i;
};

int unknownTypeTest(arrStruct a);

struct SomeStruct {
  const char* a;
  size_t b;

  std::string str() const {
    if (!a)
      return std::string();
    return std::string(a, b);
  }
};

void byValTest(int p0, int p1, int p2, int p3, int p4, int p5, SomeStruct s);

struct Container {
  int factor;
  int data[10];
};

void arrayTypeTest(Container* c);

#endif  // __TO_INSTRUMENT_H__
