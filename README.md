mirbuild
========

*mirbuild* is the build system used for almost all projects in Last.fm's MIR team. It makes it extremely easy to build, test, install and package

* C++ libraries and services,
* Thrift interfaces and
* Python libraries.

It takes care of

* handling dependencies between projects,
* doing debug, release and code-coverage builds,
* running code coverage tools and
* creating debian packages.

Installation
------------

*mirbuild* is written in Python and needs the setuptools, dateutil, debian and pytest libraries. It also needs cmake for building C++ projects and for running the test suite.

You can build and test *mirbuild* with

  ./build.py test

and install it using:

  sudo ./build.py install

Usage
-----

Have a look at mirbuild/__init__.py for some usage examples. There's no need to install mirbuild to be able to use it,

  export PYTHONPATH=/path/to/python-mirbuild

is sufficient.

It helps to stick to a certain structure when building projects with dependencies. Ideally, all projects are either in the same directory or at least below a certain common directory. To automatically build a project and its dependencies, you can run:

  python -m mirbuild.walk -p project build

To build a single project when you know that all dependencies are up-to-date and in the directory above, run:

  ./build.py --with-deps=.. build
