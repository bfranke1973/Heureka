/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include "to-instrument.h"

// Some functions to instrument
int add(int a, int b) { return a + b; }

long intTypeTest(bool sign, char c, short s, int i) {
  if (sign)
    return c + s + i;
  else
    return c - s - i;
}

double floatTypeTest(float f, double d) { return f + d; }

int* pointerTypeTest(int* ip, double* dp) {
  if (ip)
    (*ip)++;
  if (dp)
    (*dp)--;
  return ip;
}

void voidTypeTest(int* ip) {
  if (ip)
    (*ip)++;
}

Result structTypeTest(int a, int b) {
  double res = a + b;
  return {a, res};
}

Node* namedStructTypeTest(Node* head, int data) {
  if (!head)
    return new Node(data);

  Node* curr = head;
  while (curr->next) {
    curr = curr->next;
  }
  curr->next = new Node(data);
  return curr->next;
}

int unknownTypeTest(arrStruct a) { return a.ptr[a.i]; }

void byValTest(int p0, int p1, int p2, int p3, int p4, int p5, SomeStruct s) {
  std::cout << s.str() << (p0 + p1 + p2 + p3 + p4 + p5) << "\n";
}

void arrayTypeTest(Container* c) {
  for (int i = 0; i < 10; i++) {
    c->data[i] *= c->factor;
  }
}
