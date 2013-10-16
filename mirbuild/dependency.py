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
Dependency modeling classes

The classes in this file describe dependencies to other software projects.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'

import operator
import os
import re
import sys
import mirbuild.cache
import mirbuild.walk
from mirbuild.options import LocalOptions
from optparse import OptionGroup


class Dependency(object):
    def __init__(self, name):
        self.__name = name

    def set_cache(self, cache):
        pass

    @property
    def name(self):
        return self.__name

    @property
    def meta(self):
        return self.__name

    @property
    def has_options(self):
        return False

    @property
    def is_satisfied(self):
        return True

class DependencyGroup(object):
    group_name = 'Other'
    managed_classes = [Dependency]

    def __init__(self, env):
        self._env = env
        self.__deps = []

    @classmethod
    def can_manage(cls, obj):
        return any(isinstance(obj, dependency_class) for dependency_class in cls.managed_classes)

    def add(self, dep):
        assert self.can_manage(dep)
        self.__deps.append(dep)

    def any_is_a(self, cls):
        return any(isinstance(dep, cls) for dep in self.__deps)

    def set_cache(self, cache):
        for dep in self.__deps:
            dep.set_cache(cache)

    def add_options(self, parser, nomerge):
        if self.any_has_options:
            og = OptionGroup(parser, self.group_name + " Dependency Options")

            for dep in self.__deps:
                if not nomerge and self._env.has('dependencies', dep.name):
                    dep.state_merge(self._env.get('dependencies', dep.name))
                dep.add_options(og)

            self.add_group_options(og, nomerge)

            parser.add_option_group(og)

    @property
    def has_unsatisfied_dependencies(self):
        return any(not dep.is_satisfied for dep in self.__deps) if self.__deps else False

    def set_unsatisfied_dependencies(self, paths):
        for dep in self.__deps:
            if not dep.is_satisfied:
                if dep.name in paths:
                    dep.state_merge(paths[dep.name])
                else:
                    self._env.warn('Could not satisfy dependency for ' + dep.name)

    def add_group_options(self, parser, nomerge):
        pass

    def apply(self, obj):
        for dep in self.__deps:
            dep.apply(obj)

    @property
    def any_has_options(self):
        for dep in self.__deps:
            if dep.has_options:
                return True
        return False

    @property
    def names(self):
        return list(d.name for d in self.__deps)

    @property
    def meta(self):
        return [d.meta for d in self.__deps]

class CLibraryDependency(Dependency):
    def __init__(self, name):
        Dependency.__init__(self, name)
        self.__opt = LocalOptions(name)

    @staticmethod
    def isdir(basepath, env = None, *path):
        if basepath is not None:
            result = os.path.realpath(os.path.join(os.path.expanduser(basepath), *path))
            return os.path.isdir(result)
        else:
            raise ValueError

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
        return CLibraryDependency.validated_path(self._path, env, *path)

    def _isdir(self, env = None, *path):
        return CLibraryDependency.isdir(self._path, env, *path)

    def set_cache(self, cache):
        cache.register(self.__opt)

    def add_options(self, parser):
        self.__opt.add_option(parser, '--with-{0}'.format(self.name), type = 'string', dest = 'path', metavar = 'PATH',
                              help = 'use {0} includes/libraries from this path'.format(self.name))

    def apply(self, obj):
        if self._path:
            # Adding includes is simple, in or out of source makes no difference
            ipath = self._validated_path(obj.env, 'include')
            obj.add_include_path(ipath)
            obj.env.dbg('Added inc-path: {0}'.format(ipath))

            # Adding library paths is a little more complex since the dependencies could
            # have been build either in-source or out-of-source and we don't really know.
            # We'll use a little bit of educated guess work try try and figure it out!

            # This is the in-source library path
            path = 'lib'
            path_exists = self._isdir(obj.env, path)

            # This is the out-of-source library path
            oospath = os.path.join(obj.env.oosbuild_dir, path)
            oospath_exists = self._isdir(obj.env, oospath)

            # Ok, we now need to try and find the most suitable library path:
            # - If the most suitable library path exists use it
            # - If it doesn't exist but there's an alternative use that
            # - If neither exist fallback on the most suitable (warning it's not there)
            if obj.env.out_of_source:
                if oospath_exists or not path_exists:
                    path = oospath
            else:
                if not path_exists and oospath_exists:
                    path = oospath

            vpath = self._validated_path(obj.env, path)

            # Add the verified path we decided to use (with a little bit of debug for good measure)
            obj.add_library_path(vpath)
            obj.env.dbg('Added lib-path: {0}'.format(vpath))

    @property
    def _path(self):
        return getattr(self.__opt, 'path', None)

    def state_merge(self, value):
        self.__opt.state_merge({ "path": value })

    @property
    def has_options(self):
        return True

    @property
    def is_satisfied(self):
        return self._path is not None

class CLibraryDependencyGroup(DependencyGroup):
    group_name = 'C Library'
    managed_classes = [CLibraryDependency]


