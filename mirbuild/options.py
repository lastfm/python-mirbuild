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
Options handling classes for the mirbuild framework

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'

import mirbuild.cache

class LocalOptions(mirbuild.cache.Cacheable):
    def __init__(self, key = None):
        mirbuild.cache.Cacheable.__init__(self, key)
        self.__cached = set()

    def ensure_value(self, option, value):
        if not hasattr(self, option) or getattr(self, option) is None:
            setattr(self, option, value)

    def set_value(self, option, value, unique = True):
        if isinstance(getattr(self, option), list):
            current = getattr(self, option)
            if not unique or value not in current:
                setattr(self, option, current + [value])
        else:
            setattr(self, option, value)

    def add_option(self, parser, option, dest, type, metavar, help, choices = None, default = None, cache = True, defaultstr = True, multi = False, unique = True):
        if multi and default is None:
            default = list()
        self.ensure_value(dest, default)
        defstr = ''
        if defaultstr:
            if multi:
                if getattr(self, dest) is not None and len(getattr(self, dest)) > 0:
                    defstr = ' [default: {0}]'.format(', '.join(getattr(self, dest)))
            else:
                if getattr(self, dest) is not None:
                    defstr = ' [default: {0}]'.format(getattr(self, dest))
        parser.add_option(*option.split('|'), action = 'callback', type = type, choices = choices,
                          metavar = metavar, help = help + defstr,
                          callback = lambda option, optstr, value, parser: self.set_value(dest, value, unique))
        if cache:
            self.__cached.add(dest)

    def add_bool_option(self, parser, option, dest, help, cache = True):
        self.ensure_value(dest, False)
        parser.add_option(*option.split('|'), action = 'callback', help = help,
                          callback = lambda option, optstr, value, parser: self.set_value(dest, True))
        if cache:
            self.__cached.add(dest)

    @property
    def state(self):
        return dict([ (k, v) for k, v in self.__dict__.iteritems() if k in self.__cached ])

    @state.setter
    def state(self, value):
        self.__dict__.update(value)

    def state_merge(self, value):
        for k, v in value.iteritems():
            self.ensure_value(k, v)
