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
A simple project class

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'SimpleProject SimpleTestBuilder SimpleTestRunner'.split()

import os

import mirbuild.project

from mirbuild.tools import ScopedChdir

class SimpleTestBuilder(mirbuild.test.TestBuilder):
    def __init__(self, env, dir, *args):
        mirbuild.test.TestBuilder.__init__(self, env, dir, *args)

    def build(self):
        if self.dir is not None:
            if not self.tests:
                for e in os.listdir(self.dir):
                    epath = os.path.join(self.dir, e)
                    if os.access(epath, os.X_OK):
                        self.add_test(e)

class SimpleTestRunner(mirbuild.test.TestRunner):
    name = 'simple'

    def execute(self, dir, tests, observer):
        scd = ScopedChdir(dir)
        for t in tests:
            assert isinstance(t, mirbuild.test.Test)
            self._env.say('\n=== Running Test [ {0} ] ===\n'.format(t.name))
            t.start_timer()
            try:
                self._env.execute(os.path.realpath(t.test))
                t.set_passed()
            except RuntimeError:
                t.set_passed(False)
            self._env.dbg('Test {0} finished in {1:.2f} seconds.'.format(t.name, t.duration))
            observer.add_test(t)

class SimpleProject(mirbuild.project.Project):
    test_builder_class = SimpleTestBuilder
    test_runner_class = SimpleTestRunner

    def do_configure(self):
        pass

    def do_build(self):
        pass

    def do_clean(self):
        pass

    def do_realclean(self):
        pass

    def do_install(self):
        pass
