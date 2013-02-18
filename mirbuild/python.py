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
Python specific classes

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'PythonProject PythonTestBuilder PythonTestRunner PythonHelpers'.split()

import errno
import os
import glob
import re
import shutil
import sys

import mirbuild.project
import mirbuild.test
import mirbuild.version

from mirbuild.tools import LazyFileWriter, ScopedChdir

class PythonTestBuilder(mirbuild.test.TestBuilder):
    def __init__(self, env, dir, *args):
        mirbuild.test.TestBuilder.__init__(self, env, dir, *args)

    @staticmethod
    def looks_like_test_dir(dir):
        for py in os.listdir(dir):
            path = os.path.join(dir, py)
            if os.path.isfile(path) and PythonTestBuilder.looks_like_test_file(path):
                return True
        return False

    @staticmethod
    def looks_like_test_file(file):
        for line in open(file):
            if re.search('import\s+py\.?test', line):
                return True
        return False

    def build(self):
        if self.dir is not None:
            if not self.tests:
                for e in os.listdir(self.dir):
                    if e.endswith('.py'):
                        epath = os.path.join(self.dir, e)
                        if os.path.isfile(epath) and PythonTestBuilder.looks_like_test_file(epath):
                            self.add_test(e)

class PythonTestRunner(mirbuild.test.TestRunner):
    name = 'python'

    def execute(self, dir, tests, observer):
        oldpypath = os.environ.get('PYTHONPATH', None)
        try:
            os.environ['PYTHONPATH'] = ':'.join([os.path.realpath(p) for p in glob.glob('build/lib*')])
            scd = ScopedChdir(dir)
            for t in tests:
                assert isinstance(t, mirbuild.test.Test)
                self._env.say('\n=== Running Test [ {0} ] ===\n'.format(t.name))
                t.start_timer()
                try:
                    self._env.execute('py.test', os.path.realpath(t.test))
                    t.set_passed()
                except RuntimeError:
                    t.set_passed(False)
                self._env.dbg('Test {0} finished in {1:.2f} seconds.'.format(t.name, t.duration))
                observer.add_test(t)
        finally:
            if oldpypath is None:
                del os.environ['PYTHONPATH']
            else:
                os.environ['PYTHONPATH'] = oldpypath

class PythonSetupMixin(object):
    def __init__(self):
        self.add_option('--python-egg-directory',
                        dest = 'python_egg_directory',
                        type = 'string',
                        default = None,
                        metavar = 'PATH',
                        help = 'directory into which generated eggs will be moved')
        self._vinfo = mirbuild.version.VersionInfoFactory.create()

    def _exec_python_setup(self, *args):
        self.env.execute(sys.executable,
                         os.path.basename(self.python_setup_file),
                         *args,
                         stdout=sys.stderr,
                         cwd=os.path.dirname(os.path.abspath(self.python_setup_file)))

    @property
    def package_prefix(self):
        source = self._vinfo.package()
        name = self.env.project_name
        return source[:-len(name)] if source.endswith(name) else ''

    def run_bdist_egg(self):
        self.run_configure()
        self._run_plugins('pre_bdist_egg')
        self._run_plugins('bdist_egg')
        self.do_bdist_egg()
        self._run_plugins('post_bdist_egg')

    def do_bdist_egg(self):
        self._exec_python_setup('bdist_egg')
        if self.opt.python_egg_directory:
            dist_directory = os.path.join(os.path.dirname(os.path.abspath(self.python_setup_file)), 'dist')
            egg_files = list(os.path.join(dist_directory, i) for i in os.listdir(dist_directory) if i.endswith('.egg'))
            for i in egg_files:
                # shutil.move fails if file already exists in destination
                # -> remove it first
                try:
                    os.remove(os.path.join(self.opt.python_egg_directory, os.path.basename(i)))
                except OSError as ex:
                    if ex.errno != errno.ENOENT:
                        raise
                shutil.move(i, self.opt.python_egg_directory)

