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
Generic hierarchical cache implementation

This file implements a Cacheable base class as well as a Cache class that allows
other Cacheable objects (including other Cache instance) to be registered to.
Each Cacheable solely needs to implement a gettable and settable state property.
Each Cache object can be (de-)serialised from/to a file as a JSON stream, and it
will do so recursively for all registered Cacheables. For example, this is what
a cache tree might look like:

  Cache('root')
  |
  +---- Cache('foo')
  |     |
  |     +---- Cacheable Object('a')
  |     |
  |     `---- Cacheable Object('b')
  |
  `---- Cacheable Object('c')

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'Cacheable Cache'.split()

import os
import sys
import json

class Cacheable(object):
    def __init__(self, key):
        self.__key = key

    @property
    def key(self):
        return self.__key

class Cache(Cacheable):
    def __init__(self, key = None, filename = None):
        Cacheable.__init__(self, key)
        self.__reg = {}
        self.__file = filename
        self.__state = None

    @property
    def filename(self):
        return self.__file

    def register(self, cacheable):
        assert isinstance(cacheable, Cacheable)
        assert cacheable.key is not None
        assert cacheable.key not in self.__reg
        self.__reg[cacheable.key] = cacheable
        if self.__state is not None and cacheable.key in self.__state:
            cacheable.state = self.__state[cacheable.key]
            del self.__state[cacheable.key]

    @property
    def state(self):
        cache = {}
        for key, cacheable in self.__reg.iteritems():
            cache[key] = cacheable.state
        return cache

    @state.setter
    def state(self, value):
        self.__state = value
        if self.__state is not None:
            for key, cacheable in self.__reg.iteritems():
                if key in self.__state:
                    cacheable.state = self.__state[key]
                    del self.__state[key]

    def _load(self, filename):
        assert filename is not None
        return json.load(open(filename, 'r'))

    def _save(self, filename, state):
        assert filename is not None
        json.dump(state, open(filename, 'w'), indent = 4)

    def load(self, filename = None):
        if filename is None:
            filename = self.__file
        state = self._load(filename)
        self.state = state[sys.platform]

    def save(self, filename = None):
        if filename is None:
            filename = self.__file
        state = self._load(filename) if os.path.exists(filename) else {}
        state[sys.platform] = self.state
        self._save(filename, state)
