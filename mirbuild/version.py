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
Support for parsing version information and writing out version files

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'CVersionFile DebianVersionInfo'.split()

import dateutil.parser
import debian.changelog
import calendar
import os
import re
import string
import hashlib
from datetime import date
from StringIO import StringIO
from mirbuild.tools import LazyFileWriter
from mirbuild.packagers.pkg_debian import DebianControl

class Copyright:
    # Default copyright text if no debian/copyright file exists
    __copyright = 'Copyright (C) {0} Last.fm Ltd'.format(date.today().year)
    __copyright_short = '(C) {0} Last.fm Ltd'.format(date.today().year)

    # This regex extracts from the "Copyright" field in the copyright file.
    # It is not matching just an arbitrary string but a machine readable field.
    # http://dep.debian.net/deps/dep5/#fields
    __re_get = 'Copyright:\\s+(.+)$'
    __re_rep ='(?:\\([Cc]\\)\\s+)?[Cc]opyright(?:\\s+\\([Cc]\\))?'

    def __init__(self, filename = 'debian/copyright'):
        try:
            fh = open(filename, 'r')
            txt = fh.read()
            m = re.search(self.__re_get, txt, re.MULTILINE)

            if m:
                self.__copyright = m.group(1).strip()
                self.__copyright_short = re.sub(self.__re_rep, '(C)', self.__copyright)

        except IOError:
            # use the default
            None

    @property
    def full(self):
        return self.__copyright

    @property
    def short(self):
        return self.__copyright_short

class VersionFile(object):
    def __init__(self, env, filename):
        self._env = env
        self.__file = filename

    @property
    def filename(self):
        return self.__file

    def clean(self):
        self._env.remove_files(self.filename)

class CVersionFile(VersionFile):
    def __init__(self, env, filename, **opts):
        VersionFile.__init__(self, env, filename)
        self.__guard = opts.get('guard', None)
        self.__prefix = opts.get('prefix', None)
        self.__namespace = opts.get('namespace', ["fm", "last", "version"])

    @staticmethod
    def can_create(filename):
        (root, ext) = os.path.splitext(filename)
        return ext in ('.h', '.hpp', '.hxx')

    def __defaults(self, name, project):
        if self.__guard is None or self.__prefix is None:
            parts = []
            while name:
                (name, part) = os.path.split(name)
                if part in ['', 'include']:
                    break
                parts.append(re.sub('\W+', '_', part))
            parts.reverse()
            base = '_'.join(parts).upper()
            if self.__prefix is None:
                self.__prefix = re.sub('\W+', '_', project.upper()) + '_'
            if self.__guard is None:
                self.__guard = self.__prefix
                self.__guard += base + '_' + hashlib.md5(project).hexdigest()[0:8].upper() + '_'

    def set_guard(self, guard):
        self.__guard = guard

    def set_prefix(self, prefix):
        self.__prefix = prefix

    def __apply_prefix(self, name):
        return '{0}{1}'.format(self.__prefix, name);

    def __define(self, fh, name, value):
        fh.write('#define {0} {1}\n'.format(self.__apply_prefix(name), value))

    def __defstr(self, fh, name, value):
        value = re.sub('"', '\\"', value)
        fh.write('#define {0}_STR "{1}"\n'.format(self.__apply_prefix(name), value))

    def __vinfo_write(self, fh, fname, dname, rtype):
        fh[0].write('      static {0} {1}() {{ return {2}; }}\n'.format(rtype, fname.lower(), self.__apply_prefix(dname)))
        fh[1].write('      virtual {0} {1}() const {{ return {2}_vinfo::{1}(); }}\n'.format(rtype, fname.lower(), self.__project_ident))

    def __writestr(self, fh, name, value, add_suffix = True):
        dname = '{0}_STR'.format(name)
        fname = dname if add_suffix else name
        self.__defstr(fh[0], name, value)
        self.__vinfo_write(fh[1], fname, dname, 'std::string');

    def __write(self, fh, name, value, rtype = 'int'):
        self.__define(fh[0], name, value)
        self.__vinfo_write(fh[1], name, name, rtype);

    @property
    def __project_ident(self):
        return re.sub('\W+', '_', self._env.project_name)

    def __vinfo(self, fh):
        nsbeg = ' '.join(['namespace {0} {{'.format(ns) for ns in self.__namespace])
        nsend = '}'*len(self.__namespace);
        return '''
#ifdef __cplusplus

#include <string>

{3}

   ////////////////////////////////////////////////////////////////////////////
   // Use this class if you just need access to version info and have no need
   // to instantiate an object that will provide access to that version info.

   struct {0}_vinfo
   {{
{1}
   }};

   ////////////////////////////////////////////////////////////////////////////
   // Use this class if you have an existing interface that defines the vinfo
   // functions and expects them to be implemented by a derived class.

   template <typename Base>
   struct {0}_vinfo_ : Base
   {{
{2}
   }};

   ////////////////////////////////////////////////////////////////////////////

{4}

#endif /* __cplusplus */
'''.format(self.__project_ident, fh[0].getvalue(), fh[1].getvalue(), nsbeg, nsend)

    def generate(self, info):
        self.__defaults(self.filename, self._env.project_name)
        description = self._env.project_name if info.description() is None else info.description()
        copyright = Copyright()
        fh = [ LazyFileWriter(self.filename), [ StringIO(), StringIO() ] ]
        fh[0].create()
        fh[0].write('#ifndef ' + self.__guard + '\n')
        fh[0].write('#define ' + self.__guard + '\n\n')
        self.__writestr(fh, 'NAME', self._env.project_name, False)
        self.__writestr(fh, 'VERSION', '{0}.{1}.{2}'.format(info.major_rev(), info.minor_rev(), info.patchlevel()), False)
        self.__writestr(fh, 'DESCRIPTION', description, False)
        self.__writestr(fh, 'COPYRIGHT', copyright.short, False)
        self.__writestr(fh, 'COPYRIGHT_FULL', copyright.full, False)
        fh[0].write('\n')
        self.__writestr(fh, 'PROJECT', self._env.project_name)
        self.__writestr(fh, 'PACKAGE', info.package())
        self.__writestr(fh, 'AUTHOR', info.author())
        self.__writestr(fh, 'RELEASE_ISODATE', info.date().isoformat())
        self.__writestr(fh, 'RELEASE_YEAR', info.date().strftime('%Y'))
        self.__writestr(fh, 'RELEASE_DATE', info.date().strftime('%Y-%m-%d'))
        self.__writestr(fh, 'RELEASE_TIME', info.date().strftime('%H:%M:%S'))
        self.__writestr(fh, 'FULL_REVISION', info.full_version())
        self.__writestr(fh, 'REVISION', info.upstream_version())
        fh[0].write('\n')
        self.__write(fh, 'RELEASE_YEAR', info.date().strftime('%Y'))
        self.__write(fh, 'RELEASE_EPOCH_TIME', int(info.time()), 'time_t')
        self.__write(fh, 'MAJOR_REVISION', info.major_rev())
        self.__write(fh, 'MINOR_REVISION', info.minor_rev())
        self.__write(fh, 'PATCHLEVEL', info.patchlevel())
        fh[0].write(self.__vinfo(fh[1]))
        fh[0].write('\n#endif /* ' + self.__guard + ' */\n')
        fh[0].commit()

