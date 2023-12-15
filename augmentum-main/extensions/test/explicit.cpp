/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// This file gives a flavour of what the instrumentation does.
// It should be compiled without the instrumentation pass and will hopefully
// still work.
#include <cstddef>

#include "internal.h"
#include "to-instrument.h"

using namespace augmentum;

static const char* augmentum__module_name__ = "to-instrument.cpp";

/** ======================= Basic Example ========================== **/

static int _Z3addii__original__(int a, int b);

static const char* _Z3addii__name__ = "_Z3addii";
static int (*_Z3addii__fn__)(int, int) = _Z3addii__original__;
static FnExtensionPoint* _Z3addii__extension_point__;

static int _Z3addii__original__(int a, int b) { return a + b; }

static int _Z3addii__extended__(int a, int b) {
  int r;
  void* args[] = {&a, &b};
  Internal::eval(_Z3addii__extension_point__, &r, args);
  return r;
}

static void _Z3addii__reflect__(void* r_val, void* arg_vals[]) {
  int* rp = reinterpret_cast<int*>(r_val);
  int* ap = reinterpret_cast<int*>(arg_vals[0]);
  int* bp = reinterpret_cast<int*>(arg_vals[1]);
  *rp = _Z3addii__original__(*ap, *bp);
}

int add(int a, int b) { return _Z3addii__fn__(a, b); }

__attribute__((constructor)) void _Z3addii__init__() {
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* _Z3addii__fntypedesc__ =
      Internal::get_function_type(i32_type_desc, 2, i32_type_desc, i32_type_desc);
  _Z3addii__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z3addii__name__, _Z3addii__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z3addii__fn__), reinterpret_cast<Fn>(_Z3addii__original__),
      reinterpret_cast<Fn>(_Z3addii__extended__), _Z3addii__reflect__);
}

/** ======================= Integer Types ========================== **/

static long _Z11intTypeTestbcsi__original__(bool sign, char c, short s, int i);

static const char* _Z11intTypeTestbcsi__name__ = "_Z11intTypeTestbcsi";
static long (*_Z11intTypeTestbcsi__fn__)(bool, char, short, int) = _Z11intTypeTestbcsi__original__;
static FnExtensionPoint* _Z11intTypeTestbcsi__extension_point__;

static long _Z11intTypeTestbcsi__original__(bool sign, char c, short s, int i) {
  if (sign)
    return c + s + i;
  else
    return c - s - i;
}

static long _Z11intTypeTestbcsi__extended__(bool sign, char c, short s, int i) {
  long r;
  void* args[] = {&sign, &c, &s, &i};
  Internal::eval(_Z11intTypeTestbcsi__extension_point__, &r, args);
  return r;
}

static void _Z11intTypeTestbcsi__reflect__(void* r_val, void* arg_vals[]) {
  long* rp = reinterpret_cast<long*>(r_val);
  bool* signp = reinterpret_cast<bool*>(arg_vals[0]);
  char* cp = reinterpret_cast<char*>(arg_vals[1]);
  short* sp = reinterpret_cast<short*>(arg_vals[2]);
  int* ip = reinterpret_cast<int*>(arg_vals[3]);
  *rp = _Z11intTypeTestbcsi__original__(*signp, *cp, *sp, *ip);
}

long intTypeTest(bool sign, char c, short s, int i) {
  return _Z11intTypeTestbcsi__fn__(sign, c, s, i);
}

__attribute__((constructor)) void _Z11intTypeTestbcsi__init__() {
  TypeDesc* i64_type_desc = Internal::get_i64_type();
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* i16_type_desc = Internal::get_i16_type();
  TypeDesc* i8_type_desc = Internal::get_i8_type();
  TypeDesc* i1_type_desc = Internal::get_i1_type();
  TypeDesc* _Z11intTypeTestbcsi__fntypedesc__ = Internal::get_function_type(
      i64_type_desc, 4, i1_type_desc, i8_type_desc, i16_type_desc, i32_type_desc);
  _Z11intTypeTestbcsi__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z11intTypeTestbcsi__name__, _Z11intTypeTestbcsi__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z11intTypeTestbcsi__fn__),
      reinterpret_cast<Fn>(_Z11intTypeTestbcsi__original__),
      reinterpret_cast<Fn>(_Z11intTypeTestbcsi__extended__), _Z11intTypeTestbcsi__reflect__);
}

