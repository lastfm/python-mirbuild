# -*- coding: utf-8 -*-
#
# Copyright © 2011-2013 Last.fm Limited
#
# This file is part of python-mirbuild.
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

r"""

Framework for building MIR projects at Last.fm
==============================================

mirbuild is a collection of python modules that are supposed to make building
different configurations as well as testing and packaging of projects as easy
as possible. It is usually only used by a build.py script in the root of each
project. The idea is to keep this build.py short and sweet, e.g. ::

  from mirbuild import *
  CMakeProject('hobnob').run()

is sometimes all it takes. To actually build, test or package a project, all
you have to do is run build.py with an appropriate command, e.g. ::

  $ python build.py build

This will take care of building the project, regardless of its nature or of
the underlying build system. Usually, even a small build.py comes with a vast
amount of options. Just run ::

  $ python build.py

to get an overview.

Writing a build.py file
-----------------------

Where possible, mirbuild tries to figure out certain properties about the project
on its own, e.g. if there are unit tests or if there's support for packaging
the project. So, if the libmoost project contained a test folder, the simple code
from the introduction would actually be equivalent to::

  from mirbuild import *
  project = CMakeProject('hobnob')
  project.test('test')
  project.run()

This, in turn, is just a shortcut for listing all the subfolders in test/ manually
and for actually creating all the test objects yourself, e.g.::

  project.test(CMakeTestBuilder(project.env, 'test/algo',
                                Test('fancy-algos', 'test')),
               CMakeTestBuilder(project.env, 'test/containers',
                                Test('cont-test', 'test')),
               CMakeTestBuilder(project.env, 'test/io',
                                Test('io-test', 'test')),
               runner = BoostTestRunner)

The "simple" version obviously requires a certain structure, yet it's possible to
adapt the build.py to a lot of scenarios if you make full use of its classes.

To model dependencies on other projects, use the depends() method::

  project.depends('libfoo', 'libbar')

Again, this is just a shortcut and the appropriate objects for each dependency will
be generated on the fly. If the dependency is of a different type (i.e. in our case
it is not a CMakeProject), you have to construct the dependency object yourself.
For example, here's how to make a CMakeProject depend on a ThriftInterface::

  from mirbuild import *
  project = CMakeProject('libmoost')
  project.depends(ThriftDependency('thrift-fm303'))

It is also possible to generate version headers for a project. In the simplest case,
this is just::

  project.version('include/moost/version.h')

The code will automagically recognise that you want to create a C header file and
it will also try to work out where to get the necessary information from. If your
project source contains a debian/changelog file, it will take it from there.

Talking of debian packages, mirbuild also takes care of creating a debian/rules file
that will work by calling build.py for the various stages of building and installation.
You still can supply your own rules file if you need to, but there's a good chance
that you can probably do what you want by customising the packaging process in build.py::

  rules = mirbuild.packaging.DebianRules()
  rules.post_auto_install = 'mkdir -p $(TMP)/foo/bar'
  project.package(mirbuild.DebianPackaging(project.env, rules))

This is quite a stupid example, but it should give you an idea.

Writing a CMakeProject
----------------------

Assume you want to write a project for a static library that comes wth a set of
header files. You want this project to be build using CMake. The library has a
couple of dependencies, but nothing fancy, so the build.py is rather simple::

  from mirbuild import *
  project = CMakeProject('libuser-profile')
  project.depends(ThriftDependency('thrift-fm303'),
                  ThriftDependency('thrift-radb'),
                  'libmoost')
  project.run()

Now, you have to write a CMakeLists.txt for your project. Assuming you have
the following source files ::

  $ find include src -type f
  include/user_profile
  include/user_profile/radb_client.hpp
  include/user_profile/restype_enum.h
  include/user_profile/user_profile.h
  src/user_profile.cpp

this CMakeLists.txt turns out to be quite simple as well::

  PROJECT(libuser-profile)
  INCLUDE(config.cmake)
  INCLUDE_DIRECTORIES(include)
  ADD_LIBRARY(user_profile STATIC src/user_profile)

The important part is the INCLUDE of the config.cmake file. This file contains the
CMake configuration for your project and is generated by build.py's configure step
(or implicitly by running other commands that depend on a configuration).

If your CMakeProject depends on external libraries, some of them can be found and
added to the configuration automatically using the find() method. For example, let's
assume we have an executable that depends on the boost library. You could add ::

  project.find('boost')

to the build.py and modify the CMakeLists.txt accordingly::

  ADD_EXECUTABLE(client src/client_main)
  TARGET_LINK_LIBRARIES(client ${Boost_LIBRARIES})

Depending on the library, you can pass various options to the find method, e.g.::

  project.find('boost', version = '1.42', components = ['system', 'date_time'], debug = True)

Running build.py
----------------

If you run ::

  $ python build.py build

now, you should find a libuser_profile.a inside a lib/ directory in your project.

Each object that is registered with the project can add its own set of command line
options to build.py, so you might see a lot of options even for a two line build.py.

It's also easy to extend mirbuild to support other underlying build systems, other
packaging systems, other test frameworks, or other languages.

By the way, it's also possible to abbreviate commands as long as the abbreviation
is unambiguous. For example, most of the time ::

  $ python build.py bu

is enough to run a build.

Using mirbuild.walk
-------------------

There's a quite useful tool for batch processing build jobs. Just run::

  $ python -m mirbuild.walk --help

It will automatically walk a project tree, scan each project for its metadata,
topologically sort all projects according to their dependencies and then run a
series of commands for each project. I will also supply the necessary --with-xxx
options to each project. That way, doing a full rebuild of all projects is as
easy as::

  $ python -m mirbuild.walk realclean build

This is very much work in progress. There's for example support for meta-commands
that allow package installation or removal. These will be documented when it's
considered mature enough.

Building packages using mirbuild.walk
-------------------------------------

To build "clean" packages, the user running mirbuild.walk needs to have permission
to install packages. You can do that by adding the line ::

  username  ALL = NOPASSWD: /usr/bin/dpkg

to the sudoers file where you have to replace username with the name of the user
running mirbuild.walk (usually yourself). You can edit the sudoers file using::

  $ visudo

If that doesn't work, you probably don't have the sudo package installed. Try::

  $ apt-get install sudo

Rebuilding packages all projects can then be done using::

  $ python -m mirbuild.walk -n package debinstall

To rebuild only packages for a particular project and all its dependencies, use::

  $ python -m mirbuild.walk -n -p name-of-project package debinstall

Uninstalling works like this::

  $ python -m mirbuild.walk -n -r debuninstall
  $ python -m mirbuild.walk -n -r -p name-of-project debuninstall

The -r tells mirbuild.walk to reverse the dependency order so packages will be
uninstalled without introducing dependency problems.

You can optionally enable project tracking which is useful if you don't want
to rebuild all projects in case of a failure::

  $ python -m mirbuild.walk -n -t track.json package debinstall

The tracking file will only be removed after all projects have been processed.

Debian Packaging
----------------

Preparing a project for debian packaging is a two-step process with both steps
usually being quite easy. First of all, you need to ensure that your project
installs fine to an arbitrary location using the --install-destdir option of
build.py. Let's go back to our example of the user-profile library above. In
order to install the project files, CMake needs the following two directives::

  INSTALL(TARGETS user_profile ARCHIVE DESTINATION lib)
  INSTALL(DIRECTORY include/user_profile DESTINATION include)

The destination is relative to the prefix (specified with the --prefix option)
and this in turn is relative to the location specified using --install-destdir.

Now you can try and see if the following works::

  $ python build.py install --prefix=/usr --install-destdir=tmp

You should find that the library as well as the header files have been installed
in the in the tmp/ folder::

  $ find tmp -type f
  tmp/usr/lib/libuser_profile.a
  tmp/usr/include/user_profile/radb_client.hpp
  tmp/usr/include/user_profile/restype_enum.h
  tmp/usr/include/user_profile/user_profile.h

The second step is writing a few debian specific packaging files. Don't worry,
the most complicated ones are automatically generated by mirbuild during the
packaging process. The files you need to create are::

  debian/control
  debian/copyright
  debian/changelog
  debian/lastfm-libuser-profile-dev.install

The control file tells the dpkg toolchain which packages to build and what
their properties are. In our example, the control file might look like this::

  Source: lastfm-libuser-profile
  Section: unknown
  Priority: extra
  Maintainer: Ricky Cormier <ricky@last.fm>
  Build-Depends: debhelper (>= 7), cmake, python-mirbuild,
                 lastfm-libmoost-dev, lastfm-libthrift-fm303-dev,
                 lastfm-libthrift-radb-dev
  Standards-Version: 3.7.3
  
  Package: lastfm-libuser-profile-dev
  Architecture: any
  Depends: ${shlibs:Depends}, ${misc:Depends},
           lastfm-libmoost-dev, lastfm-libthrift-fm303-dev,
           lastfm-libthrift-radb-dev
  Description: header files and static library for the radb user profile library
   user_profile contains functions for querying/modifying user profiles

A more complex project might actually contain more than one just one package.

Preferably, the first line of the Description should be a short and sweet name
for the package, starting in lowercase (unless it starts with an abbreviation)
and not containing any punctuation.

The changelog file contains a changelog that lists all released revisions and
the features they introduced. The changelog can be edited manually or using the
dch tool.

The copyright file usually lists the authors, copyright message and a license
for the project.

Last but not least, for each package defined in the control file, there has to be
an install file. In our case, this is only one called libuser-profile-dev.install
and is looks like this::

  usr/lib/libuser_profile.a
  usr/include/user_profile/*

This tells dpkg to grab all includes below usr/include/user_profile and the
static library for packaging.

That's basically all you need, mirbuild will take care of all the rest for you.
You can now run ::

  $ python build.py package

and should end up with debian source, description and package (deb) files.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'

from mirbuild.project import *
from mirbuild.cmake import *
from mirbuild.scons import *
from mirbuild.python import *
from mirbuild.lua import *
from mirbuild.test import *
from mirbuild.version import *
from mirbuild.thriftinterface import *
from mirbuild.simple import *
from mirbuild.playground import *