class VersionFileFactory(object):
    implementations = [CVersionFile]

    @classmethod
    def create(cls, env, filename, **opts):
        assert isinstance(filename, basestring)
        cand = [c for c in cls.implementations if c.can_create(filename)]
        if len(cand) != 1:
            raise RuntimeError('{0} VersionFile candidates for "{1}", please use a concrete implementation'.format('No' if not cand else 'Too many', filename))
        return cand[0](env, filename, **opts)

class VersionInfo(object):
    def package(self):
        return None

    def description(self):
        return None

    def author(self):
        return None

    def time(self):
        return None

    def date(self):
        return None

    def full_version(self):
        return None

    def package_version(self):
        return None

    def upstream_version(self):
        return None

    def major_rev(self):
        return None

    def minor_rev(self):
        return None

    def patchlevel(self):
        return None

    def distributions(self):
        return None

    def urgency(self):
        return None

class DebianVersionInfo(VersionInfo):
    _re_author = re.compile(r'(.*)\s+<(.*)>')
    _re_version = re.compile(r'((\d+)\.(\d+)\.(\d+)).*')

    def __init__(self, dir = None):
        if dir is None:
            if os.path.exists('debian/changelog'):
                dir = 'debian'
            elif os.path.exists('changelog'):
                dir = '.'
            else:
                raise RuntimeError('No changelog file found')
        self.__chlog = debian.changelog.Changelog()
        self.__chlog.parse_changelog(open(os.path.join(dir, 'changelog'), 'r'))
        self.__current = iter(self.__chlog).next()

    @staticmethod
    def can_parse():
        return os.path.exists('debian/changelog') or os.path.exists('changelog')

    def package(self):
        return self.__current.package

    def description(self):
        try:
            return DebianControl().package_info(self.__current.package).summary
        except Exception:
            return None

    def author(self):
        return self.__current.author

    def author_name(self):
        return self._re_author.match(self.author()).group(1)

    def author_email(self):
        return self._re_author.match(self.author()).group(2)

    def date(self):
        return dateutil.parser.parse(self.__current.date)

    def time(self):
        return calendar.timegm(self.date().timetuple())

    def full_version(self):
        return self.__current.version.full_version

    def package_version(self):
        return self.__current.version.debian_version

    def upstream_version(self):
        return self._re_version.match(self.__current.version.upstream_version).group(1)

    def __version_part(self, part):
        return self._re_version.match(self.__current.version.upstream_version).group(2 + part)

    def major_rev(self):
        return self.__version_part(0)

    def minor_rev(self):
        return self.__version_part(1)

    def patchlevel(self):
        return self.__version_part(2)

    def distributions(self):
        return self.__current.distributions

    def urgency(self):
        return self.__current.urgency

class VersionInfoFactory(object):
    implementations = [DebianVersionInfo]

    @classmethod
    def create(cls):
        cand = [c for c in cls.implementations if c.can_parse()]
        if len(cand) != 1:
            raise RuntimeError('{0} VersionInfo candidates, please use a concrete implementation'.format('No' if not cand else 'Too many'))
        return cand[0]()