class PythonProject(mirbuild.project.Project, PythonSetupMixin):
    test_builder_class = PythonTestBuilder
    test_runner_class = PythonTestRunner
    python_setup_file = 'setup.py'

    def __init__(self, name, **opts):
        # Steal the 'setup' and 'packages' named parameter
        setup_option = opts.pop('setup', {})
        packages = opts.pop('packages', None)

        # Initialise base class
        mirbuild.project.Project.__init__(self, name, **opts)
        PythonSetupMixin.__init__(self)

        # Build actual list of parameters to setup.py's setup function
        author = re.match('(.*?)\s+<([^>]+)>', self._vinfo.author());

        stripped_project_name = name[7:] if name.startswith('python-') else name

        # These are default members
        setup_info = {
            'name': self.package_prefix + stripped_project_name,
            'version': self._vinfo.upstream_version(),
            'description': '',
            'package_dir': {'': '.'},
            'maintainer': author.group(1),
            'maintainer_email': author.group(2),
            'packages': packages,
        }

        # Override these defaults with user supplied values
        setup_info.update(setup_option)
        self.__setup_info = setup_info

    def do_configure(self):
        if self.__is_autogenerated(self.python_setup_file):
            self.__write_setup_file(self.python_setup_file)

    @property
    def setup_info(self):
        return self.__setup_info

    def __write_setup_file(self, file):
        setup_info = dict(self.__setup_info)

        setup_args = []

        packages = setup_info.pop('packages', None)
        if packages is None:
            # no 'packages' option was given, or it is None
            setup_args.append('packages=find_packages()')
        else:
            setup_args.append('packages={0!r}'.format(packages))

        for key, value in setup_info.iteritems():
            val = self.options.get(key, value)
            setup_args.append('{0}={1!r}'.format(key, val))

        setup = LazyFileWriter(file)
        setup.create()
        setup.write('''#!{0}
#########################################################################
#                                                                       #
#               -----------------------------------------               #
#                THIS FILE WAS AUTOGENERATED BY MIRBUILD                #
#               -----------------------------------------               #
#                                                                       #
#  You can put your own customisations in this file, just remove this   #
#  header and the file won't be cleaned up automatically.               #
#                                                                       #
#########################################################################

from setuptools import setup, find_packages

setup({1})
'''.format(sys.executable, ",\n      ".join(setup_args)))
        setup.commit()

    def do_build(self):
        if self.opt.called_by_packager:
            return
        self._exec_python_setup('build')

    def do_install(self):
        if self.opt.called_by_packager:
            return
        args = ['install']
        if self.opt.install_destdir is not None:
            args.append('--root=' + self.opt.install_destdir)
        args.append('--no-compile')
        self._setup(*args)

    def __is_autogenerated(self, file):
        if not os.path.exists(file):
            return True
        try:
            fh = open(file, 'r')
            for line in fh:
                if re.match('#\s+THIS FILE WAS AUTOGENERATED BY MIRBUILD\s+#', line):
                    return True
        except Exception:
            pass
        return False

    def do_clean(self):
        for root, dirs, files in os.walk('.'):
            for f in files:
                if f.endswith('.pyc'):
                    self.env.remove_files(os.path.join(root, f))
            for d in dirs:
                if d.endswith('.egg-info') or d == '__pycache__':
                    self.env.remove_trees(os.path.join(root, d))
        self.env.remove_files('README.debtags')
        if self.__is_autogenerated(self.python_setup_file):
            self.env.remove_files(self.python_setup_file)
        self.env.remove_trees('build', 'dist')

    def do_realclean(self):
        self.do_clean()

    def prepare_package(self):
        mirbuild.project.Project.prepare_package(self)
        if isinstance(self.packager, mirbuild.packagers.pkg_debian.DebianPackaging):
            # We are building a Python package. The old "dh_pysupport" way of
            # doing this has been deprecated. The new "dh_python2" must be
            # selected by using a corresponding option when calling dh.
            # NB: For as long as we have to support lenny, only add --with python2
            #     if we actually find that dh_python2 is installed.
            if os.path.exists('/usr/bin/dh_python2'):
                self.packager.rules.dh_options += ['--with', 'python2']

            # If this packages comes without a setup.py file, the "build.py configure"
            # step will create one.

            # The build and install steps are calling build.py. Build and
            # install steps for Python Debian packages, however, are a bit
            # more sophisticated, as it includes building and installing
            # the packages for various Python versions. This is best done
            # by the Debian dh scripts.
            # The standard override_dh_auto_{build,install} targets, the
            # way that mirbuild.Project sets them up, call build.py using
            # the "--called-by-packager" option. The strategy here is,
            # that build.py should not call setup.py, but only do the
            # additional build/install steps (e.g. defined by plugins in
            # the build.py file). After the call to build.py, the standard
            # dh_auto_{build,install} executables are called, and they
            # do the real work.
            self.packager.rules.target_prepend('override_dh_auto_build', ['dh_auto_build'])
            self.packager.rules.target_prepend('override_dh_auto_install', ['dh_auto_install'])


class PythonHelpers(object):
    namespace_package_declaration = """\
try:
    # See http://peak.telecommunity.com/DevCenter/setuptools#namespace-packages
    __import__('pkg_resources').declare_namespace(__name__)
except ImportError:
    # See http://docs.python.org/library/pkgutil.html#pkgutil.extend_path
    from pkgutil import extend_path
    __path__ = extend_path(__path__, __name__)\n"""

    @staticmethod
    def modules2namespaces(modules):
        """
        Returns a list of namespaces necessary to host the given modules.
        E.g. ['foo.bar.baz', 'foo.foo.foo', 'foo.foo.bar'] will return
        ['foo', 'foo.bar', 'foo.foo']
        """
        namespaces = []
        for m in modules:
            comp = m.split('.')
            for i in range(1, len(comp)):
                ns = '.'.join(comp[0:i])
                if ns in modules:
                    break
                if ns not in namespaces:
                    namespaces.append(ns)
        return namespaces
