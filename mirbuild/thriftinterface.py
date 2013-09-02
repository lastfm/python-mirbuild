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
Thrift interface classes

This file contains a mirbuild project class for Thrift interface definitions.

"""

__author__ = 'Sven Over <sven@last.fm>'
__all__ = ['ThriftInterface', 'ThriftDependency', 'PyThriftDependency']

import glob
import os
import re
import shutil
import stat
import subprocess
import sys

import mirbuild.dependency
import mirbuild.options
import mirbuild.packagers
import mirbuild.project
import mirbuild.python
import mirbuild.version
import mirbuild.cmake as cmake

_thrift_include_files = set("""TApplicationException.h TLogging.h TProcessor.h
TReflectionLocal.h Thrift.h concurrency/Exception.h concurrency/FunctionRunner.h
concurrency/Monitor.h concurrency/Mutex.h concurrency/PosixThreadFactory.h
concurrency/Thread.h concurrency/ThreadManager.h concurrency/TimerManager.h
concurrency/Util.h config.h processor/PeekProcessor.h processor/StatsProcessor.h
protocol/TBase64Utils.h protocol/TBinaryProtocol.h protocol/TCompactProtocol.h
protocol/TDebugProtocol.h protocol/TDenseProtocol.h protocol/TJSONProtocol.h
protocol/TOneWayProtocol.h protocol/TProtocol.h protocol/TProtocolException.h
protocol/TProtocolTap.h server/TNonblockingServer.h server/TServer.h
server/TSimpleServer.h server/TThreadPoolServer.h server/TThreadedServer.h
transport/TBufferTransports.h transport/TFDTransport.h
transport/TFileTransport.h transport/THttpClient.h transport/THttpServer.h
transport/THttpTransport.h transport/TServerSocket.h
transport/TServerTransport.h transport/TShortReadTransport.h
transport/TSimpleFileTransport.h transport/TSocket.h transport/TSocketPool.h
transport/TTransport.h transport/TTransportException.h
transport/TTransportUtils.h transport/TZlibTransport.h""".split())

class ThriftDependency(mirbuild.dependency.CLibraryDependency):
    def __init__(self, name):
        super(ThriftDependency, self).__init__(name)
        self.__opt = mirbuild.options.LocalOptions(name)

    def apply(self, obj):
        if self._path is not None:
            if hasattr(obj, "add_thrifts_path"):
                path = self._validated_path(None, 'thrifts')
                if os.path.isdir(path):
                    obj.add_thrifts_path(path)
                else:
                    obj.add_thrifts_path(self._validated_path(obj.env, 'share', 'thrifts'))

            # we're applying C++ stuff so let the CLib dependency handle things
            super(ThriftDependency, self).apply(obj)


class PyThriftDependency(mirbuild.dependency.Dependency):
    def __init__(self, name):
        super(PyThriftDependency, self).__init__(name)
        self.__opt = mirbuild.options.LocalOptions(name)

    def set_cache(self, cache):
        cache.register(self.__opt)

    def add_options(self, parser):
        self.__opt.add_option(parser, '--with-{0}'.format(self.name), type = 'string', dest = 'path', metavar = 'PATH',
                              help = 'use {0} includes/libraries from this path'.format(self.name))

    def apply(self, obj):
        if self._path is not None:
            if hasattr(obj, "add_thrifts_path"):
                path = self._validated_path(None, 'thrifts')
                if os.path.isdir(path):
                    obj.add_thrifts_path(path)
                else:
                    obj.add_thrifts_path(self._validated_path(obj.env, 'share', 'thrifts'))

            # Add the thrift path to the library path
            obj.add_library_path(self._path)
            obj.env.dbg('Added lib-path: {0}'.format(self._path))

    @property
    def _path(self):
        return getattr(self.__opt, 'path', None)

    def state_merge(self, value):
        self.__opt.state_merge({ "path": value })

    @property
    def has_options(self):
        return True

    @staticmethod
    def validated_path(basepath, env = None, *path):
        """
        Return the given path prefixed with the path given by the --with-... options

        If an environment is given as keyword parameter 'env', the existence of the
        returned path is checked and a warning is output through the environment
        in case it does not exist.
        """
        if basepath is not None:
            result = os.path.realpath(os.path.join(os.path.expanduser(basepath), *path))

            if env is not None and not os.path.isdir(result):
                env.warn(result + ' not found.')

            return result
        else:
            raise ValueError

    def _validated_path(self, env = None, *path):
        return PyThriftDependency.validated_path(self._path, env, *path)


class ThriftDependencyGroup(mirbuild.dependency.DependencyGroup):
    group_name = 'Thrift Interface Definition'
    managed_classes = [ThriftDependency]


class PyThriftDependencyGroup(mirbuild.dependency.DependencyGroup):
    group_name = 'Py Thrift Interface Def'
    managed_classes = [PyThriftDependency]


mirbuild.dependency.Dependencies.register_group_class(ThriftDependencyGroup)
mirbuild.dependency.Dependencies.register_group_class(PyThriftDependencyGroup)


class ThriftDebianPackaging(mirbuild.packagers.DebianPackaging):
    can_package = None

    def __init__(self, env, deps, languages, build_bin_package, debug):
        super(ThriftDebianPackaging, self).__init__(env)
        self._languages = languages
        self.rules.target_set('override_dh_auto_build', '@echo "Build will happen during install stage"')
        self.rules.target_set('override_dh_auto_clean', '@$(PYTHON) build.py --noconfig clean')
        self.__vinfo = mirbuild.version.DebianVersionInfo('.')
        self.__build_bin_package = build_bin_package
        self._debug = debug
        self._deps = deps

    @property
    def _prefix(self):
        source = self.__vinfo.package()
        name = self._env.project_name
        return source[:-len(name)] if source.endswith(name) else ''

    def package(self):
        thrift_dependency_group = self._deps.get_dependency_group(ThriftDependencyGroup)
        thrift_dependencies = thrift_dependency_group.names if thrift_dependency_group else ()
        self._env.remove_trees('debian')
        self._env.make_dirs('debian', os.path.join('debian', 'source'))
        try:
            os.symlink(os.path.relpath('changelog', 'debian'), os.path.join('debian', 'changelog'))
            build_dep = ["debhelper (>= 7.0.50~)", "python (>= 2.6.6-3~)", "{0}python-mirbuild (>= 0.2.24)".format(self._prefix), "thrift-compiler (>= 0.5.0-lastfm2)"]

            if 'cpp' in self._languages:
                for dep in thrift_dependencies:
                    build_dep.append("{0}{1}".format(self._prefix, dep))
                    build_dep.append("{0}lib{1}-dev".format(self._prefix, dep))
                build_dep += ["cmake (>= 2.8)", "libthrift-dev", "libboost-dev"]

            x_python_version_line = ""
            if 'py' in self._languages:
                build_dep += ["python-setuptools (>= 0.6.14)", "python-thrift"]
                for dep in thrift_dependencies:
                    build_dep.append("{0}python-{1}".format(self._prefix, dep))
                if os.path.exists('/usr/bin/dh_python2'):
                    # dh_python2 does not work on lenny
                    # For the time being, the '--with python2' option is
                    # omitted on lenny machines. This leaves build-dependcies
                    # still incompatible with lenny, but we have to ignore
                    # them anyways for lenny build.
                    # GET RID OF LENNY!
                    x_python_version_line = "X-Python-Version: >= 2.6\n"
                    self.rules.dh_options += ['--with', 'python2']

            open(os.path.join('debian', 'source', 'format'), 'w').write('3.0 (native)\n')
            open(os.path.join('debian', '{0}{1}.install'.format(self._prefix, self._env.project_name)), 'w').write('debian/tmp/usr/share/thrifts\n')
            control = open(os.path.join('debian', 'control'), 'w')

            # source package
            control.write("""Source: {0}{1}
