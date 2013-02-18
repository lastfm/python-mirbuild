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
Random collection of helper classes

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'

import os, filecmp, shutil, stat, errno

class ScopedChdir(object):
    def __init__(self, path):
        self.__saved_cwd = os.getcwd()
        if path is not None:
            os.chdir(path)

    def __del__(self):
        os.chdir(self.__saved_cwd)

    @property
    def original_dir(self):
        return self.__saved_cwd

class LazyFileWriter(object):
    def __init__(self, name, executable = False):
        self.__name = name
        self.__temp = name + '.new'
        self.__fh = None
        self.__executable = executable

    @property
    def exists(self):
        return os.path.exists(self.__name)

    def create(self):
        self.__fh = open(self.__temp, 'w')

    def write(self, *args):
        self.__fh.write(*args)

    def commit(self):
        self.__fh.close()
        self.__fh = None
        if self.exists and filecmp.cmp(self.__name, self.__temp):
            # files are identical, just remove our new version
            os.remove(self.__temp)
            return False
        if self.__executable:
            mode = os.stat(self.__temp).st_mode
            mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            os.chmod(self.__temp, mode)
        try:
            # try atomic rename first
            os.rename(self.__temp, self.__name)
        except OSError:
            old = self.__name + '.old'
            os.rename(self.__name, old)
            try:
                os.rename(self.__temp, self.__name)
            except OSError:
                os.rename(old, self.__name)
                raise
            os.remove(old)
        return True

    def __del__(self):
        if self.__fh is not None:
            # file hasn't been committed or commit went wrong
            self.__fh.close()
            try:
                os.remove(self.__temp)
            except OSError:
                pass

class ScopedFileCopy(object):
    def __init__(self, name, backup = None, create = True):
        self.__name = name
        self.__backup = self.__backup(name) if backup is None else backup
        self.__created = False
        if create:
            self.create()

    def __backup(self, name):
        (path, name) = os.path.split(name)
        return os.path.join(path, '_' + name + '.backup')

    def create(self):
        if not self.__created:
            os.rename(self.__name, self.__backup)
            shutil.copy(self.__backup, self.__name)
            self.__created = True

    def __del__(self):
        if self.__created:
            tmp = self.__name + '.old'
            os.rename(self.__name, tmp)
            os.rename(self.__backup, self.__name)
            os.remove(tmp)

class ScopedFileBase(object):
    def __init__(self, filename, keep = False):
        self._file = os.path.realpath(filename)
        self.__keep = keep
        self.__created_dirs = []
        self.__created = False

    def __del__(self):
        if self.__created:
            self.remove()

    @property
    def filename(self):
        return self._file

    def keep(self, keep = True):
        self.__keep = keep

    def __ensure_dir_rec(self, path):
        try:
            os.mkdir(path)
        except OSError as ex:
            if ex.errno == errno.EEXIST:
                return
            elif ex.errno == errno.ENOENT:
                self.__ensure_dir_rec(os.path.split(path)[0])
                os.mkdir(path)
            else:
                raise
        self.__created_dirs.append(path)

    def _ensure_dir(self):
        self.__ensure_dir_rec(os.path.split(self._file)[0])

    def _remove_created_dirs(self):
        while self.__created_dirs:
            os.rmdir(self.__created_dirs.pop())

    def _create(self, content):
        self._ensure_dir()
        fh = LazyFileWriter(self._file)
        fh.create()
        fh.write(content)
        fh.commit()
        self._set_created()

    def _set_created(self):
        self.__created = True

    def remove(self):
        if not self.__keep:
            try:
                os.remove(self._file)
                self._remove_created_dirs()
            except OSError:
                pass    # too bad :-(

class ScopedFile(ScopedFileBase):
    def __init__(self, name, content = None, path = None):
        if path is not None:
            name = os.path.join(path, name)
        ScopedFileBase.__init__(self, name)
        if content is not None:
            self.create(content)

    def create(self, content):
        self._create(content)

    @property
    def name(self):
        return self._file
