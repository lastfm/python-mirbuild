#include <cstring>
#include <iostream>

#include "test/test.h"

int main(int argc, char **argv)
{
#ifdef HAVE_LIB_A
   std::cout << "a(12)=" << a(12) << std::endl;
#endif

#ifdef HAVE_LIB_B
   std::cout << "b(23)=" << b(23) << std::endl;
#endif

   for (int i = 1; i < argc; ++i)
      if (!strcmp("fail", argv[i]))
         return 1;

   return 0;
}