/** ======================= Double Types ========================== **/

static double _Z13floatTypeTestfd__original__(float f, double d);

static const char* _Z13floatTypeTestfd__name__ = "_Z13floatTypeTestfd";
static double (*_Z13floatTypeTestfd__fn__)(float, double) = _Z13floatTypeTestfd__original__;
static FnExtensionPoint* _Z13floatTypeTestfd__extension_point__;

static double _Z13floatTypeTestfd__original__(float f, double d) { return f + d; }

static double _Z13floatTypeTestfd__extended__(float f, double d) {
  double r;
  void* args[] = {&f, &d};
  Internal::eval(_Z13floatTypeTestfd__extension_point__, &r, args);
  return r;
}

static void _Z13floatTypeTestfd__reflect__(void* r_val, void* arg_vals[]) {
  double* rp = reinterpret_cast<double*>(r_val);
  float* f = reinterpret_cast<float*>(arg_vals[0]);
  double* d = reinterpret_cast<double*>(arg_vals[1]);
  *rp = _Z13floatTypeTestfd__original__(*f, *d);
}

double floatTypeTest(float f, double d) { return _Z13floatTypeTestfd__fn__(f, d); }

__attribute__((constructor)) void _Z13floatTypeTestfd__init__() {
  TypeDesc* float_type_desc = Internal::get_float_type();
  TypeDesc* double_type_desc = Internal::get_double_type();
  TypeDesc* _Z13floatTypeTestfd__fntypedesc__ =
      Internal::get_function_type(double_type_desc, 2, float_type_desc, double_type_desc);
  _Z13floatTypeTestfd__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z13floatTypeTestfd__name__, _Z13floatTypeTestfd__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z13floatTypeTestfd__fn__),
      reinterpret_cast<Fn>(_Z13floatTypeTestfd__original__),
      reinterpret_cast<Fn>(_Z13floatTypeTestfd__extended__), _Z13floatTypeTestfd__reflect__);
}

/** ======================= Pointer Types ========================== **/

static int* _Z15pointerTypeTestPiPd__original__(int* ip, double* dp);

static const char* _Z15pointerTypeTestPiPd__name__ = "_Z15pointerTypeTestPiPd";
static int* (*_Z15pointerTypeTestPiPd__fn__)(int*, double*) = _Z15pointerTypeTestPiPd__original__;

static FnExtensionPoint* _Z15pointerTypeTestPiPd__extension_point__;

static int* _Z15pointerTypeTestPiPd__original__(int* ip, double* dp) {
  if (ip)
    (*ip)++;
  if (dp)
    (*dp)--;
  return ip;
}

static int* _Z15pointerTypeTestPiPd__extended__(int* ip, double* dp) {
  int* r;
  void* args[] = {&ip, &dp};
  Internal::eval(_Z15pointerTypeTestPiPd__extension_point__, &r, args);
  return r;
}

static void _Z15pointerTypeTestPiPd__reflect__(void* r_val, void* arg_vals[]) {
  int** rpp = reinterpret_cast<int**>(r_val);
  int** ipp = reinterpret_cast<int**>(arg_vals[0]);
  double** dpp = reinterpret_cast<double**>(arg_vals[1]);
  *rpp = _Z15pointerTypeTestPiPd__original__(*ipp, *dpp);
}

int* pointerTypeTest(int* ip, double* dp) { return _Z15pointerTypeTestPiPd__fn__(ip, dp); }

