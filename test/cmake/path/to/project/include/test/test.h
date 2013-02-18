#ifndef TEST_TEST_H
#define TEST_TEST_H

int test(int);

#ifdef HAVE_LIB_A
int a(int x);
#endif

#ifdef HAVE_LIB_B
int b(int x);
#endif

#endif