class PythonDependency(Dependency):
    def __init__(self, name):
        Dependency.__init__(self, name)
        self.__opt = LocalOptions(name)

    @staticmethod
    def isdir(basepath, env = None, *path):
        if basepath is not None:
            result = os.path.realpath(os.path.join(os.path.expanduser(basepath), *path))
            return os.path.isdir(result)
        else:
            raise ValueError

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
        return PythonDependency.validated_path(self._path, env, *path)

    def _isdir(self, env = None, *path):
        return PythonDependency.isdir(self._path, env, *path)

    def set_cache(self, cache):
        cache.register(self.__opt)

    def add_options(self, parser):
        self.__opt.add_option(parser, '--with-{0}'.format(self.name), type = 'string', dest = 'path', metavar = 'PATH',
                              help = 'use {0} includes/libraries from this path'.format(self.name))

    def apply(self, obj):
        return
        if self._path:
            # Adding includes is simple, in or out of source makes no difference
            ipath = self._validated_path(obj.env)
            obj.add_include_path(ipath)
            obj.env.dbg('Added inc-path: {0}'.format(ipath))

            # Adding library paths is a little more complex since the dependencies could
            # have been build either in-source or out-of-source and we don't really know.
            # We'll use a little bit of educated guess work try try and figure it out!

            # This is the in-source library path
            path = 'lib'
            path_exists = self._isdir(obj.env, path)

            # This is the out-of-source library path
            oospath = os.path.join(obj.env.oosbuild_dir, path)
            oospath_exists = self._isdir(obj.env, oospath)

            # Ok, we now need to try and find the most suitable library path:
            # - If the most suitable library path exists use it
            # - If it doesn't exist but there's an alternative use that
            # - If neither exist fallback on the most suitable (warning it's not there)
            if obj.env.out_of_source:
                if oospath_exists or not path_exists:
                    path = oospath
            else:
                if not path_exists and oospath_exists:
                    path = oospath

            vpath = self._validated_path(obj.env, path)

            # Add the verified path we decided to use (with a little bit of debug for good measure)
            obj.add_library_path(vpath)
            obj.env.dbg('Added lib-path: {0}'.format(vpath))

    @property
    def _path(self):
        return getattr(self.__opt, 'path', None)

    def state_merge(self, value):
        self.__opt.state_merge({ "path": value })

    @property
    def has_options(self):
        return True

    @property
    def is_satisfied(self):
        return self._path is not None


class PythonDependencyGroup(DependencyGroup):
    group_name = 'Python Dependency'
    managed_classes = [PythonDependency]


class Dependencies(object):
    __dependency_group_classes = set([DependencyGroup])

    def __init__(self, env, default_dependency_class):
        self.__env = env
        self.__default = default_dependency_class
        self.__groups = {}
        self.__opt = LocalOptions()

    @classmethod
    def register_group_class(cls, dependency_group_class):
        cls.__dependency_group_classes.add(dependency_group_class)

    def add(self, *args):
        for arg in args:
            if isinstance(arg, basestring):
                arg = self.__default(arg)
            assert isinstance(arg, Dependency)
            group = None
            for cls in self.__group_classes():
                if cls.can_manage(arg):
                    if cls not in self.__groups:
                        self.__groups[cls] = cls(self.__env)
                    group = self.__groups[cls]
                    break
            if group is not None:
                group.add(arg)
            else:
                raise RuntimeError('No class found that can manage ' + arg.__class__.__name__)


    def any_is_a(self, cls):
        return any(grp.any_is_a(cls) for grp in self.__groups.itervalues())

    def __group_classes(self):
        src = []
        for group in self.__dependency_group_classes:
            for managed in group.managed_classes:
                src.append((managed, group))
        dst = []
        while src:
            cls = src.pop(0)
            if any(issubclass(x[0], cls[0]) for x in src):
                src.append(cls)
            elif cls[1] not in dst:
                dst.append(cls[1])
        return dst

    def set_cache(self, cache):
        for grp in self.__groups.itervalues():
            try:
                grp.set_cache(cache)
            except Exception as ex:
                sys.stderr.write(str(ex) + '\n')

    def add_options(self, parser, nomerge = False):
        if self.__groups:
            if not nomerge and self.__env.has('dependencies', 'search_path'):
                self.__opt.state_merge({ 'deps_from': self.__env.get('dependencies', 'search_path') })
            og = OptionGroup(parser, "General Dependency Options")
            self.__opt.add_option(og, '--with-deps-from', type = 'string', dest = 'deps_from', metavar = 'PATH',
                                  help = 'scan this path for dependencies')
            parser.add_option_group(og)
            for cls in sorted(self.__groups, key=operator.attrgetter('__name__')):
                self.__groups[cls].add_options(parser, nomerge)

    def __autoresolve(self):
        if any(group.has_unsatisfied_dependencies for group in self.__groups.itervalues()):
            self.__env.say('Resolving dependencies...')
            path = self.__opt.deps_from
            fast = True
            if path.startswith('slow:'):
                path = path[5:]
                fast = False
            found = mirbuild.walk.Walker(path, fastscan = fast, env = self.__env).dependencies
            for group in self.__groups.itervalues():
                group.set_unsatisfied_dependencies(found)

    def apply(self, obj):
        if self.__groups and self.__opt.deps_from:
            self.__autoresolve()
        for grp in self.__groups.itervalues():
            grp.apply(obj)

    def get_dependency_group(self, cls):
        return self.__groups.get(cls)

    @property
    def meta(self):
        m = []
        for grp in self.__groups.itervalues():
            m += grp.meta
        return m

Dependencies.register_group_class(CLibraryDependencyGroup)
Dependencies.register_group_class(PythonDependencyGroup)
