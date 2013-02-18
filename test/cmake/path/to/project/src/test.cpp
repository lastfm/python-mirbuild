#ifdef HAVE_LIB_A
# include <lib_a.h>
#endif

#ifdef HAVE_LIB_B
# include <foo/lib_b.h>
#endif

#include "test/test.h"

int test(int x)
{
   return 2*x;
}

#ifdef HAVE_LIB_A
int a(int x)
{
   return x + LIB_A_CONSTANT;
}
#endif

#ifdef HAVE_LIB_B
int b(int x)
{
   return x + LIB_B_CONSTANT;
}
#endif
