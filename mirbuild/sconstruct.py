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

__all__ = "mirbuild_vars add_mirbuild_vars mirbuild_env setup_mirbuild_env".split()

from SCons.Script import *

def mirbuild_vars():
    return add_mirbuild_vars(Variables('scons-local-config.py', ARGUMENTS))

def add_mirbuild_vars(vars):
    vars.AddVariables(
        ('CPPPATH',),
        ('LIBPATH',),
        ('CCFLAGS',),
        ('CPPDEFINES',),
        ('PREFIX', 'install prefix' , '/usr/local'),
        ('CC',),
        ('CXX',),
        ('DESTDIR', 'install files to this path', ''),
        )
    return vars

def mirbuild_env():
    return setup_mirbuild_env(Environment(variables = mirbuild_vars()))

def setup_mirbuild_env(env):
    return env
