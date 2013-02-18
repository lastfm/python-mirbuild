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
The main project class

This is where it all comes together.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'Project'.split()

import errno, os, sys, glob, re, json, shutil
import mirbuild.dependency, mirbuild.test, mirbuild.environment
import mirbuild.version, mirbuild.packaging, mirbuild.cache
import mirbuild.plugin
from optparse import OptionParser, OptionGroup
from mirbuild.options import LocalOptions

# TODO: - profiling

def rootrelpath(path):
    # returns the path relative to '/'
    # this should rather have been:
    #   return os.path.relpath(path, '/')
    return path.lstrip('/')    # work around http://bugs.python.org/issue5117

class InstallRule(object):
    pass

class Project(object):
    environment_class = mirbuild.environment.Environment
    test_runner_class = mirbuild.test.BoostTestRunner
    default_dependency_class = None
    nocache_commands = set('meta'.split())
    noapply_commands = set('meta clean realclean distclean'.split())

    def __init__(self, name, **opts):
        self.__configurecache = mirbuild.cache.Cache(filename = 'configure.json')
        self.__options = opts
        self.__tests = None
        self.__versions = []
        self.__plugins = []
        self.__install = []
        self.__packagers = {}
        self.__test_runners = {}

        try:
            self.__configurecache.load()
        except Exception:
            # if we can't load the cache, so be it
            pass

        self.__parser = OptionParser(add_help_option = False)
        self.__general_options = OptionGroup(self.__parser, "General Options")
        self.__parser.add_option_group(self.__general_options)

        self.opt = LocalOptions('general')
        self.__configurecache.register(self.opt)

        if self.has_build_configs:
            self.add_option('-c|--configuration', dest = 'configuration', type = 'string', defaultstr = False,
                            metavar = 'CFG', help = 'selected build configuration')

        self.add_bool_option('-h|--help', dest = 'help', help = 'show this help message and exit', cache = False)

        for opt, dest, help in [('-d|--debug', 'debug', 'debug build.py execution'),
                                ('-q|--quiet', 'quiet', 'be quiet'),
                                ('-v|--verbose', 'verbose', 'verbose compiler/packaging output'),
                                ('--trace', 'trace', 'trace build process (if supported by the builder)'),
                                ('--nodeps', 'nodeps', "don't use dependencies from .mirbuildrc"),
                                ('--noconfig', 'noconfig', "don't use .mirbuildrc files at all"),
                                ('--noenv', 'noenv', "don't honour environment variables"),
                                ('--called-by-packager', 'called_by_packager', "option indicating that build.py is being invoked by a mirbuild packager"),
                                ]:
            self.add_bool_option(opt, dest = dest, help = help, cache = False)
            for o in opt.split('|'):
                if o in sys.argv:
                    self.opt.set_value(dest, True)

        self.__env = self.environment_class(name)
        self.__env.set_options(self.opt)
        self._deps = mirbuild.dependency.Dependencies(self.__env, self.default_dependency_class)

        if not self.opt.noconfig:
            self.__env.read_config()
            if self.__env.has('build', 'prefix'):
                self.opt.state_merge({ 'prefix': self.__env.get('build', 'prefix') })

        self.opt.ensure_value('jobs', self.__env.get('build', 'parallel', 'auto'))
        self.add_option('-j|--jobs', dest = 'jobs', type = 'string', metavar = 'NUM', cache = False,
                        help = 'number of parallel jobs to execute if possible')

        self.add_option('--prefix', dest = 'prefix', type = 'string', default = self.default_install_path,
                        metavar = 'PATH', help = 'install prefix for this project')
        self.add_option('--install-destdir', dest = 'install_destdir', type = 'string',
                        metavar = 'PATH', help = 'install files to this path')

        self.add_option('-b|--build-mode', dest = 'build_mode', type = 'choice', choices = ['in', 'out'], default = 'in',
                        metavar = "MODE", help = '[in|out] source build mode')

        for o in [('-I|--include-path', 'include', 'C_INCLUDE_PATH CPLUS_INCLUDE_PATH'.split()),
                  ('-L|--library-path', 'library', 'LIBRARY_PATH'.split())]:
            var = o[1] + '_path'
            if hasattr(self, 'add_' + var):
                path = []
                if not self.opt.noenv:
                    for e in o[2]:
                        path += [x for x in os.environ.get(e, '').split(os.path.pathsep) if x]
                path += [x for x in self.env.get('build', var, '').split(os.path.pathsep) if x]
                self.opt.state_merge({ var: path })
                self.add_option(o[0], type = 'string', dest = var, multi = True,
                                metavar = 'PATH', help = 'use additional ' + o[1] + ' path')

    @property
    def _configure_cache(self):
        return self.__configurecache

    @property
    def _option_parser(self):
        return self.__parser

    @property
    def default_install_path(self):
        return '/usr/local'

    @property
    def ident(self):
        return self.__parser.get_prog_name()

    @property
    def options(self):
        return self.__options

    @property
    def env(self):
        return self.__env

    @property
    def commands(self):
        return self.methlist('run_(\w+)')

    @property
    def build_configurations(self):
        return self.methlist('configure_(\w+)')

    @property
    def tests(self):
        return self.__tests

    @property
    def packager(self):
        return self.__packagers[self.opt.packager]

    @property
    def project_name(self):
        return self.__env.project_name

    @property
    def build_config(self):
        return getattr(self.opt, 'configuration', None)

    @property
    def has_thrift_dependency(self):
        # We need to know if there's a thrift dependency as we'll need to
        # configure some additional things for Visual Studio if we do
        # [mhx] We could cache the result, but I'd rather not bother with that now...
        return self._deps.any_is_a(mirbuild.ThriftDependency)

    def prefixpath(self, path):
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(self.opt.prefix, path)

    def installpath(self, path, isdir = False, mkdir = False):
        destdir = path if isdir else os.path.split(path)[0]
        if os.path.isabs(destdir):
            if self.opt.install_destdir is not None:
                destdir = os.path.join(self.opt.install_destdir, rootrelpath(destdir))
            else:
                destdir = destdir
        else:
            if self.opt.install_destdir is not None:
                destdir = os.path.join(self.opt.install_destdir, rootrelpath(self.opt.prefix), destdir)
            else:
                destdir = os.path.join(self.opt.prefix, destdir)

        if mkdir:
            try:
                os.makedirs(destdir)
            except OSError as ex:
                if ex.errno != errno.EEXIST:
                    raise

        return destdir if isdir else os.path.join(destdir, os.path.split(path)[1])

    def __usage(self):
        usage = 'Usage: %prog [Options] <Command>'
        usage += '\n\nCommands: {0}'.format(', '.join(self.commands))
        if self.has_build_configs:
            usage += '\n\nBuild Configurations: {0}'.format(', '.join(map(lambda x: (x + ' [*]') \
                   if x == self.__default_build_config() else x, self.build_configurations)))
        return usage

    def __default_build_config(self):
        if not self.has_build_configs:
            return None
        if self.opt.configuration is not None:
            return self.opt.configuration
        try:
            return self.env.get('build', 'configuration')
        except Exception:
            pass
        if 'release' in self.build_configurations:
            return 'release'
        return self.build_configurations[0]

    def methlist(self, match):
        list = []
        run = re.compile(match)
        for method in dir(self):
            m = run.match(method)
            if m is not None and getattr(self, method) is not None:
                list.append(m.group(1))
        list.sort()
        return list

    def add_option(self, *args, **kw):
        self.opt.add_option(self.__general_options, *args, **kw)

    def add_bool_option(self, *args, **kw):
        self.opt.add_bool_option(self.__general_options, *args, **kw)

    def depends(self, *deps):
        self._deps.add(*deps)

    def test(self, *args, **kwargs):
        filt = kwargs.get('filter', lambda x: True)
        recurse = kwargs.get('recurse', True)
        runner_class = kwargs.get('runner', self.test_runner_class)
        test_builders = []
        if self.__tests is None:
            self.__tests = []

        for arg in args:
            if isinstance(arg, mirbuild.test.TestBuilder):
                test_builders.append(arg)
            elif isinstance(arg, basestring):
                dirs = []
                for e in glob.glob(arg):
                    if os.path.isdir(e):
                        if filt(e) and self.test_builder_class.looks_like_test_dir(e):
                            dirs.append(e)
                        if recurse:
                            for root, ds, fs in os.walk(e):
                                for d in ds:
                                    path = os.path.join(root, d)
                                    if filt(path) and self.test_builder_class.looks_like_test_dir(path):
                                        dirs.append(path)
                dirs.sort()
                for d in dirs:
                    test_builders.append(self.test_builder_class(self.env, d))
            else:
                test_builders.append(self.test_builder_class(self.env, *arg))

        if test_builders:
            if runner_class.name not in self.__test_runners:
                self.__test_runners[runner_class.name] = runner_class(self.env)
            runner = self.__test_runners[runner_class.name]

            for tb in test_builders:
                self.__tests.append(mirbuild.test.TestWrapper(builder = tb, runner = runner))

    def package(self, *args):
        for arg in args:
            assert isinstance(arg, mirbuild.packaging.Packaging)
            assert not self.__packagers.has_key(arg.name)
            self.__packagers[arg.name] = arg

    def install(self, source, destdir, glob = True):
        i = InstallRule()
        i.source = [source] if isinstance(source, basestring) else source
        i.destdir = destdir
        i.glob = glob
        self.__install.append(i)

    def __install_files(self):
        for i in self.__install:
            destdir = self.installpath(i.destdir, isdir = True, mkdir = True)

            source = []

            for src in i.source:
                if i.glob:
                    source += glob.glob(src)
                else:
                    source.append(src)

            for src in source:
                dst = os.path.join(destdir, os.path.split(src)[1])
                self.env.vsay('installing {0} -> {1}'.format(src, dst))
                if os.path.isdir(src):
                    shutil.copytree(src, dst, symlinks = True)
                else:
                    shutil.copy2(src, dst)

    def version(self, file = os.path.join('src', 'version.h'), info = None, **opts):
        if isinstance(file, basestring):
            file = mirbuild.version.VersionFileFactory.create(self.env, file, **opts)
        if info is None:
            info = mirbuild.version.VersionInfoFactory.create()
        assert isinstance(file, mirbuild.version.VersionFile)
        assert isinstance(info, mirbuild.version.VersionInfo)
        self.__versions.append({ 'file': file, 'info': info })

    def add_plugin(self, *args):
        for arg in args:
            assert isinstance(arg, mirbuild.plugin.Plugin)
            self.__plugins.append(arg)

    def _run_plugins(self, meth, reverse = False):
        for plugin in reversed(self.__plugins) if reverse else self.__plugins:
            self.env.dbg("running plugin method {0}.{1}".format(plugin.__class__.__name__, meth))
            getattr(plugin, meth)(self)

    @property
    def has_build_configs(self):
        return len(self.build_configurations) > 0

    def __expand_command(self, raw):
        if raw in self.commands:
            return raw
        cand = [cmd for cmd in self.commands if cmd.startswith(raw)]
        if len(cand) == 1:
            return cand[0]
        raise RuntimeError('{0} command "{1}".'.format('Invalid' if not cand else 'Ambiguous', raw))

    def run_has(self, what, arg):
        if what in ['command']:
            raise SystemExit(0 if arg in self.commands else 1)
        if what in ['config', 'configuration']:
            raise SystemExit(0 if arg in self.build_configurations else 1)
        raise SystemExit(2)

    def run(self):
        try:
            if self.__tests is None:
                self.test('test')

            if not self.__packagers:
                self.package(*mirbuild.packaging.PackagingFactory.create_all(self.env))

            dc = mirbuild.cache.Cache('dependencies')
            self._deps.set_cache(dc)
            self.__configurecache.register(dc)

            rc = mirbuild.cache.Cache('test_runners')
            for runner in self.__test_runners.itervalues():
                try:
                    runner.set_cache(rc)
                except Exception as ex:
                    sys.stderr.write(str(ex) + '\n')
            self.__configurecache.register(rc)

            self._deps.add_options(self.__parser, nomerge = self.opt.nodeps)

            for name, runner in self.__test_runners.iteritems():
                if self.env.has_section('test:' + name):
                    runner.state_merge(self.env.get_section('test:' + name))
                runner.add_options(self.__parser)

            if self.__packagers:
                self.add_option('--packager', dest = 'packager', type = 'choice',
                                choices = self.__packagers.keys(), defaultstr = len(self.__packagers) == 1,
                                default = self.__packagers.keys()[0] if len(self.__packagers) == 1 else None,
                                metavar = 'PKG', help = 'selected packager')
                for name, pkg in self.__packagers.iteritems():
                    sec = 'packaging:' + name
                    if self.env.has_section(sec):
                        pkg.state_merge(self.env.get_section(sec))
                    pkg.add_options(self.__parser)
                self.run_package = self.do_package

            self.__parser.set_usage(self.__usage())

            args = self.__parser.parse_args()[1]

            if self.has_build_configs:
                self.opt.ensure_value('configuration', self.__default_build_config())

            if self.opt.help or len(args) < 1:
                self.__parser.print_help()
                raise SystemExit(0)

            if self.has_build_configs and self.build_config not in self.build_configurations:
                raise RuntimeError('Invalid build configuration "{0}".'.format(self.build_config))

            command = self.__expand_command(args[0])
            command_method = getattr(self, 'run_' + command)

            if command not in self.noapply_commands:
                self.__apply_paths()
                self._deps.apply(self)

            if command not in self.nocache_commands:
                self.__configurecache.save()

            self.env.vsay('''******************************
   Config : {0}
   Action : {1}
******************************'''.format(self.build_config if self.has_build_configs else '(none)', command))

            command_method(*args[1:])

        except RuntimeError as ex:
            if self.opt.debug:
                raise
            sys.stderr.write('*** ERROR: ' + str(ex) + '\n')
            raise SystemExit(1)

        except KeyboardInterrupt:
            if self.opt.debug:
                raise
            sys.stderr.write('*** INTERRUPTED\n')
            raise SystemExit(1)

    def run_meta(self):
        meta = {
            'project': self.project_name,
            'commands': self.commands,
            'dependencies': self._deps.meta,
        }
        if self.__packagers:
            meta['packaging'] = {}
            for name, p in self.__packagers.iteritems():
                meta['packaging'][name] = p.meta
        try:
            info = mirbuild.version.VersionInfoFactory.create()
            meta['version'] = info.upstream_version()
        except RuntimeError:
            pass
        print json.dumps(meta, indent = 4)

    def run_build(self):
        self.run_configure()
        self._run_plugins('pre_build')
        self._run_plugins('build')
        self.do_build()
        self._run_plugins('post_build')

    def run_test(self):
        self.run_build()
        self._run_plugins('pre_test')
        self._run_plugins('test')
        self.do_test()
        self._run_plugins('post_test')

    def run_install(self):
        self.run_build()
        self._run_plugins('pre_install')
        self._run_plugins('install')
        self.do_install()
        self.__install_files()
        self._run_plugins('post_install')

    # TODO
    # def run_coverage(self):
    #     self.run_test()
    #     self.do_coverage()

    # this is just an alias
    def run_distclean(self):
        self.run_realclean()

    def run_realclean(self):
        for t in self.tests:
            t.clean()
        self._run_plugins('pre_realclean', reverse = True)
        self.do_realclean()
        self._run_plugins('realclean', reverse = True)
        self._run_plugins('post_realclean', reverse = True)
        self.env.remove_files(self.__configurecache.filename)
        self.env.remove_trees('build')
        for v in self.__versions:
            v['file'].clean()

    def run_clean(self):
        self._run_plugins('pre_clean', reverse = True)
        self.do_clean()
        self._run_plugins('clean', reverse = True)
        self._run_plugins('post_clean', reverse = True)
        for t in self.tests:
            t.clean()

    def __apply_paths(self):
        for opt in ['include_path', 'library_path']:
            meth = getattr(self, 'add_' + opt, None)
            if meth is not None:
                for path in getattr(self.opt, opt):
                    meth(mirbuild.dependency.CLibraryDependency.validated_path(path, env = self.env))

    def run_configure(self):
        for v in self.__versions:
            v['file'].generate(v['info'])
        self._run_plugins('pre_configure')
        self._run_plugins('configure')
        self.do_configure()
        self._run_plugins('post_configure')

    def do_test(self):
        for t in self.tests:
            t.configure()
            t.build()
        obs = mirbuild.test.TestObserver()
        for t in self.tests:
            t.run(obs)
        if obs.num_total > 0:
            self.env.say(obs.report())
            if obs.num_failed > 0:
                raise SystemExit(1)
        elif self.tests:
            raise RuntimeError('No test runs observed.')

    def do_package(self):
        self._run_plugins('pre_package')
        self.prepare_package()
        self._run_plugins('package')
        self.packager.package()
        self._run_plugins('post_package')

    def prepare_package(self):
        pass