Section: devel
Priority: optional
Maintainer: {2}
Build-Depends: {3}
{4}Standards-Version: 3.9.2.0

""".format(self._prefix, self._env.project_name, self.__vinfo.author(), ", ".join(build_dep), x_python_version_line))

            # thrift idl package
            depends = ['${misc:Depends}']
            for dep in thrift_dependencies:
                depends.append("{0}{1}".format(self._prefix, dep))
            control.write("""Package: {0}{1}
Architecture: all
Depends: {2}
Description: Thrift interface definition for {1}

""".format(self._prefix, self._env.project_name, ", ".join(depends)))

            # lib*-dev package (c++)
            if 'cpp' in self._languages:
                open(os.path.join('debian', '{0}lib{1}-dev.install'.format(self._prefix, self._env.project_name)), 'w').write('debian/tmp/usr/include/thrifts\ndebian/tmp/usr/lib/*.a\n')
                depends = ['${misc:Depends}']
                for dep in thrift_dependencies:
                    depends.append("{0}lib{1}-dev".format(self._prefix, dep))
                control.write("""Package: {0}lib{1}-dev
Architecture: any
Depends: {2}
Description: Static library and include files for {1}

""".format(self._prefix, self._env.project_name, ", ".join(depends)))

            # python-* packache (python)
            if 'py' in self._languages:
                open(os.path.join('debian', '{0}python-{1}.install'.format(self._prefix, self._env.project_name)), 'w').write('debian/tmp/usr/lib/python*\n')
                open(os.path.join('debian', '{0}{1}-bin.install'.format(self._prefix, self._env.project_name)), 'w').write('debian/tmp/usr/bin/*-remote\n')
                depends = ['${python:Depends}', '${misc:Depends}']
                for dep in thrift_dependencies:
                    depends.append("{0}python-{1}".format(self._prefix, dep))
                print(depends)
                control.write("""Package: {0}python-{1}