__attribute__((constructor)) void _Z15pointerTypeTestPiPd__init__() {
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* int_ptr_type_desc = Internal::get_ptr_type(i32_type_desc);
  TypeDesc* double_type_desc = Internal::get_double_type();
  TypeDesc* double_ptr_type_desc = Internal::get_ptr_type(double_type_desc);
  TypeDesc* _Z15pointerTypeTestPiPd__fntypedesc__ =
      Internal::get_function_type(int_ptr_type_desc, 2, int_ptr_type_desc, double_ptr_type_desc);
  _Z15pointerTypeTestPiPd__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z15pointerTypeTestPiPd__name__,
      _Z15pointerTypeTestPiPd__fntypedesc__, reinterpret_cast<Fn*>(&_Z15pointerTypeTestPiPd__fn__),
      reinterpret_cast<Fn>(_Z15pointerTypeTestPiPd__original__),
      reinterpret_cast<Fn>(_Z15pointerTypeTestPiPd__extended__),
      _Z15pointerTypeTestPiPd__reflect__);
}

/** ======================= Void Types ========================== **/

static void _Z12voidTypeTestPi__original__(int* ip);

static const char* _Z12voidTypeTestPi__name__ = "_Z12voidTypeTestPi";
static void (*_Z12voidTypeTestPi__fn__)(int*) = _Z12voidTypeTestPi__original__;
static FnExtensionPoint* _Z12voidTypeTestPi__extension_point__;

static void _Z12voidTypeTestPi__original__(int* ip) {
  if (ip)
    (*ip)++;
}

static void _Z12voidTypeTestPi__extended__(int* ip) {
  void* args[] = {&ip};
  Internal::eval(_Z12voidTypeTestPi__extension_point__, nullptr, args);
}

static void _Z12voidTypeTestPi__reflect__(void* r_val, void* arg_vals[]) {
  int** ipp = reinterpret_cast<int**>(arg_vals[0]);
  _Z12voidTypeTestPi__original__(*ipp);
}

void voidTypeTest(int* ip) { _Z12voidTypeTestPi__fn__(ip); }

__attribute__((constructor)) void _Z12voidTypeTestPi__init__() {
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* int_ptr_type_desc = Internal::get_ptr_type(i32_type_desc);
  TypeDesc* void_type_desc = Internal::get_void_type();
  TypeDesc* _Z12voidTypeTestPi__fntypedesc__ =
      Internal::get_function_type(void_type_desc, 1, int_ptr_type_desc);
  _Z12voidTypeTestPi__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z12voidTypeTestPi__name__, _Z12voidTypeTestPi__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z12voidTypeTestPi__fn__),
      reinterpret_cast<Fn>(_Z12voidTypeTestPi__original__),
      reinterpret_cast<Fn>(_Z12voidTypeTestPi__extended__), _Z12voidTypeTestPi__reflect__);
}

/** ======================= Anon Struct Types ========================== **/

static Result _Z14structTypeTestii__original__(int a, int b);

static const char* _Z14structTypeTestii__name__ = "_Z14structTypeTestii";
static Result (*_Z14structTypeTestii__fn__)(int, int) = _Z14structTypeTestii__original__;
static FnExtensionPoint* _Z14structTypeTestii__extension_point__;

static Result _Z14structTypeTestii__original__(int a, int b) {
  double res = a + b;
  return {a, res};
}

static Result _Z14structTypeTestii__extended__(int a, int b) {
  Result r;
  void* args[] = {&a, &b};
  Internal::eval(_Z14structTypeTestii__extension_point__, &r, args);
  return r;
}

static void _Z14structTypeTestii__reflect__(void* r_val, void* arg_vals[]) {
  Result* rp = reinterpret_cast<Result*>(r_val);
  int* ap = reinterpret_cast<int*>(arg_vals[0]);
  int* bp = reinterpret_cast<int*>(arg_vals[1]);
  *rp = _Z14structTypeTestii__original__(*ap, *bp);
}

Result structTypeTest(int a, int b) { return _Z14structTypeTestii__fn__(a, b); }

__attribute__((constructor)) void _Z14structTypeTestii__init__() {
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* i64_type_desc = Internal::get_i64_type();
  TypeDesc* double_type_desc = Internal::get_double_type();
  TypeDesc* struct_type_desc = Internal::get_anon_struct_type(2, i64_type_desc, double_type_desc);
  TypeDesc* _Z14structTypeTestii__fntypedesc__ =
      Internal::get_function_type(struct_type_desc, 2, i32_type_desc, i32_type_desc);
  _Z14structTypeTestii__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z14structTypeTestii__name__, _Z14structTypeTestii__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z14structTypeTestii__fn__),
      reinterpret_cast<Fn>(_Z14structTypeTestii__original__),
      reinterpret_cast<Fn>(_Z14structTypeTestii__extended__), _Z14structTypeTestii__reflect__);
}

