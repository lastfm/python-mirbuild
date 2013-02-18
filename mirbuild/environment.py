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
Class representing the current environment of a mirbuild project

The environment can be used to emit diagnostic messages, execute commands
and random other stuff.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'

import filecmp, os, re, sys, subprocess, shutil, errno

try:
    import ConfigParser as configparser
except ImportError:
    # called configparser in python3
    import configparser

_no_default_given = object()

class Environment(object):
    def __init__(self, project_name):
        self.__project_name = project_name
        self.__cfg = configparser.ConfigParser()
        self.__cached_num_processors = None
        self.__opt = None
        self.__global_mirbuildrc = '/etc/mirbuildrc'

    def set_options(self, opt):
        self.__opt = opt

    @property
    def _options(self):
        return self.__opt

    @property
    def project_name(self):
        return self.__project_name

    @property
    def debug(self):
        return self.__opt is not None and self.__opt.debug

    @property
    def trace(self):
        return self.__opt is not None and self.__opt.trace

    @property
    def quiet(self):
        return self.__opt is not None and self.__opt.quiet

    @property
    def verbose(self):
        return self.__opt is not None and self.__opt.verbose

    @property
    def build_config(self):
        return self.__opt is not None and self.__opt.configuration

    @property
    def build_mode(self):
        return self.__opt.build_mode

    @property
    def out_of_source(self):
        return self.build_mode == 'out'

    @property
    def oosbuild_dir(self):
        # always return what our out-of-source path would be (even if we're not actually oos)!
        return os.path.join('build', sys.platform, self.build_config)

    @property
    def build_dir(self):
        # we may or may not be building out-of-source, so just return cwd if we're not
        return self.oosbuild_dir if self.out_of_source else '.'

    @property
    def oosbin_dir(self):
        return os.path.join(self.oosbuild_dir, 'bin')

    @property
    def bin_dir(self):
        return self.oosbin_dir if self.out_of_source else os.path.join(self.build_dir, 'bin')

    def warn(self, *args):
        sys.stderr.write('*** WARNING: ' + ''.join(args) + '\n')
        sys.stderr.flush()

    def say(self, *args):
        if not self.quiet:
            sys.stdout.write(''.join(args) + '\n')
            sys.stdout.flush()

    def vsay(self, *args):
        if self.verbose or self.debug:
            sys.stdout.write(''.join(args) + '\n')
            sys.stdout.flush()

    def dbg(self, *args):
        if self.debug:
            sys.stdout.write('[dbg] ' + ''.join(args) + '\n')
            sys.stdout.flush()

    def has_section(self, section):
        return self.__cfg.has_section(section)

    def get_section(self, section):
        sec = {}
        for k, v in self.__cfg.items(section):
            sec[k] = v
        return sec

    def has(self, section, option):
        return self.__cfg.has_option(section, option)

    def __get(self, name, section, option, default):
        method = getattr(self.__cfg, name)
        if default is _no_default_given:
            return method(section, option)
        else:
            try:
                return method(section, option)
            except configparser.Error:
                return default

    def get(self, section, option, default = _no_default_given):
        return self.__get('get', section, option, default)

    def getint(self, section, option, default = _no_default_given):
        return self.__get('getint', section, option, default)

    def getfloat(self, section, option, default = _no_default_given):
        return self.__get('getfloat', section, option, default)

    def getboolean(self, section, option, default = _no_default_given):
        return self.__get('getboolean', section, option, default)

    def read_config(self):
        files = []

        dir = self.getcwd()
        while dir:
            path = os.path.join(dir, '.mirbuildrc')
            if os.path.exists(path):
                files.append(path)
            (dir, ignore) = os.path.split(dir)
            if not ignore:
                break

        if os.path.exists(self.__global_mirbuildrc):
            files.append(self.__global_mirbuildrc)

        if files:
            files.reverse()
            self.__cfg.read(files)

    def getcwd(self):
        return os.getcwd()

    def execute(self, cmd, *args, **options):
        if not args and (isinstance(cmd, list) or isinstance(cmd, tuple)):
            args = tuple(cmd[1:])
            cmd = cmd[0]
        self.dbg("child process [in {0}]: {1} {2}".format(os.path.realpath(options.get('cwd', self.getcwd())), cmd, ' '.join(args)))
        r = -1
        try:
            r = subprocess.call([cmd] + list(args), **options)
        except OSError as ex:
            if ex.errno == errno.ENOENT:
                raise RuntimeError('Command "{0}" not found.'.format(cmd))
            else:
                raise
        if r != 0:
            raise RuntimeError('{0} failed ({1}).'.format(cmd, r))

    def execute_tool(self, name, *args, **options):
        if not args and (isinstance(name, list) or isinstance(name, tuple)):
            args = tuple(name[1:])
            name = name[0]
        return self.execute(self.tool(name), *args, **options)

    def remove_trees(self, *args):
        for tree in args:
            self.dbg("removing tree: ", tree)
            shutil.rmtree(tree, True)

    def remove_files(self, *args):
        for file in args:
            try:
                self.dbg("removing file: ", file)
                os.remove(file)
            except OSError as ex:
                if ex.errno != errno.ENOENT:
                    raise

    def remove_dirs(self, *args):
        for dir in args:
            try:
                self.dbg("removing directory: ", dir)
                os.rmdir(dir)
            except OSError as ex:
                if ex.errno not in (errno.ENOENT, errno.ENOTEMPTY):
                    raise

    def make_dirs(self, *args):
        for dir in args:
            try:
                os.makedirs(dir)
                continue
            except OSError as ex:
                # OSError 'File exists' usually means that the directory already exists
                # and can be ignored.
                if ex.errno != errno.EEXIST:
                    raise
            if not os.path.isdir(dir):
                # 'File exists' can also mean that a regular file exists where the directory
                # should be created. The exception was ignored. So we check here explicitly
                # whether dir exists and is a directory. If it's not, we raise.
                raise RuntimeError('Directory "{0}" could not be created.'.format(dir))

    def move(self, src, dst, if_different = True):
        # The move/rename will happen if:
        #  - the destination doesn't exist OR
        #  - if_different is False OR
        #  - the source and destination files are different (filecmp returns True if they're equal)
        # I.e. it will not happen if:
        #  - the destination exists AND
        #  - if_different is True AND
        #  - the files have the same content
        if not (os.path.exists(dst) and if_different and filecmp.cmp(src, dst)):
            if os.path.exists(dst):
                self.remove_files(dst)
            self.dbg("moving {0} to {1}".format(src, dst))
            os.rename(src, dst)

    def can_make(self):
        return os.path.exists('SConstruct') or os.path.exists('Makefile') or os.path.exists('CMakeCache.txt') or os.path.exists('CMakeFiles')

    def make(self, *args, **options):
        self.execute(self.tool('make'), *args, **options)

    def tool(self, name):
        return self.get('tools', name, name)

    def has_tool(self, name):
        return self.__cfg.has_option('tools', name)

    @property
    def __num_processors(self):
        if self.__cached_num_processors is None:
            try:
                self.__cached_num_processors = 0
                fh = open('/proc/cpuinfo', 'r')
                for line in fh:
                    if re.match('processor\s*:\s*\d+', line):
                        self.__cached_num_processors += 1
            except Exception:
                self.__cached_num_processors = 1
        return self.__cached_num_processors

    @property
    def parallel_builds(self):
        num = self.__opt.jobs
        if num == 'auto':
            return self.__num_processors
        try:
            return max(1, int(num))
        except ValueError:
            raise RuntimeError('Invalid value for number of parallel jobs ("{0}")'.format(num))
