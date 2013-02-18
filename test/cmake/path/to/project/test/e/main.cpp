#include <iostream>

#ifdef HAS_VERSION_H
#  include "test/version.h"
#endif

using namespace std;

int main()
{
#ifdef TEST_PROJECT_STR
   cout << "TEST_PROJECT_STR=" << TEST_PROJECT_STR << endl;
#endif

#ifdef TEST_PACKAGE_STR
   cout << "TEST_PACKAGE_STR=" << TEST_PACKAGE_STR << endl;
#endif

#ifdef TEST_AUTHOR_STR
   cout << "TEST_AUTHOR_STR=" << TEST_AUTHOR_STR << endl;
#endif

#ifdef TEST_RELEASE_ISODATE_STR
   cout << "TEST_RELEASE_ISODATE_STR=" << TEST_RELEASE_ISODATE_STR << endl;
#endif

#ifdef TEST_RELEASE_YEAR_STR
   cout << "TEST_RELEASE_YEAR_STR=" << TEST_RELEASE_YEAR_STR << endl;
#endif

#ifdef TEST_RELEASE_DATE_STR
   cout << "TEST_RELEASE_DATE_STR=" << TEST_RELEASE_DATE_STR << endl;
#endif

#ifdef TEST_RELEASE_TIME_STR
   cout << "TEST_RELEASE_TIME_STR=" << TEST_RELEASE_TIME_STR << endl;
#endif

#ifdef TEST_FULL_REVISION_STR
   cout << "TEST_FULL_REVISION_STR=" << TEST_FULL_REVISION_STR << endl;
#endif

#ifdef TEST_REVISION_STR
   cout << "TEST_REVISION_STR=" << TEST_REVISION_STR << endl;
#endif

#ifdef TEST_RELEASE_YEAR
   cout << "TEST_RELEASE_YEAR=" << TEST_RELEASE_YEAR << endl;
#endif

#ifdef TEST_RELEASE_EPOCH_TIME
   cout << "TEST_RELEASE_EPOCH_TIME=" << TEST_RELEASE_EPOCH_TIME << endl;
#endif

#ifdef TEST_MAJOR_REVISION
   cout << "TEST_MAJOR_REVISION=" << TEST_MAJOR_REVISION << endl;
#endif

#ifdef TEST_MINOR_REVISION
   cout << "TEST_MINOR_REVISION=" << TEST_MINOR_REVISION << endl;
#endif

#ifdef TEST_PATCHLEVEL
   cout << "TEST_PATCHLEVEL=" << TEST_PATCHLEVEL << endl;
#endif

   return 0;
}