/** ======================= Named / Forward Struct Types
 * ========================== **/

Node* _Z19namedStructTypeTestP4Nodei__original__(Node* head, int data);

static const char* _Z19namedStructTypeTestP4Nodei__name__ = "_Z19namedStructTypeTestP4Nodei";
static const char* augmentum__node_struct_type_name__ = "struct.Node";
static Node* (*_Z19namedStructTypeTestP4Nodei__fn__)(Node*, int) =
    _Z19namedStructTypeTestP4Nodei__original__;
static FnExtensionPoint* _Z19namedStructTypeTestP4Nodei__extension_point__;

Node* _Z19namedStructTypeTestP4Nodei__original__(Node* head, int data) {
  if (!head)
    return new Node(data);

  Node* curr = head;
  while (curr->next) {
    curr = curr->next;
  }
  curr->next = new Node(data);
  return curr->next;
}

static Node* _Z19namedStructTypeTestP4Nodei__extended__(Node* head, int data) {
  Node* r;
  void* args[] = {&head, &data};
  Internal::eval(_Z19namedStructTypeTestP4Nodei__extension_point__, &r, args);
  return r;
}

static void _Z19namedStructTypeTestP4Nodei__reflect__(void* r_val, void* arg_vals[]) {
  Node** rp = reinterpret_cast<Node**>(r_val);
  Node** headp = reinterpret_cast<Node**>(arg_vals[0]);
  int* datap = reinterpret_cast<int*>(arg_vals[1]);
  *rp = _Z19namedStructTypeTestP4Nodei__original__(*headp, *datap);
}

Node* namedStructTypeTest(Node* head, int data) {
  return _Z19namedStructTypeTestP4Nodei__fn__(head, data);
}

__attribute__((constructor)) void _Z19namedStructTypeTestP4Nodei__init__() {
  TypeDesc* struct_type_desc = Internal::get_forward_struct_type(
      augmentum__module_name__, augmentum__node_struct_type_name__);
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* struct_ptr_type_desc = Internal::get_ptr_type(struct_type_desc);
  Internal::set_struct_elem_types(struct_type_desc, 2, i32_type_desc, struct_ptr_type_desc);
  TypeDesc* _Z19namedStructTypeTestP4Nodei__fntypedesc__ =
      Internal::get_function_type(struct_ptr_type_desc, 2, struct_ptr_type_desc, i32_type_desc);
  _Z19namedStructTypeTestP4Nodei__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z19namedStructTypeTestP4Nodei__name__,
      _Z19namedStructTypeTestP4Nodei__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z19namedStructTypeTestP4Nodei__fn__),
      reinterpret_cast<Fn>(_Z19namedStructTypeTestP4Nodei__original__),
      reinterpret_cast<Fn>(_Z19namedStructTypeTestP4Nodei__extended__),
      _Z19namedStructTypeTestP4Nodei__reflect__);
}

/** ======================= Unknown Type ========================== **/

static int _Z15unknownTypeTest9arrStruct__original__(arrStruct a);

static const char* _Z15unknownTypeTest9arrStruct__name__ = "_Z15unknownTypeTest9arrStruct";
static const char* augmentum__unknown_type_signature__ = "[50 x i8]";
static int (*_Z15unknownTypeTest9arrStruct__fn__)(arrStruct) =
    _Z15unknownTypeTest9arrStruct__original__;
static FnExtensionPoint* _Z15unknownTypeTest9arrStruct__extension_point__;

static int _Z15unknownTypeTest9arrStruct__original__(arrStruct a) { return a.ptr[a.i]; }

static int _Z15unknownTypeTest9arrStruct__extended__(arrStruct a) {
  int r;
  void* args[] = {&a};
  Internal::eval(_Z15unknownTypeTest9arrStruct__extension_point__, &r, args);
  return r;
}

