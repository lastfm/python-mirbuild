@echo off

REM To have these aliases installed when you start your command shell:
REM    1. Open Run (Win+R), type regedit and press enter.
REM    2. Navigate to HKEY_CURRENT_USER\Software\Microsoft\Command Processor
REM    3. Right click on Command Processor and create a new String Value. Name it autorun.
REM    4. Double click on autorun and enter the path of the batch file you created a short while back.
REM    5. Press OK and you are done.

doskey opts = python build.py $*
doskey build = python build.py build $*
doskey config = python build.py configure $*
doskey clean = python build.py clean $*
doskey rclean = python build.py realclean $*
doskey meta = python build.py meta $*
doskey utest = python build.py test $*
doskey doinstall = python build.py install $*
doskey uninstall = python build.py uninstall $*
doskey package = python build.py package $*
doskey coverage = python build.py package $*
