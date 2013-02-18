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
Project class for Playground and Playground apps

"""

__author__ = 'Sven Over <sven@last.fm>'
__all__ = 'PlaygroundProject'.split()

import collections
import os
import glob
import re
import sys

import mirbuild.python

from mirbuild.tools import ScopedFile

def _recursive_listdir(path, root=None):
    if root is None:
        root = path

    def walker(l, dirname, names):
        prefix = os.path.relpath(dirname, root)
        for n in names:
            if os.path.isfile(os.path.join(dirname, n)):
                l.append(os.path.join(prefix, n))

    files = []
    os.path.walk(path, walker, files)
    return files

def _walker(root, dirname, names):
    path = os.path.relpath(dirname, root)


class PlaygroundProject(mirbuild.python.PythonProject):
    data_directories = ('static', 'templates')

    def __init__(self, name, modules, **opts):
        modules = list(modules)
        user_provided_setup_opts = opts.pop('setup', {})

        # Identify namespaces
        namespaces = mirbuild.python.PythonHelpers.modules2namespaces(modules)

        setup_opts = dict(
                packages = namespaces + modules,
                namespace_packages = namespaces,
            )

        # Data files
        self.__package_data_folders = collections.defaultdict(list)
        if 'package_data' not in user_provided_setup_opts:
            package_data = {}
            for m in modules:
                mpath = os.path.join(*m.split('.'))
                data_files = []
                for d in self.data_directories:
                    dd = os.path.join(mpath, d)
                    if os.path.isdir(dd):
                        files = _recursive_listdir(dd, mpath)
                        if files:
                            self.__package_data_folders[m].append(d)
                            data_files += files
                package_data[m] = data_files
            setup_opts['package_data'] = package_data

        setup_opts.update(user_provided_setup_opts)

        # Entry points for automatic detection of playground apps
        entry_points = setup_opts.get('entry_points', None) or {}
        if isinstance(entry_points, dict) and 'lfm.playground.apps' not in entry_points:
            apps = list('{0}={1}'.format(i[20:], i) for i in modules if i.startswith('lfm.playground.apps.'))
            if apps:
                entry_points['lfm.playground.apps'] = apps
        setup_opts['entry_points'] = entry_points

        opts['setup'] = setup_opts
        mirbuild.python.PythonProject.__init__(self, name, **opts)

        if self.opt.called_by_packager:
            # PythonProject.do_package will create the setup.py file.
            # For packaging, we have a different strategy for dealing with
            # those data files (templates and static files)
            package_data = self.setup_info.pop('package_data', {})
            data_files = collections.defaultdict(list)
            for module, files in package_data.iteritems():
                mpath = os.path.join(*module.split('.'))
                for f in files:
                    f = os.path.join(mpath, f)
                    data_files[os.path.join('share', os.path.dirname(f))].append(f)
            self.setup_info['data_files'] = list(data_files.items())

    def do_package(self):
        x = []
        for module, datadirs in self.__package_data_folders.items():
            mpath = os.path.join(*module.split('.'))
            pyfilename = os.path.join(mpath, '_data.py')
            locations = dict((d, '/usr/share/{0}/{1}'.format(mpath, d)) for d in datadirs)
            contents = 'locations = {0!r}\n'.format(locations)
            x.append(ScopedFile(pyfilename, contents))
        mirbuild.python.PythonProject.do_package(self)
