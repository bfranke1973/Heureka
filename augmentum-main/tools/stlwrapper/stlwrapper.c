/* Copyright (c) 2021, Björn Franke
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#define _GNU_SOURCE

#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>

static void* (*real_malloc)(size_t) = NULL;
// static void *(*real_calloc)(size_t, size_t) = NULL;
static void* (*real_realloc)(void*, size_t) = NULL;
static void (*real_free)(void*) = NULL;
static int (*real_posix_memalign)(void**, size_t, size_t) = NULL;
static FILE* (*real_fopen)(const char*, const char*) = NULL;
static int (*real_fclose)(FILE*) = NULL;

static int (*real_vfprintf)(FILE*, const char*, va_list) = NULL;
static int (*real_vsprintf)(char*, const char*, va_list) = NULL;
static int (*real_vprintf)(const char*, va_list) = NULL;

static __thread int no_malloc_hook;
static __thread int no_free_hook;

static void mtrace_init(void) {
  real_malloc = dlsym(RTLD_NEXT, "malloc");
  if (NULL == real_malloc) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }

  // real_calloc = dlsym(RTLD_NEXT, "calloc");
  // if (NULL == real_calloc) {
  //     fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  // }

  real_realloc = dlsym(RTLD_NEXT, "realloc");
  if (NULL == real_realloc) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }

  real_free = dlsym(RTLD_NEXT, "free");
  if (NULL == real_free) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }

  real_posix_memalign = dlsym(RTLD_NEXT, "posix_memalign");
  if (NULL == real_posix_memalign) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }

  real_fopen = dlsym(RTLD_NEXT, "fopen");
  if (NULL == real_fopen) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }

  real_fclose = dlsym(RTLD_NEXT, "fclose");
  if (NULL == real_fclose) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }

  real_vfprintf = dlsym(RTLD_NEXT, "vfprintf");
  if (NULL == real_vfprintf) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }

  real_vsprintf = dlsym(RTLD_NEXT, "vsprintf");
  if (NULL == real_vsprintf) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }

  real_vprintf = dlsym(RTLD_NEXT, "vprintf");
  if (NULL == real_vprintf) {
    fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
  }
}

int fprintf(FILE* stream, const char* format, ...) {
  if (real_vfprintf == NULL) {
    mtrace_init();
  }

  // some implementations of fprintf call malloc or free,
  // so make sure you can avoid endless recursion
  no_free_hook = no_malloc_hook = 1;

  va_list va;
  va_start(va, format);
  const int ret = real_vfprintf(stream, format, va);
  va_end(va);

  no_free_hook = no_malloc_hook = 0;
  return ret;
}

int sprintf(char* s, const char* format, ...) {
  if (real_vsprintf == NULL) {
    mtrace_init();
  }

  // some implementations of fprintf call malloc or free,
  // so make sure you can avoid endless recursion
  no_free_hook = no_malloc_hook = 1;

  va_list va;
  va_start(va, format);
  const int ret = real_vsprintf(s, format, va);
  va_end(va);

  no_free_hook = no_malloc_hook = 0;
  return ret;
}

int printf(const char* format, ...) {
  if (real_vprintf == NULL) {
    mtrace_init();
  }

  // some implementations of printf call malloc or free,
  // so make sure you can avoid endless recursion
  no_free_hook = no_malloc_hook = 1;

  va_list va;
  va_start(va, format);
  const int ret = real_vprintf(format, va);
  va_end(va);

  no_free_hook = no_malloc_hook = 0;
  return ret;
}

void* malloc(size_t size) {
  if (real_malloc == NULL) {
    mtrace_init();
  }

  // some implementations of fprintf call malloc or free,
  // so make sure you can avoid endless recursion
  if (no_malloc_hook) {
    return real_malloc(size);
  }

  size_t s = size;
  void* p = NULL;

  p = real_malloc(size);
  fprintf(stderr, "malloc(%zu) = %p\n", s, p);

  return p;
}

// TODO calloc calls dlsym which calls calloc which calls dlsym ...
// find a solution for the first call where real_calloc is not initialised yet
//
// void *calloc(size_t nitems, size_t size)
// {
//     if(real_calloc==NULL) {
//         mtrace_init();
//     }

//     size_t n = nitems;
//     size_t s = size;
//     void *p = NULL;
//     p = real_calloc(nitems,size);
//     fprintf(stderr, "cmalloc(%zu,%zu) = %p\n", n, s, p);

//     return p;
// }

void* realloc(void* ptr, size_t size) {
  if (real_realloc == NULL) {
    mtrace_init();
  }

  void* ip = ptr;
  size_t s = size;
  void* p = NULL;
  p = real_realloc(ptr, size);
  fprintf(stderr, "realloc(%p,%zu) = %p\n", ip, s, p);
  return p;
}

void free(void* ptr) {
  if (real_free == NULL) {
    mtrace_init();
  }

  // some implementations of fprintf call malloc or free,
  // so make sure you can avoid endless recursion
  if (no_free_hook) {
    real_free(ptr);
    return;
  }

  real_free(ptr);
  fprintf(stderr, "free(%p)\n", ptr);
}

int posix_memalign(void** memptr, size_t alignment, size_t size) {
  if (real_posix_memalign == NULL) {
    mtrace_init();
  }

  void** m = memptr;
  size_t a = alignment;
  size_t s = size;
  int err = real_posix_memalign(memptr, alignment, size);
  fprintf(stderr, "posix_memalign(%p, %zu, %zu) = %d\n", m, a, s, err);
  return err;
}

FILE* fopen(const char* filename, const char* mode) {
  if (real_fopen == NULL) {
    mtrace_init();
  }

  FILE* f = NULL;
  const char* fn = filename;
  const char* m = mode;
  f = real_fopen(filename, mode);
  fprintf(stderr, "fopen(%s,%s) = %p\n", fn, m, f);
  return f;
}

int fclose(FILE* stream) {
  if (real_fclose == NULL) {
    mtrace_init();
  }

  FILE* s = stream;
  int err = real_fclose(stream);
  fprintf(stderr, "fclose(%p) = %d\n", s, err);
  return err;
}
