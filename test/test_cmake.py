#!/usr/bin/env python
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

import os, subprocess, sys, re, json, string, platform, glob, posixpath
from mirbuild.tools import ScopedChdir, ScopedFile

try:
    import py.test as pytest
except ImportError:
    import pytest

class TreeWatcher(object):
    def __init__(self, path):
        self.__path = posixpath.realpath(path)
        (self.__od, self.__of) = self.scan()

    def diff(self, relative = False):
        (d, f) = self.scan()
        ef = f - self.__of
        mf = self.__of - f
        ed = d - self.__od
        md = self.__od - d
        if relative:
            ef = set([posixpath.relpath(x, self.__path) for x in ef])
            mf = set([posixpath.relpath(x, self.__path) for x in mf])
            ed = set([posixpath.relpath(x, self.__path) for x in ed])
            md = set([posixpath.relpath(x, self.__path) for x in md])
        return ed, ef, md, mf

    @property
    def same(self):
        (ed, ef, md, mf) = self.diff()
        return not(ed or ef or md or mf)

    def clean(self):
        (ed, ef, md, mf) = self.diff()
        if md or mf:
            print md, mf
            assert False
        else:
            for f in ef:
                os.remove(f)
            for d in ed:
                os.rmdir(d)

    def scan(self):
        dirs = set()
        files = set()
        for r, d, f in os.walk(self.__path):
            dirs |= set(map(lambda x: posixpath.join(r, x), d))
            files |= set(map(lambda x: posixpath.join(r, x), f))
        return dirs, files

class ScopedRename(object):
    def __init__(self, src, dst, path = None):
        if path is not None:
            src = posixpath.join(path, src)
            dst = posixpath.join(path, dst)
        self.__src = posixpath.realpath(src)
        self.__dst = posixpath.realpath(dst)
        os.rename(src, dst)

    def __del__(self):
        os.rename(self.__dst, self.__src)