static void _Z15unknownTypeTest9arrStruct__reflect__(void* r_val, void* arg_vals[]) {
  int* rp = reinterpret_cast<int*>(r_val);
  arrStruct* ap = reinterpret_cast<arrStruct*>(arg_vals[0]);
  *rp = _Z15unknownTypeTest9arrStruct__original__(*ap);
}

int unknownTypeTest(arrStruct a) { return _Z15unknownTypeTest9arrStruct__fn__(a); }

__attribute__((constructor)) void _Z15unknownTypeTest9arrStruct__init__() {
  TypeDesc* unknown_type_desc =
      Internal::get_unknown_type(augmentum__module_name__, augmentum__unknown_type_signature__);
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* struct_type_desc = Internal::get_anon_struct_type(2, unknown_type_desc, i32_type_desc);
  TypeDesc* _Z15unknownTypeTest9arrStruct__fntypedesc__ =
      Internal::get_function_type(i32_type_desc, 1, unknown_type_desc);
  _Z15unknownTypeTest9arrStruct__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z15unknownTypeTest9arrStruct__name__,
      _Z15unknownTypeTest9arrStruct__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z15unknownTypeTest9arrStruct__fn__),
      reinterpret_cast<Fn>(_Z15unknownTypeTest9arrStruct__original__),
      reinterpret_cast<Fn>(_Z15unknownTypeTest9arrStruct__extended__),
      _Z15unknownTypeTest9arrStruct__reflect__);
}

/** ======================= ByVal Test ========================== **/

static void _Z9byValTestiiiiii10SomeStruct__original__(int p0, int p1, int p2, int p3, int p4,
                                                       int p5, SomeStruct s);

static const char* _Z9byValTestiiiiii10SomeStruct__name__ = "_Z9byValTestiiiiii10SomeStruct";
static const char* augmentum__someStruct_struct_type_name__ = "struct.SomeStruct";
static void (*_Z9byValTestiiiiii10SomeStruct__fn__)(int, int, int, int, int, int, SomeStruct) =
    _Z9byValTestiiiiii10SomeStruct__original__;
static FnExtensionPoint* _Z9byValTestiiiiii10SomeStruct__extension_point__;

static void _Z9byValTestiiiiii10SomeStruct__original__(int p0, int p1, int p2, int p3, int p4,
                                                       int p5, SomeStruct s) {
  std::cout << s.str() << (p0 + p1 + p2 + p3 + p4 + p5) << "\n";
}

static void _Z9byValTestiiiiii10SomeStruct__extended__(int p0, int p1, int p2, int p3, int p4,
                                                       int p5, SomeStruct s) {
  void* args[] = {&p0, &p1, &p2, &p3, &p4, &p5, &s};
  Internal::eval(_Z9byValTestiiiiii10SomeStruct__extension_point__, nullptr, args);
}

static void _Z9byValTestiiiiii10SomeStruct__reflect__(void* r_val, void* arg_vals[]) {
  int* p0p = reinterpret_cast<int*>(arg_vals[0]);
  int* p1p = reinterpret_cast<int*>(arg_vals[1]);
  int* p2p = reinterpret_cast<int*>(arg_vals[2]);
  int* p3p = reinterpret_cast<int*>(arg_vals[3]);
  int* p4p = reinterpret_cast<int*>(arg_vals[4]);
  int* p5p = reinterpret_cast<int*>(arg_vals[5]);
  SomeStruct* sp = reinterpret_cast<SomeStruct*>(arg_vals[6]);
  _Z9byValTestiiiiii10SomeStruct__original__(*p0p, *p1p, *p2p, *p3p, *p4p, *p5p, *sp);
}

void byValTest(int p0, int p1, int p2, int p3, int p4, int p5, SomeStruct s) {
  return _Z9byValTestiiiiii10SomeStruct__fn__(p0, p1, p2, p3, p4, p5, s);
}