Architecture: all
Depends: {2}
Description: Python language bindings for {1}

""".format(self._prefix, self._env.project_name, ", ".join(depends)))
                # *-bin package - command line client - only build when python package is built, too
                if self.__build_bin_package:
                    control.write("""Package: {0}{1}-bin
Depends: ${{misc:Depends}}, {0}python-{1} (= ${{binary:Version}})
Architecture: all
Description: Command line remote tool for {1}

""".format(self._prefix, self._env.project_name))
            control.close()
            super(ThriftDebianPackaging, self).package()
        finally:
            if not self._debug:
                self._env.remove_trees('debian')

    @property
    def meta(self):
        name = self._env.project_name
        m = { 'source': self._prefix + name, 'package': [self._prefix + name] }
        pypkgs = ['{0}python-{1}']
        if self.__build_bin_package:
            pypkgs.append('{0}{1}-bin')
        for lang, pkgs in ('cpp', ['{0}lib{1}-dev']), ('py', pypkgs):
            if lang in self._languages:
                for pkg in pkgs:
                    m['package'].append(pkg.format(self._prefix, name))
        return m

class ThriftCompiler(object):
    def __init__(self, env, thrift_dir = 'thrifts'):
        self.__env = env
        self.__thrift_dir = os.path.realpath(thrift_dir)
        self.__include = [self.__thrift_dir]

    def include(self, *args):
        self.__include += args

    def run(self, generator, source, output_dir = None):
        cmd = ['thrift']
        for i in self.__include:
            cmd += ['-I', os.path.realpath(i)]
        cmd += ['-I', '/usr/share/thrifts']    # add default include path (fixes MIR-2587)
        if output_dir is not None:
            cmd += ['-o', os.path.realpath(output_dir)]
            if 'twisted' in generator:
                self.__env.execute_tool(['mkdir', '-p',  os.path.join(os.path.realpath(output_dir), 'gen-py')])
                cmd += ['--out', os.path.join(os.path.realpath(output_dir), 'gen-py')]
        self.__env.execute_tool(cmd + ['--gen', generator, os.path.relpath(source, self.__thrift_dir)], cwd = self.__thrift_dir)



class ThriftInterface(mirbuild.cmake.CMakeProject, mirbuild.python.PythonSetupMixin):
    default_dependency_class = ThriftDependency
    _re_namespace = re.compile(r'\s*namespace\s+(\w+)\s+([\w\.]+)')
    _re_import = re.compile(r'(\s*)import\s+(\w+)(\s*\n?)$')
    _re_from_import = re.compile(r'(\s*)from\s+(\w+)\s+import\s+(.*\n?)$')
    _re_include_dquotes = re.compile(r'(\s*#include\s+)"([^"]+)"(\s*\n?)$')
    _re_include_angle = re.compile(r'(\s*#include\s+)<([^>]+)>(\s*\n?)$')
    _cpp = None
    _py = None
    python_setup_file = os.path.join('build', 'setup.py')

    def __init__(self, name, **opts):
        if not name.startswith('thrift-'):
            raise RuntimeError('Names of ThriftInterface projects must start with "thrift-", this one does not ("{0}")'.format(name))
        self.__py_twisted = opts['py_twisted'] if 'py_twisted' in opts else False
        mirbuild.cmake.CMakeProject.__init__(self, name, **opts)
        mirbuild.python.PythonSetupMixin.__init__(self)
        self.__thriftspath = []
        self.__thriftfiles = []

        self._language2module2namespace = {}
        directories = [ 'thrifts' ]
        while directories:
            directory = directories.pop()
            filenames = os.listdir(directory)
            for filename in filenames:
                path = os.path.join(directory, filename)
                st = os.stat(path)
                if stat.S_ISDIR(st.st_mode):
                    directories.append(path)
                elif stat.S_ISREG(st.st_mode) and filename.endswith('.thrift'):
                    self.__thriftfiles.append(path)
                    for line in open(path):
                        res = self._re_namespace.match(line)
                        if res:
                            language, namespace = res.groups()
                            if language not in self._language2module2namespace:
                                self._language2module2namespace[language] = {}
                            self._language2module2namespace[language][path] = namespace

        if not self._language2module2namespace:
            raise RuntimeError('No thrift definition files found in directory thrifts.\n')

        if 'py' in self._language2module2namespace:
            # One or more Thrift files define a namespace for Python modules.
            # Therefore, Python packages will be built.
            # Check if the namespaces given for the Python modules are
            # unique, as otherwise the Python packages will be broken.
            # (The Thrift compiler writes some files with fixed names into
            # the directory defined by the namespace. If more than one
            # Thrift file give the same Python namespace, files created
            # by one run of the Thrift interpreter will be overwritten by
            # later runs.)
            python_namespaces = list(self._language2module2namespace['py'].values())
            if len(python_namespaces) != len(set(python_namespaces)):
                # Assigned namespaces are not unique!
                # This breaks Python packages. Fatal error -> go fix your Thrift files!
                raise RuntimeError('FATAL: Different thrift definition files use the same Python namespace.\n')

        self.__packageobj = ThriftDebianPackaging(self.env, self._deps,
                                                  set(self._language2module2namespace),
                                                  build_bin_package = self.options.get('has_service', True),
                                                  debug = self.opt.debug)
        self.package(self.__packageobj)

    def add_thrifts_path(self, *args):
        self.__thriftspath += args

    def do_configure(self):
        self.__do_configure_cpp()
        self.__do_configure_py()

    def do_realclean(self):
        super(ThriftInterface, self).do_realclean()
        self.env.remove_trees('bin', 'build', 'include', 'lib', 'python', 'src', 'debian')
        self.env.remove_files(self.python_setup_file, 'CMakeLists.txt')

    def __do_configure(self):
        self.env.make_dirs('build')

    def __do_configure_cpp(self):
        if not self._cpp:
            self.__do_configure()
            self._cpp = self._language2module2namespace.get('cpp')
            if self._cpp:
                thrift = ThriftCompiler(self.env)
                thrift.include(os.path.join(self.opt.prefix, 'share', 'thrifts'), *self.__thriftspath)

                # Prepare build: create directories
                self.env.make_dirs('src', 'lib')
                static_lib_src = []

                for i in self._cpp:
                    # Run Thrift compiler on all Thrift interface definitions
                    try:
                        thrift.run(generator = 'cpp:include_prefix', output_dir = 'build', source = i)
                    except RuntimeError:
                        self.env.warn('Failed to generate thrift bindings - did you set all the dependencies?')
                        raise

                    # Correct include statements
                    gen_cpp_files = set(os.listdir(os.path.join('build', 'gen-cpp')))
                    for filename in gen_cpp_files:
                        path = os.path.join('build', 'gen-cpp', filename)
                        out = []
                        for line in open(path):
                            res = self._re_include_dquotes.match(line)
                            if res:
                                includefile = res.group(2)
                                inc_dir, inc_file = os.path.split(includefile)
                                if os.path.basename(inc_dir) == 'gen-cpp':
                                    includefile = os.path.join(os.path.dirname(inc_dir), inc_file)
                                line = "{0}<thrifts/{1}>{2}".format(res.group(1), includefile, res.group(3))
                            else:
                                res = self._re_include_angle.match(line)
                                if res and res.group(1) in _thrift_include_files:
                                    line = "{0}<thrift/{1}>{2}".format(*res.groups())
                                    self.env.warn('Corrected include statements in {0}'.format(path))
                            out.append(line)
                        open(path, 'w').write("".join(out))

                    # Move include files over
                    includefile_destination = os.path.join('include', os.path.dirname(i))
                    self.env.make_dirs(includefile_destination)
                    for j in glob.glob(os.path.join('build', 'gen-cpp', '*.h')):
                        dest = os.path.join(includefile_destination, os.path.basename(j))
                        self.env.move(j, dest)

                    # Move C++ source files over
                    cppfile_destination = os.path.join('src', os.path.dirname(os.path.relpath(i, 'thrifts')))
                    self.env.make_dirs(cppfile_destination)
                    for j in glob.glob(os.path.join('build', 'gen-cpp', '*.cpp')):
                        if not j.endswith('.skeleton.cpp'):
                            cppfile = os.path.join(cppfile_destination, os.path.basename(j))
                            self.env.move(j, cppfile)
                            static_lib_src.append(cppfile)

                self.__write_cmake(static_lib_src)
                super(ThriftInterface, self).do_configure()

        return self._cpp

    def __do_configure_py(self):
        if not self._py:
            self.__do_configure()
            self._py = self._language2module2namespace.get('py')
            if self._py:
                thrift = ThriftCompiler(self.env)
                thrift.include(os.path.join(self.opt.prefix, 'share', 'thrifts'), *self.__thriftspath)
                twisted_ext = ',twisted' if self.__py_twisted else ''
                for i in self._py:
                    thrift.run(generator = 'py:new_style=1' + twisted_ext, output_dir = 'build', source = i)

        return self._py

    def __write_cmake(self, static_lib_src):
        target = self.project_name.replace('-', '_')
        source = '\n   '.join(static_lib_src)

        cmake = '''
PROJECT({PROJECT})

CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

INCLUDE(config.cmake)

INCLUDE_DIRECTORIES(include)

ADD_LIBRARY({TARGET} STATIC
   {SOURCE}
)

###
# This is to work around the following issue
# https://issues.apache.org/jira/browse/THRIFT-1326
ADD_DEFINITIONS_POSIX(-DHAVE_INTTYPES_H -DHAVE_NETINET_IN_H)
###

INSTALL(TARGETS {TARGET} ARCHIVE DESTINATION lib)

INSTALL(DIRECTORY include DESTINATION include)
'''.format(PROJECT = self.project_name, TARGET = target, SOURCE = source)

        open('CMakeLists.txt', 'w').write(cmake)

    def do_build(self):
        if self.__do_configure_cpp():
            super(ThriftInterface, self).do_build()

        py = self.__do_configure_py()
        if py:
            # Prepare build: create directories
            self.env.make_dirs('bin')

            python_modules = list(py.itervalues())
            python_namespaces = mirbuild.python.PythonHelpers.modules2namespaces(python_modules)

            thrift_dependency_group = self._deps.get_dependency_group(ThriftDependencyGroup)
            thrift_dependencies = thrift_dependency_group.names if thrift_dependency_group else []
            python_thrift_dependency_group = self._deps.get_dependency_group(PyThriftDependencyGroup)
            thrift_dependencies.extend(python_thrift_dependency_group.names if python_thrift_dependency_group else [])
            thrift_dependencies = thrift_dependencies if thrift_dependencies else ()

            # Python setup
            open(self.python_setup_file, 'w').write(
                "from setuptools import setup\nsetup(**{0!r})\n".format(dict(
                    name = self.package_prefix + self.project_name,
                    version = self._vinfo.upstream_version(),
                    description = 'Python language bindings for ' + self.project_name,
                    package_dir = {'': 'gen-py'},
                    packages = python_namespaces + python_modules,
                    namespace_packages = python_namespaces,
                    maintainer = self._vinfo.author_name(),
                    maintainer_email = self._vinfo.author_email(),
                    install_requires = ['Thrift'] + list(
                        self.package_prefix+i for i in thrift_dependencies),
                )))

            # Write __init__.py files into Python namespace folders to enable
            # correct sharing of these namespaces with other packages
            for ns in python_namespaces:
                open(os.path.join('build', 'gen-py', *(ns.split('.') + ['__init__.py'])), 'w').write(
                    mirbuild.python.PythonHelpers.namespace_package_declaration
                    )

            self._exec_python_setup('build')

            # Copy and patch the *-remote scripts
            directories = [ (os.path.join('build', 'gen-py'), '') ]
            while directories:
                directory, prefix = directories.pop()
                pymodules = set()
                scriptfiles = []
                for filename in os.listdir(directory):
                    path = os.path.join(directory, filename)
                    st = os.stat(path)
                    if (stat.S_ISDIR(st.st_mode)):
                        directories.append((path, '{0}{1}.'.format(prefix, filename)))
                    elif (stat.S_ISREG(st.st_mode)):
                        if filename.endswith('.py'):
                            pymodules.add(filename[:-3])
                        elif filename.endswith('-remote'):
                            scriptfiles.append((path, prefix))
                for infilename, prefix in scriptfiles:
                    outfilename = os.path.join('bin', os.path.basename(infilename))
                    infile = open(infilename)
                    outfile = open(outfilename, 'w')
                    os.chmod(outfilename, 0755)
                    for line in infile:
                        res = self._re_import.match(line)
                        if res and res.group(2) in pymodules:
                            line = '{0}import {1}{2} as {2}{3}'.format(res.group(1), prefix, res.group(2), res.group(3))
                        else:
                            res = self._re_from_import.match(line)
                            if res and res.group(2) in pymodules:
                                line = '{0}from {1}{2} import {3}'.format(res.group(1), prefix, res.group(2), res.group(3))
                        outfile.write(line)

    def do_install(self):
        prefix = (self.opt.install_destdir or "") + self.opt.prefix

        # Install Thrift definition files in /usr/share/thrifts
        for i in self.__thriftfiles:
            destination = os.path.join(prefix, "share", i)
            self.env.make_dirs(os.path.dirname(destination))
            shutil.copy2(i, destination)

        if self._language2module2namespace.get('cpp'):
            # Install header files in include/thrifts
            include_thrifts = os.path.join(prefix, "include", "thrifts")
            for dirpath, dirnames, filenames in os.walk(os.path.join('include', 'thrifts')):
                headerfiles = list(i for i in filenames if i.endswith('.h'))
                if headerfiles:
                    self.env.make_dirs(os.path.join(prefix, dirpath))
                    for filename in headerfiles:
                        shutil.copy2(os.path.join(dirpath, filename), os.path.join(prefix, dirpath, filename))

            # Install static library in lib
            lib = os.path.join(prefix, "lib")
            self.env.make_dirs(lib)
            for i in glob.glob(os.path.join('lib', '*.a')):
                shutil.copy2(i, lib)

        if self._language2module2namespace.get('py'):
            args = ['install', '--prefix=' + self.opt.prefix, '--no-compile']
            if self.opt.install_destdir:
                args += ['--root=' + self.opt.install_destdir]
            # XXX: workaround for old versions of python-setuptools
            # (before 0.6c9-0ubuntu4) that don't support --install-layout.
            # (This is the case on lenny.)
            try:
                self._exec_python_setup(*(args + ['--install-layout=deb']))
            except Exception:
                self._exec_python_setup(*args)

            # Install *-remote files in bin
            bin = os.path.join(prefix, "bin")
            self.env.make_dirs(bin)
            for i in glob.glob(os.path.join('bin', '*-remote')):
                shutil.copy2(i, bin)