class BPY(object):
    path = 'cmake/path/to/project'
    name = 'build.py'

    def __init__(self, content, *args):
        self.sf = ScopedFile(self.name, content, self.path)
        self.run(*args)

    def __del__(self):
        self.run('realclean')

    @staticmethod
    def buildarch():
        # TODO: enable this once we've moved to at least python2.7
        # return string.strip(subprocess.check_output(['dpkg-architecture', '-qDEB_BUILD_ARCH']))
        return string.strip(subprocess.Popen(['dpkg-architecture', '-qDEB_BUILD_ARCH'], stdout=subprocess.PIPE).communicate()[0])

    @staticmethod
    def debcontents(deb, filter = None):
        # ar t mypackage.deb | grep data.tar
        p1 = subprocess.Popen(['ar', 't', deb],                        stdout = subprocess.PIPE)
        p2 = subprocess.Popen(['grep', 'data.tar'], stdin = p1.stdout, stdout = subprocess.PIPE)
        p1.stdout.close()
        datafile = p2.communicate()[0].strip()

        decompressor = "gzip"
        if datafile.endswith(".xz"):
            decompressor = "xz"

        # ar p mypackage.deb data.tar.gz | gzip -dc | tar tf -
        p1 = subprocess.Popen(['ar', 'p', deb, datafile],                    stdout = subprocess.PIPE)
        p2 = subprocess.Popen([decompressor, '-dc'],      stdin = p1.stdout, stdout = subprocess.PIPE)
        p3 = subprocess.Popen(['tar', 'tf', '-'],         stdin = p2.stdout, stdout = subprocess.PIPE)
        p1.stdout.close()
        p2.stdout.close()
        output = p3.communicate()[0]
        dirs = []
        files = []
        for line in re.split('\r?\n', output):
            if line and (filter is None or filter(line)):
                if re.search('/$', line):
                    dirs.append(line)
                else:
                    files.append(line)
        return dirs, files

    @staticmethod
    def srccontents(src, filter = None):
        p1 = subprocess.Popen(['gzip', '-dc', src], stdout = subprocess.PIPE)
        p2 = subprocess.Popen(['tar', 'tf', '-'], stdin = p1.stdout, stdout = subprocess.PIPE)
        p1.stdout.close()
        output = p2.communicate()[0]
        dirs = []
        files = []
        for line in re.split('\r?\n', output):
            if line and (filter is None or filter(line)):
                if re.search('/$', line):
                    dirs.append(line)
                else:
                    files.append(line)
        return dirs, files

    @property
    def cache(self):
        try:
            return json.load(open(posixpath.join(self.path, 'configure.json'), 'r'))
        except Exception:
            return None

    @property
    def config(self):
        try:
            cfg = { 'var': {} }

            cfgfile = open(posixpath.join(self.path, 'config.cmake')).read()

            ms = re.findall('SET\((\w+)\s+([^)]+)\)', cfgfile)
            for m in ms:
                if m is not None:
                    cfg['var'][m[0]] = m[1]

            ms = re.findall('(\w+)\(([^)]+)\)', cfgfile, re.MULTILINE)
            for m in ms:
                if m is not None:
                    cfg[m[0]] = m[1]

            return cfg

        except Exception:
            return None

    @property
    def test_output(self):
        tout = {}
        current = None
        summary = None
        for line in re.split('\r?\n', self.out):
            m = re.match('=+\s*Running Test\s*\[\s*(.*?)\s*\]\s*=+$', line)
            if m is not None:
                current = m.group(1)
                tout[current] = []
            elif current is not None:
                if re.match('---------------------------------------+$', line):
                    current = None
                elif re.search('\S', line):
                    tout[current].append(line)
            m = re.match('(\d+)/(\d+) tests? passed in.*?---\s*(.+?)\s*$', line)
            if m is not None:
                summary = [int(m.group(1)), int(m.group(2)), m.group(3)]
        return tout, summary

    def run(self, *args):
        scd = ScopedChdir(self.path)
        bpy = subprocess.Popen([sys.executable, self.name] + list(args), \
                               stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        (self.out, self.err) = bpy.communicate()
        self.exitcode = bpy.returncode
        print "=================\n{0}\n------------\n{1}------------\n{2}------------\nexitcode: {3}\n------------" \
              .format(' '.join([sys.executable, self.name] + list(args)), self.out, self.err, self.exitcode)

    def parse_help(self):
        self.has_usage = re.match('Usage: ' + self.name, self.out) != None
        m = re.search('Commands: (.*)', self.out)
        self.commands = re.split(',\s*', m.group(1))
        m = re.search('Build Configurations: (.*)', self.out)
        self.configs = re.split(',\s*', m.group(1))
        self.parse_options()

    def parse_options(self):
        self.options = {}
        section = None
        for line in re.split('\n', self.out):
            m = re.match('\s*(.+?)\s*Options:', line)
            if m is not None:
                section = m.group(1)
                self.options[section] = {}
                current = None
            elif section is not None:
                m = re.match('\s*(?:-(\w)(?:\s+\w+)?,\s*)?--([\w-]+)(?:=\w+)?\s*(.*)$', line)
                if m is not None:
                    current = m.group(2)
                    self.options[section][current] = {
                        'short': m.group(1),
                        'long': m.group(2),
                        'help': m.group(3),
                        'default': None
                    }
                elif current is not None and re.search('\S', line):
                    self.options[section][current]['help'] += re.sub('^\s*', '\n', line)
        for s in self.options.itervalues():
            for o in s.itervalues():
                o['help'] = re.sub('^\s+', '', o['help'])
                rex = re.compile('\s*\[default:\s*(.+)\]$', re.DOTALL)
                m = re.search(rex, o['help'])
                if m is not None:
                    o['default'] = re.sub('\n', '', m.group(1))
                    o['help'] = re.sub(rex, '', o['help'])

# ensure there are no packaging files lurking around from a previous failed run
for path in glob.glob(posixpath.split(BPY.path)[0] + '/*') + [
              posixpath.join(BPY.path, 'debian', 'rules'),
              posixpath.join(BPY.path, 'debian', 'compat'),
              posixpath.join(BPY.path, 'debian', 'source', 'local-options')
            ]:
    if not posixpath.isdir(path):
        try:
            os.remove(path)
        except OSError:
            pass
try:
    os.rmdir(posixpath.join(BPY.path, 'debian', 'source'))
except OSError:
    pass

def have_dpkg():
    try:
        BPY.buildarch()
        return True
    except Exception:
        return False

def tar_ignore_supported():
    output = subprocess.Popen(['dpkg-source', '--version'], stdout=subprocess.PIPE).communicate()[0]
    m = re.search('version\s+(\d+(?:\.\d+)+)', output)
    v = re.split('\.', m.group(1))
    return int(v[0]) > 1 or (int(v[0]) == 1 and int(v[1]) > 14)

LIB_a = posixpath.realpath('cmake/a')
LIB_b = posixpath.realpath('cmake/b')

BPY_std = """import mirbuild
mirbuild.CMakeProject('test').run()
"""

BPY_dep = """import mirbuild
project = mirbuild.CMakeProject('test')
project.depends('foo', 'oh-my')
project.define('HAVE_LIB_A')
project.define('HAVE_LIB_B')
project.run()
"""

BPY_ver = """import mirbuild
project = mirbuild.CMakeProject('test')
project.version('include/test/version.h')
project.define('HAS_VERSION_H')
project.run()
"""

BPY_ver_arg = """import mirbuild
project = mirbuild.CMakeProject('test')
project.test(
  mirbuild.CMakeTestBuilder(project.env, 'test/a', ['a_test', 'test', 'fail']),
  mirbuild.CMakeTestBuilder(project.env, 'test/b', ['b_test', 'test', 'fail']),
  mirbuild.CMakeTestBuilder(project.env, 'test/e', ['e_test', 'test', 'fail']),
)
project.run()
"""

BPY_pkg = """import mirbuild
project = mirbuild.CMakeProject('test')
rules = mirbuild.packagers.DebianRules()
rules.target_append('override_dh_auto_install', ['mkdir -p $(TMP)/usr/etc',
                           '(cd $(TMP)/usr/etc && ln -sf ../lib bla);'])
project.package(mirbuild.packagers.DebianPackaging(project.env, rules))
project.run()
"""

RC = """
[build]
configuration=debug

[dependencies]
foo={0}
oh-my={1}

[test:boost]
log_level=nothing
log_sink=stderr
""".format(LIB_a, LIB_b)

RC2 = """
[build]
configuration=debug
include_path={0}/include
library_path={0}/lib

[dependencies]
oh-my={1}

[test:boost]
log_level=nothing
log_sink=stderr
""".format(LIB_a, LIB_b)

RC_PKG = """
[packaging:debian]
buildpackage_args = ["-d", "-tc", "-us", "-uc"]
"""

CONTROL = """Source: test
Section: unknown
Priority: extra
Maintainer: Marcus Holland-Moritz <marcus@last.fm>
Build-Depends: debhelper (>=7), cmake
Standards-Version: 3.7.3

Package: libtest-dev
Architecture: any
Depends: ${shlibs:Depends}, ${misc:Depends}
Description: Header files and static libs for test
 The test library is a foo.
"""

INSTALL = """usr/lib/libtest*.a
usr/include/test/*
"""

INSTALL_etc = """usr/lib/libtest*.a
usr/include/test/*
usr/etc/*
"""

def test_usage():
    bpy = BPY(BPY_std)
    bpy.parse_help()
    assert bpy.err == ''
    assert bpy.has_usage
    assert bpy.exitcode == 0
    assert set(bpy.options.keys()) == set(['General', 'Boost Test', 'CMake Coverage'])
    assert set(bpy.commands) == set(['build', 'clean', 'configure', 'coverage', 'has', 'install', \
                                    'uninstall', 'meta', 'distclean', 'realclean', 'test'])

def test_usage_help():
    bpy = BPY(BPY_std, '--help')
    bpy.parse_help()
    assert bpy.err == ''
    assert bpy.has_usage
    assert bpy.exitcode == 0
    assert set(bpy.options.keys()) == set(['General', 'Boost Test', 'CMake Coverage'])

def test_usage_no_tests():
    srn = ScopedRename('test', 'testxxx', BPY.path)
    bpy = BPY(BPY_std)
    bpy.parse_help()
    assert bpy.err == ''
    assert bpy.has_usage
    assert bpy.exitcode == 0
    assert set(bpy.options.keys()) == set(['General', 'CMake Coverage'])

def test_usage_with_package():
    srn = ScopedFile('debian/control', 'nothing', BPY.path)
    bpy = BPY(BPY_std)
    bpy.parse_help()
    assert bpy.err == ''
    assert bpy.has_usage
    assert bpy.exitcode == 0
    assert set(bpy.options.keys()) == set(['General', 'Boost Test', 'CMake Coverage', 'Debian Packaging'])
    assert set(bpy.commands) == set(['build', 'clean', 'configure', 'coverage', 'has', 'install', \
                                    'uninstall', 'meta', 'package', 'distclean', 'realclean', 'test'])

def test_usage_with_deps():
    bpy = BPY(BPY_dep)
    bpy.parse_help()
    assert bpy.err == ''
    assert bpy.has_usage
    assert bpy.exitcode == 0
    assert set(bpy.options.keys()) == set(['General', 'Boost Test', 'CMake Coverage', 'General Dependency', 'C Library Dependency'])
    assert set(bpy.options['C Library Dependency'].keys()) == set(['with-foo', 'with-oh-my'])

def test_usage_rcfile():
    rc1 = ScopedFile('cmake/path/to/.mirbuildrc', """
[build]
configuration=debug
include_path={0}/include:{1}/include
library_path={1}/lib

[dependencies]
foo={0}

[test:boost]
log_level=all
""".format(LIB_a, LIB_b))
    bpy = BPY(BPY_dep)
    bpy.parse_help()
    assert bpy.err == ''
    assert bpy.has_usage
    assert bpy.exitcode == 0
    assert set(bpy.options.keys()) == set(['General', 'Boost Test', 'CMake Coverage', 'General Dependency', 'C Library Dependency'])
    assert set(bpy.options['C Library Dependency'].keys()) == set(['with-foo', 'with-oh-my'])
    assert set(bpy.configs) >= set(['release', 'debug [*]'])
    assert bpy.options['General']['configuration']['default'] == None
    assert bpy.options['C Library Dependency']['with-foo']['default'] == LIB_a
    assert set(re.split(',\s*', bpy.options['General']['include-path']['default'])) \
               == set([posixpath.join(LIB_a, 'include'), posixpath.join(LIB_b, 'include')])
    assert set(re.split(',\s*', bpy.options['General']['library-path']['default'])) \
               == set([posixpath.join(LIB_b, 'lib')])
    assert bpy.options['Boost Test']['boost-test-log-level']['default'] == 'all'

def test_usage_rcfile_multi():
    rc1 = ScopedFile('cmake/path/to/.mirbuildrc', """
[build]
include_path={0}/include:{1}/include

[dependencies]
oh-my={0}

[test:boost]
log_sink=stderr
""".format(LIB_a, LIB_b))
    rc2 = ScopedFile('cmake/path/.mirbuildrc', """
[build]
configuration=release
library_path={0}/lib

[dependencies]
foo={0}
oh-my=/oh/no
""".format(LIB_b))
    rc3 = ScopedFile('cmake/.mirbuildrc', """
[build]
configuration=debug

[test:boost]
log_level=nothing
log_sink=/some/where
""")

    bpy = BPY(BPY_dep)
    bpy.parse_help()

    assert bpy.err == ''
    assert bpy.has_usage
    assert bpy.exitcode == 0
    assert bpy.cache is None

    assert set(bpy.options.keys()) == set(['General', 'Boost Test', 'CMake Coverage', 'General Dependency', 'C Library Dependency'])
    assert set(bpy.options['C Library Dependency'].keys()) == set(['with-foo', 'with-oh-my'])
    assert set(bpy.configs) >= set(['release [*]', 'debug'])
    assert bpy.options['General']['configuration']['default'] == None
    assert bpy.options['C Library Dependency']['with-foo']['default'] == LIB_b
    assert bpy.options['C Library Dependency']['with-oh-my']['default'] == LIB_a
    assert set(re.split(',\s*', bpy.options['General']['include-path']['default'])) \
               == set([posixpath.join(LIB_a, 'include'), posixpath.join(LIB_b, 'include')])
    assert set(re.split(',\s*', bpy.options['General']['library-path']['default'])) \
               == set([posixpath.join(LIB_b, 'lib')])
    assert bpy.options['Boost Test']['boost-test-log-level']['default'] == 'nothing'
    assert bpy.options['Boost Test']['boost-test-log-sink']['default'] == 'stderr'

    bpy.run('configure')

    cache = bpy.cache
    cfg = bpy.config
    assert bpy.err == ''
    assert bpy.exitcode == 0
    assert cache is not None
    assert cache.has_key(sys.platform)
    cache = cache[sys.platform]
    assert cache['test_runners']['boost']['log_sink'] == 'stderr'
    assert cache['test_runners']['boost']['log_level'] == 'nothing'
    assert cache['dependencies']['foo']['path'] == LIB_b
    assert cache['dependencies']['oh-my']['path'] == LIB_a
    assert set(cache['general']['include_path']) \
               == set([posixpath.join(LIB_a, 'include'), posixpath.join(LIB_b, 'include')])
    assert set(cache['general']['library_path']) \
               == set([posixpath.join(LIB_b, 'lib')])
    assert cache['general']['configuration'] == 'release'
    assert cfg is not None
    assert cfg['var']['CMAKE_BUILD_TYPE'] == 'release'
    assert string.count(cfg['INCLUDE_DIRECTORIES'], posixpath.join(LIB_a, 'include')) >= 1
    assert string.count(cfg['INCLUDE_DIRECTORIES'], posixpath.join(LIB_b, 'include')) >= 1
    assert string.count(cfg['LINK_DIRECTORIES'], posixpath.join(LIB_a, 'lib')) >= 1
    assert string.count(cfg['LINK_DIRECTORIES'], posixpath.join(LIB_b, 'lib')) >= 1

    bpy.run('configure', '--boost-test-log-sink=filename.out', '-c', 'debug', '--with-foo=' + LIB_a, \
                         '--prefix=/opt/bpy', '--library-path=' + posixpath.join(LIB_a, 'lib'))

    cache = bpy.cache
    cfg = bpy.config
    assert bpy.err == ''
    assert bpy.exitcode == 0
    assert cache is not None
    assert cache.has_key(sys.platform)
    cache = cache[sys.platform]
    assert cache['test_runners']['boost']['log_sink'] == 'filename.out'
    assert cache['test_runners']['boost']['log_level'] == 'nothing'
    assert cache['dependencies']['foo']['path'] == LIB_a
    assert cache['dependencies']['oh-my']['path'] == LIB_a
    assert set(cache['general']['include_path']) \
               == set([posixpath.join(LIB_a, 'include'), posixpath.join(LIB_b, 'include')])
    assert set(cache['general']['library_path']) \
               == set([posixpath.join(LIB_a, 'lib'), posixpath.join(LIB_b, 'lib')])
    assert cache['general']['configuration'] == 'debug'
    assert cfg is not None
    assert cfg['var']['CMAKE_BUILD_TYPE'] == 'debug'
    assert cfg['var']['CMAKE_INSTALL_PREFIX'] == '/opt/bpy'
    assert string.count(cfg['INCLUDE_DIRECTORIES'], posixpath.join(LIB_a, 'include')) >= 1
    assert string.count(cfg['LINK_DIRECTORIES'], posixpath.join(LIB_a, 'lib')) >= 1

    bpy.run()
    bpy.parse_help()

    assert bpy.err == ''
    assert bpy.has_usage
    assert bpy.exitcode == 0
    assert set(bpy.configs) >= set(['release', 'debug [*]'])
    assert bpy.options['C Library Dependency']['with-foo']['default'] == LIB_a
    assert bpy.options['C Library Dependency']['with-oh-my']['default'] == LIB_a
    assert set(re.split(',\s*', bpy.options['General']['include-path']['default'])) \
               == set([posixpath.join(LIB_a, 'include'), posixpath.join(LIB_b, 'include')])
    assert set(re.split(',\s*', bpy.options['General']['library-path']['default'])) \
               == set([posixpath.join(LIB_a, 'lib'), posixpath.join(LIB_b, 'lib')])
    assert bpy.options['Boost Test']['boost-test-log-sink']['default'] == 'filename.out'

def test_invalid_command():
    bpy = BPY(BPY_std, 'woot')
    assert re.search('ERROR: Invalid command "woot"', bpy.err)
    assert bpy.out == ''
    assert bpy.exitcode > 0

def test_ambiguous_command():
    bpy = BPY(BPY_std, 'c')
    assert re.search('ERROR: Ambiguous command "c"', bpy.err)
    assert bpy.out == ''
    assert bpy.exitcode > 0

def test_meta():
    tw = TreeWatcher(BPY.path)
    bpy = BPY(BPY_std, 'meta')
    assert bpy.err == ''
    assert bpy.exitcode == 0
    meta = json.loads(bpy.out)
    assert meta == { 'project': 'test', 'dependencies': [], 'version': '2.0.18',
                     'commands': 'build clean configure coverage distclean has install meta realclean test uninstall'.split() }
    (ed, ef, md, mf) = tw.diff(relative = True)
    assert not (md or mf or ed)
    assert ef == set(['build.py'])

def test_meta_dep():
    bpy = BPY(BPY_dep, 'meta')
    assert bpy.err == ''
    assert bpy.exitcode == 0
    meta = json.loads(bpy.out)
    assert meta == { 'project': 'test', 'dependencies': ['foo', 'oh-my'], 'version': '2.0.18',
                     'commands': 'build clean configure coverage distclean has install meta realclean test uninstall'.split() }

def test_meta_control():
    scon = ScopedFile('debian/control', CONTROL, BPY.path)
    bpy = BPY(BPY_dep, 'meta')
    assert bpy.err == ''
    assert bpy.exitcode == 0
    meta = json.loads(bpy.out)
    assert meta == { 'project': 'test', 'dependencies': ['foo', 'oh-my'], 'version': '2.0.18',
                     'packaging': { 'debian': { 'source': 'test', 'package': [ 'libtest-dev' ] } },
                     'commands': 'build clean configure coverage distclean has install meta package realclean test uninstall'.split() }

def test_build():
    rc = ScopedFile('cmake/.mirbuildrc', RC)
    tw = TreeWatcher(BPY.path)
    bpy = BPY(BPY_dep, 'build')
    assert bpy.exitcode == 0
    (ed, ef, md, mf) = tw.diff(relative = True)
    assert not (md or mf)
    assert set(['lib/libtest.a', 'configure.json', 'config.cmake']) <= ef
    assert set(['test/a/bin/test', 'test/b/bin/test', 'test/e/bin/test']).isdisjoint(ef)
    bpy.run('realclean')
    assert bpy.exitcode == 0
    (ed, ef, md, mf) = tw.diff(relative = True)
    assert not (md or mf or ed)
    assert ef == set(['build.py'])

def test_test():
    rc = ScopedFile('cmake/.mirbuildrc', RC)
    tw = TreeWatcher(BPY.path)
    bpy = BPY(BPY_ver, 'test')
    assert bpy.exitcode == 0
    (ed, ef, md, mf) = tw.diff(relative = True)
    assert not (md or mf)
    assert set(['lib/libtest.a', 'configure.json', 'config.cmake', \
                'test/a/bin/test', 'test/b/bin/test', 'test/e/bin/test']) <= ef
    (to, summary) = bpy.test_output
    assert set(to.keys()) == set(['a_test', 'b_test', 'e_test'])
    assert summary == [3, 3, 'ALL TESTS PASSED']
    assert posixpath.isabs(to['a_test'][0])
    assert set(to['a_test'][1:]) >= set(['--log_level=nothing', '--log_sink=stderr'])
    ver = {}
    for l in to['e_test']:
        (k, v) = re.sub('^TEST_', '', l).split('=')
        ver[k] = v
    assert ver['PROJECT_STR'] == 'test'
    assert ver['PACKAGE_STR'] == 'test'
    assert ver['AUTHOR_STR'] == 'Marcus Holland-Moritz <marcus@last.fm>'
    assert ver['RELEASE_ISODATE_STR'] == '2011-07-24T17:58:15+00:00'
    assert ver['RELEASE_YEAR_STR'] == '2011'
    assert ver['RELEASE_DATE_STR'] == '2011-07-24'
    assert ver['RELEASE_TIME_STR'] == '17:58:15'
    assert ver['FULL_REVISION_STR'] == '2.0.18-1-git.f76b429-1'
    assert ver['REVISION_STR'] == '2.0.18'
    assert int(ver['RELEASE_YEAR']) == 2011
    assert int(ver['RELEASE_EPOCH_TIME']) == 1311530295
    assert int(ver['MAJOR_REVISION']) == 2
    assert int(ver['MINOR_REVISION']) == 0
    assert int(ver['PATCHLEVEL']) == 18
    bpy.run('realclean')
    assert bpy.exitcode == 0
    (ed, ef, md, mf) = tw.diff(relative = True)
    assert not (md or mf or ed)
    assert ef == set(['build.py'])

def test_test_dep():
    rc = ScopedFile('cmake/.mirbuildrc', RC2)
    bpy = BPY(BPY_dep, 'test')
    assert bpy.exitcode == 0
    (to, summary) = bpy.test_output
    assert set(to.keys()) == set(['a_test', 'b_test', 'e_test'])
    assert summary == [3, 3, 'ALL TESTS PASSED']
    assert set(to['b_test']) == set(['a(12)=54', 'b(23)=4734'])

def test_test_arg_fail():
    rc = ScopedFile('cmake/.mirbuildrc', RC)
    bpy = BPY(BPY_ver_arg, 'test')
    assert bpy.exitcode > 0
    (to, summary) = bpy.test_output
    assert set(to.keys()) == set(['a_test', 'b_test', 'e_test'])
    assert summary == [2, 3, '1 TEST FAILED']
    assert set(to['a_test'][1:]) >= set(['fail', '--log_level=nothing', '--log_sink=stderr'])

def test_package():
    if not have_dpkg():
        pytest.skip("unsupported configuration")
    rc = ScopedFile('cmake/.mirbuildrc', RC_PKG)
    scon = ScopedFile('debian/control', CONTROL, BPY.path)
    sins = ScopedFile('debian/libtest-dev.install', INSTALL, BPY.path)
    sgit = ScopedFile('.git/foo', 'nothing', BPY.path)
    debdir = posixpath.split(BPY.path)[0]
    tw = TreeWatcher(debdir)
    bpy = BPY(BPY_ver, 'package')
    assert bpy.exitcode == 0
    (ed, ef, md, mf) = tw.diff(relative = True)
    assert not (md or mf or ed)
    deb = 'libtest-dev_2.0.18-1-git.f76b429-1_' + BPY.buildarch() + '.deb'
    src = 'test_2.0.18-1-git.f76b429-1.tar.gz'
    assert ef == set(['project/build.py', deb, 'test_2.0.18-1-git.f76b429-1_' + BPY.buildarch() + '.changes',
                      'test_2.0.18-1-git.f76b429-1.dsc', 'test_2.0.18-1-git.f76b429-1.tar.gz'])
    (dirs, files) = BPY.debcontents(posixpath.join(debdir, deb), filter = lambda x: not re.match('\./usr/share/doc', x))
    print dirs, files
    assert set(files) == set(['./usr/lib/libtest.a', './usr/include/test/version.h', './usr/include/test/test.h'])
    (dirs, files) = BPY.srccontents(posixpath.join(debdir, src), filter = lambda x: re.search('/\.git/', x))
    print dirs, files
    if tar_ignore_supported():
        assert set(files) == set() and set(dirs) == set()
    del bpy     # force cleanup
    tw.clean()

def test_package_keep_rules():
    if not have_dpkg():
        pytest.skip("unsupported configuration")
    rc = ScopedFile('cmake/.mirbuildrc', RC_PKG)
    scon = ScopedFile('debian/control', CONTROL, BPY.path)
    sins = ScopedFile('debian/libtest-dev.install', INSTALL_etc, BPY.path)
    sgit = ScopedFile('.git/foo', 'nothing', BPY.path)
    debdir = posixpath.split(BPY.path)[0]
    tw = TreeWatcher(debdir)
    bpy = BPY(BPY_pkg, 'package', '--debian-pkg-keep-rules')
    assert bpy.exitcode == 0
    (ed, ef, md, mf) = tw.diff(relative = True)
    assert not (md or mf or ed)
    deb = 'libtest-dev_2.0.18-1-git.f76b429-1_' + BPY.buildarch() + '.deb'
    src = 'test_2.0.18-1-git.f76b429-1.tar.gz'
    assert ef == set(['project/build.py', 'project/debian/rules', deb, 'test_2.0.18-1-git.f76b429-1_' + BPY.buildarch() + '.changes',
                      'test_2.0.18-1-git.f76b429-1.dsc', 'test_2.0.18-1-git.f76b429-1.tar.gz'])
    (dirs, files) = BPY.debcontents(posixpath.join(debdir, deb), filter = lambda x: not re.match('./usr/share/doc', x))
    print dirs, files
    assert set(files) == set(['./usr/lib/libtest.a', './usr/etc/bla', './usr/include/test/test.h'])
    (dirs, files) = BPY.srccontents(posixpath.join(debdir, src), filter = lambda x: re.search('/\.git/', x))
    print dirs, files
    if tar_ignore_supported():
        assert set(files) == set() and set(dirs) == set()
    del bpy     # force cleanup
    tw.clean()

if __name__ == "__main__":
    run = None
    if len(sys.argv) > 1:
        run = map(lambda name: globals()['test_' + name], sys.argv[1:])
    else:
        run = sorted(obj for name, obj in globals().items() if callable(obj) and name.startswith('test_'))
    for f in run:
        print '=========================================================================='
        print '\n  >>>>>  ' + f.__name__ + '  <<<<<\n'
        print '=========================================================================='
        f()
