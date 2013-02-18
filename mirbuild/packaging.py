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
Packaging modeling classes

The classes in this file implement the logic required to package a project.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'Packaging'.split()

from mirbuild.tools import ScopedFileBase, ScopedFileCopy, LazyFileWriter
from mirbuild.options import LocalOptions
from optparse import OptionGroup
from debian.debfile import Deb822
import json, os, re, sys

class PackageInfo(object):
    pass

class UserInfo(object):
    pass

class DirectoryInfo(object):
    pass

class Packaging(object):
    pass

class PackagingFactory(object):
    implementations = set()

    @classmethod
    def create_all(cls, env):
        return [c(env) for c in cls.implementations if c.can_package()]

    @classmethod
    def register(cls, packaging_class):
        cls.implementations.add(packaging_class)
