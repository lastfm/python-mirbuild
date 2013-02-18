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
Lua specific classes

These don't really exist yet...

"""

__author__ = 'Ricky Cormier <ricky@last.fm>'
__all__ = 'LuaProject LuaTestBuilder LuaTestRunner LuaTest'.split()

import sys

import mirbuild.project
import mirbuild.test

# TODO: whatever it takes to make this work :)

class LuaTest(mirbuild.test.Test):
    def __init__(self, name, test, *args):
        mirbuild.test.Test.__init__(self, name, sys.executable, test, *args)

class LuaTestBuilder(mirbuild.test.TestBuilder):
    _testclass = LuaTest

class LuaTestRunner(mirbuild.test.TestRunner):
    name = 'lua'

class LuaProject(mirbuild.project.Project):
    test_builder_class = LuaTestBuilder
    test_runner_class = LuaTestRunner

    def __init__(self, name):
        mirbuild.project.Project.__init__(self, name)

    def run_configure(self):
        pass

    def do_build(self):
        pass

    def do_install(self):
        pass

    def do_clean(self):
        pass

    def do_realclean(self):
        pass
