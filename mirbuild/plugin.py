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
Plugin base class

Base class for plugins extending the functionality of a project.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'Plugin'.split()

class Plugin(object):
    def __init__(self):
        pass

    def configure(self, project):
        pass

    def build(self, project):
        pass

    def clean(self, project):
        pass

    def realclean(self, project):
        pass

    def install(self, project):
        pass

    def package(self, project):
        pass

    def test(self, project):
        pass

    def pre_configure(self, project):
        pass

    def pre_build(self, project):
        pass

    def pre_clean(self, project):
        pass

    def pre_realclean(self, project):
        pass

    def pre_install(self, project):
        pass

    def pre_package(self, project):
        pass

    def pre_test(self, project):
        pass

    def post_configure(self, project):
        pass

    def post_build(self, project):
        pass

    def post_clean(self, project):
        pass

    def post_realclean(self, project):
        pass

    def post_install(self, project):
        pass

    def post_package(self, project):
        pass

    def post_test(self, project):
        pass