__attribute__((constructor)) void _Z9byValTestiiiiii10SomeStruct__init__() {
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* i8_type_desc = Internal::get_i8_type();
  TypeDesc* i8_ptr_type_desc = Internal::get_ptr_type(i8_type_desc);
  TypeDesc* i64_type_desc = Internal::get_i64_type();
  TypeDesc* void_type_desc = Internal::get_void_type();
  TypeDesc* struct_type_desc = Internal::get_forward_struct_type(
      augmentum__module_name__, augmentum__someStruct_struct_type_name__);
  TypeDesc* struct_ptr_type_desc = Internal::get_ptr_type(struct_type_desc);
  Internal::set_struct_elem_types(struct_type_desc, 2, i8_ptr_type_desc, i64_type_desc);
  TypeDesc* _Z9byValTestiiiiii10SomeStruct__fntypedesc__ =
      Internal::get_function_type(void_type_desc, 7, i32_type_desc, i32_type_desc, i32_type_desc,
                                  i32_type_desc, i32_type_desc, i32_type_desc, struct_type_desc);
  _Z9byValTestiiiiii10SomeStruct__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z9byValTestiiiiii10SomeStruct__name__,
      _Z9byValTestiiiiii10SomeStruct__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z9byValTestiiiiii10SomeStruct__fn__),
      reinterpret_cast<Fn>(_Z9byValTestiiiiii10SomeStruct__original__),
      reinterpret_cast<Fn>(_Z9byValTestiiiiii10SomeStruct__extended__),
      _Z9byValTestiiiiii10SomeStruct__reflect__);
}

/** ======================= Array Test ========================== **/

void _Z13arrayTypeTestP9Container__original__(Container* head);

static const char* _Z13arrayTypeTestP9Container__name__ = "_Z13arrayTypeTestP9Container";
static const char* augmentum__container_struct_type_name__ = "struct.Container";
static void (*_Z13arrayTypeTestP9Container__fn__)(Container*) =
    _Z13arrayTypeTestP9Container__original__;
static FnExtensionPoint* _Z13arrayTypeTestP9Container__extension_point__;

void _Z13arrayTypeTestP9Container__original__(Container* c) {
  for (int i = 0; i < 10; i++) {
    c->data[i] *= c->factor;
  }
}

static void _Z13arrayTypeTestP9Container__extended__(Container* c) {
  void* args[] = {&c};
  Internal::eval(_Z13arrayTypeTestP9Container__extension_point__, nullptr, args);
}

static void _Z13arrayTypeTestP9Container__reflect__(void* r_val, void* arg_vals[]) {
  Container** cp = reinterpret_cast<Container**>(arg_vals[0]);
  _Z13arrayTypeTestP9Container__original__(*cp);
}

void arrayTypeTest(Container* c) { _Z13arrayTypeTestP9Container__fn__(c); }

__attribute__((constructor)) void _Z13arrayTypeTestP9Container__init__() {
  TypeDesc* struct_type_desc = Internal::get_forward_struct_type(
      augmentum__module_name__, augmentum__container_struct_type_name__);
  TypeDesc* i32_type_desc = Internal::get_i32_type();
  TypeDesc* array_type_desc = Internal::get_array_type(i32_type_desc, 10);
  TypeDesc* struct_ptr_type_desc = Internal::get_ptr_type(struct_type_desc);
  Internal::set_struct_elem_types(struct_type_desc, 2, i32_type_desc, array_type_desc);
  TypeDesc* void_type_desc = Internal::get_void_type();
  TypeDesc* _Z13arrayTypeTestP9Container__fntypedesc__ =
      Internal::get_function_type(void_type_desc, 1, struct_ptr_type_desc);
  _Z13arrayTypeTestP9Container__extension_point__ = Internal::create_extension_point(
      augmentum__module_name__, _Z13arrayTypeTestP9Container__name__,
      _Z13arrayTypeTestP9Container__fntypedesc__,
      reinterpret_cast<Fn*>(&_Z13arrayTypeTestP9Container__fn__),
      reinterpret_cast<Fn>(_Z13arrayTypeTestP9Container__original__),
      reinterpret_cast<Fn>(_Z13arrayTypeTestP9Container__extended__),
      _Z13arrayTypeTestP9Container__reflect__);
}
