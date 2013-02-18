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
Test modeling classes

The classes in this file implement support for different test frameworks.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'BoostTestRunner Test'.split()

import os, re, time
from mirbuild.tools import ScopedChdir
from mirbuild.options import LocalOptions
from optparse import OptionGroup

class Test(object):
    def __init__(self, name, test, *args):
        self.__time = None
        self.__passed = None
        self.__name = name
        self.__test = test
        self.__args = args

    @property
    def name(self):
        assert self.__name is not None
        return self.__name

    @property
    def test(self):
        assert self.__test is not None
        return self.__test

    @property
    def args(self):
        return self.__args

    @property
    def duration(self):
        assert self.__time is not None
        return self.__time

    @property
    def passed(self):
        assert self.__passed is not None
        return self.__passed

    @property
    def failed(self):
        return not self.passed

    def start_timer(self):
        assert self.__time is None
        self.__time = time.time()

    def set_passed(self, passed = True):
        assert self.__time is not None
        assert self.__passed is None
        self.__time = time.time() - self.__time
        self.__passed = passed

class TestObserver(object):
    def __init__(self):
        self.__results = []

    def add_test(self, result):
        assert isinstance(result, Test)
        self.__results.append(result)

    @property
    def num_total(self):
        return len(self.__results)

    @property
    def num_passed(self):
        return len([x for x in self.__results if x.passed])

    @property
    def num_failed(self):
        return self.num_total - self.num_passed

    @property
    def total_duration(self):
        return sum(map(lambda x: x.duration, self.__results))

    def report(self):
        return '''
------------------------------------------------------------------------
{0}/{1} test{2} passed in {3:.2f} seconds --- {4}
------------------------------------------------------------------------
'''.format(self.num_passed, self.num_total, 's' if self.num_passed != 1 else '', self.total_duration,
           'ALL TESTS PASSED' if self.num_failed == 0 else '{0} TEST{1} FAILED'.format(self.num_failed, 'S' if self.num_failed != 1 else ''))

class TestWrapper(object):
    def __init__(self, builder, runner):
        self.__builder = builder
        self.__runner = runner

    @property
    def dir(self):
        return self.__builder.dir

    def configure(self):
        self.__builder.configure()

    def clean(self):
        self.__builder.clean()

    def build(self):
        self.__builder.build()

    def run(self, observer):
        self.__builder.run(self.__runner, observer)

class TestBuilder(object):
    _testclass = Test

    def __init__(self, env, dir, *args):
        self._env = env
        self.__dir = dir
        self.__tests = []
        for a in args:
            self.add_test(a)

    @staticmethod
    def looks_like_test_dir(dir):
        return True

    def __test_name(self, path):
        if self.dir is not None:
            path = os.path.join(self.dir, path)
        parts = []
        while path != '':
            (path, tail) = os.path.split(path)
            if tail == '' or (parts and tail == 'test'):
                break
            parts.append(tail)
        parts.reverse()
        return '_'.join(parts)

    def add_test(self, test):
        if isinstance(test, Test):
            pass
        elif isinstance(test, basestring):
            test = self._testclass(self.__test_name(test), test)
        else:
            test = self._testclass(*test)
        self._env.dbg('added test case: ' + test.name)
        self.__tests.append(test)

    @property
    def dir(self):
        return self.__dir

    @property
    def tests(self):
        return self.__tests

    def run(self, runner, observer):
        runner.execute(self.dir, self.tests, observer)

    def configure(self):
        pass

    def build(self):
        pass

    def clean(self):
        pass

class TestRunner(object):
    def __init__(self, env):
        self._env = env

    def add_options(self, parser):
        pass

    def set_cache(self, cache):
        pass

class BoostTestRunner(TestRunner):
    name = 'boost'

    def __init__(self, env):
        TestRunner.__init__(self, env)
        self.__opt = LocalOptions('boost')

    def add_options(self, parser):
        boost = OptionGroup(parser, "Boost Test Options")
        self.__opt.add_option(boost, '--boost-test-output-dir', type = 'string', dest = 'output_dir', metavar = 'PATH',
                              help = 'write test log/result files to this directory')
        self.__opt.add_option(boost, '--boost-test-log-format', type = 'string', dest = 'log_format', metavar = 'FORMAT',
                              help = 'log output format (HRF, XML)')
        self.__opt.add_option(boost, '--boost-test-log-sink', type = 'string', dest = 'log_sink', metavar = 'FILE',
                              help = 'stdout/stderr or file pattern for log files')
        self.__opt.add_option(boost, '--boost-test-log-level', type = 'string', dest = 'log_level', metavar = 'LEVEL',
                              help = 'test log level (e.g. all, warning, error, nothing)')
        self.__opt.add_bool_option(boost, '--boost-test-show-progress', dest = 'show_progress',
                                   help = 'display progress indicator during test run')
        parser.add_option_group(boost)

    def set_cache(self, cache):
        cache.register(self.__opt)

    def __output_file(self, basedir, template, name):
        path = re.sub('\{name\}', name, template)
        if os.path.dirname(path) == '' and self.__opt.output_dir:
            path = ofspath.join(self.__opt.output_dir, path)
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(basedir, path))
        return path

    def execute(self, dir, tests, observer):
        genopt = []
        if self.__opt.log_format:
            genopt.append('--log_format=' + self.__opt.log_format)
        if self.__opt.log_level:
            genopt.append('--log_level=' + self.__opt.log_level)
        if self.__opt.show_progress:
            genopt.append('--show_progress')

        dir = os.path.join(dir, self._env.bin_dir)
        scd = ScopedChdir(dir)

        for t in tests:
            assert isinstance(t, Test)
            opt = genopt[:]
            if self.__opt.log_sink:
                sink = self.__opt.log_sink
                if sink not in ('stdout', 'stderr'):
                    if self.__opt.show_progress:
                        raise RuntimeError('using --boost-test-show-progress corrupts output files')
                    sink = self.__output_file(scd.original_dir, sink, t.name)
                opt.append('--log_sink=' + sink)
            opt += t.args
            self._env.say('\n=== Running Test [ {0} ] ===\n'.format(t.name))
            t.start_timer()
            try:
                self._env.execute(os.path.realpath(t.test), *opt)
                t.set_passed()
            except RuntimeError:
                t.set_passed(False)
            self._env.dbg('Test {0} finished in {1:.2f} seconds.'.format(t.name, t.duration))
            observer.add_test(t)

    def state_merge(self, value):
        self.__opt.state_merge(value)
