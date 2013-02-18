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

import os, subprocess, json, sys, glob, errno
from mirbuild.tools import ScopedChdir
from optparse import OptionParser

if hasattr(subprocess, 'check_output'):
    my_check_output = subprocess.check_output
else:
    def my_check_output(*popenargs, **kwargs):
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            raise subprocess.CalledProcessError(retcode, cmd)
        return output

class Builder(object):
    name = 'build.py'

    def __init__(self, path):
        self.__path = os.path.realpath(path)
        self.__metacache = None

    def __getmeta(self):
        cd = ScopedChdir(self.__path)
        try:
            return json.loads(my_check_output([sys.executable, self.name, '-q', 'meta']))
        except subprocess.CalledProcessError:
            print 'failed to get meta information from {0} in {1}'.format(self.name, self.__path)
            raise

    @property
    def __meta(self):
        if self.__metacache is None:
            self.__metacache = self.__getmeta()
        return self.__metacache

    def run(self, args, opt):
        print '##### [{0}] running {1} {2}'.format(self.path, self.name, ' '.join(args))
        if not opt.dryrun:
            cd = ScopedChdir(self.__path)
            subprocess.check_call([sys.executable, self.name] + list(args))

    def supports(self, command):
        return command in self.commands or sum((cmd.startswith(command)) for cmd in self.commands) == 1

    @property
    def path(self):
        return self.__path

    @property
    def project(self):
        return self.__meta['project']

    @property
    def commands(self):
        return self.__meta['commands']

    @property
    def version(self):
        try:
            return self.__meta['version']
        except (TypeError, KeyError):
            return None

    @property
    def dependencies(self):
        return self.__meta['dependencies']

    @property
    def packages(self):
        try:
            return self.__meta['packaging']['debian']['package']
        except (TypeError, KeyError):
            return []

class Walker(object):
    def __init__(self, path, env = None, fastscan = False):
        self.__bpy = {}
        self.__tracked = set()
        self.__scan(path, fastscan, env)

    def __scan(self, path, fast, env):
        if os.path.exists(os.path.join(path, Builder.name)):
            b = Builder(path)
            pro = os.path.split(path)[1] if fast else b.project
            self.__bpy[pro] = b
            if env:
                env.dbg("found " + pro)
        else:
            for e in os.listdir(path):
                if not e.startswith('.'):
                    p = os.path.join(path, e)
                    if os.path.isdir(p):
                        self.__scan(p, fast, env)

    def __project_deps(self, project, rec = False):
        s = set()
        try:
            s |= set([self.__bpy[project]])
            for x in self.__bpy[project].dependencies:
                s |= self.__project_deps(x, True)
        except KeyError:
            if not rec:
                raise RuntimeError("no such project: {0}".format(project))
        return s

    def __sorted_bpy(self, projects = None, force = False):
        if projects is None:
            bpy = self.__bpy.values()
        else:
            s = set()
            for p in projects.split(','):
                s |= self.__project_deps(p.rstrip(os.sep))
            bpy = list(s)
        return self.__sort_by_deps(bpy, force if projects is None else False)

    @property
    def dependencies(self):
        return dict((project, b.path) for project, b in self.__bpy.iteritems())

    def __sort_by_deps(self, src, force):
        src.sort(key = lambda p: p.project)
        dst = []
        tmp = []
        rec = set(src)
        while src:
            p = src.pop(0)
            if set(p.dependencies) <= set(map(lambda p: p.project, dst)):
                dst.append(p)
            else:
                tmp.append(p)
            if not src:
                if set(tmp) != set(rec):
                    src = tmp
                    rec = set(src)
                    tmp = []
                else:
                    sys.stderr.write("WARNING: cannot resolve dependencies for: {0}\n".format(', '.join([p.project for p in tmp])))
                    resolved = set([p.project for p in dst])
                    for u in tmp:
                        deps = set(u.dependencies) - resolved
                        sys.stderr.write("  - project '{0}' depends on unknown project{1} {2}\n".format(u.project, '' if len(deps) == 1 else 's', ', '.join(deps)))
                    if not force:
                        raise RuntimeError("dependency resolver failed")
        return dst

    def check_run(self, args, opt):
        print '##### [{0}] running {1}'.format(os.getcwd(), ' '.join(args))
        if not opt.dryrun:
            subprocess.check_call(args)

    def run(self, args, opt):
        print '##### [{0}] running {1}'.format(os.getcwd(), ' '.join(args))
        if not opt.dryrun:
            subprocess.call(args)

    def debinstall(self, p, opt):
        cd = ScopedChdir(os.path.split(p.path)[0])
        debs = []
        for pkg in p.packages:
            deb = glob.glob("{0}_{1}*.deb".format(pkg, p.version))
            if len(deb) == 1:
                debs.append(deb[0])
            elif len(deb) > 1:
                print "*** WARNING"
        if debs:
            args = ['-i']
            if opt.force_install:
                args = ['--force-depends'] + args
            self.check_run(['/usr/bin/sudo', '/usr/bin/dpkg'] + args + debs, opt)

    def debremove(self, p, opt):
        if p.packages:
            self.run(['/usr/bin/sudo', '/usr/bin/dpkg', '-r'] + p.packages, opt)

    def debpurge(self, p, opt):
        if p.packages:
            self.run(['/usr/bin/sudo', '/usr/bin/dpkg', '--purge'] + p.packages, opt)

    def __load_tracked(self, filename):
        if filename is not None:
            try:
                self.__tracked = set(json.load(open(filename, 'r')))
            except Exception:
                pass

    def __save_tracked(self, filename):
        if filename is not None:
            json.dump(list(self.__tracked), open(filename, 'w'), indent = 4)

    def __clear_tracked(self, filename):
        if filename is not None:
            try:
                os.remove(filename)
            except OSError as ex:
                if ex.errno != errno.ENOENT:
                    raise

    def walk(self, cmds, opt):
        self.__load_tracked(opt.track)
        bpy = self.__sorted_bpy(opt.projects, opt.force)
        if opt.reverse:
            bpy.reverse()
        if not cmds:
            for p in bpy:
                print p.project
        else:
            for p in bpy:
                if p.project in self.__tracked:
                    print 'project "{0}" is already tracked, skipping...'.format(p.project)
                else:
                    args = []
                    if not opt.nodeps:
                        args = map(lambda d: '--with-{0}={1}'.format(d, self.__bpy[d].path), p.dependencies)
                    for c in cmds:
                        if hasattr(self, c):
                            getattr(self, c)(p, opt)
                        elif p.supports(c):
                            p.run([c] + args, opt)
                        else:
                            print 'project "{0}" does not support "{1}" command, skipping...'.format(p.project, c)
                    if not opt.dryrun:
                        self.__tracked.add(p.project)
                        self.__save_tracked(opt.track)
            if not opt.dryrun:
                self.__clear_tracked(opt.track);

if __name__ == "__main__":
    parser = OptionParser(usage = '{0} -m mirbuild.walk [options] [mirbuild commands]'.format(sys.executable))
    parser.add_option('-t', '--track', dest = 'track', type = 'string',
                      metavar = 'FILE', help = 'track projects that have already been worked on')
    parser.add_option('-p', '--projects', dest = 'projects', type = 'string',
                      metavar = 'NAME', help = 'run only for dependencies of comma-separated projects')
    parser.add_option('-b', '--base', dest = 'base', type = 'string', default = '.',
                      metavar = 'PATH', help = 'base path to projects')
    parser.add_option('-r', '--reverse', dest = 'reverse', default = False, action = 'store_true',
                      help = 'reverse dependency order')
    parser.add_option('-n', '--no-deps', dest = 'nodeps', default = False, action = 'store_true',
                      help = 'do not set --with-xxx for dependent projects')
    parser.add_option('-f', '--force', dest = 'force', default = False, action = 'store_true',
                      help = 'force action even if dependency resolver fails')
    parser.add_option('-F', '--force-install', dest = 'force_install', default = False, action = 'store_true',
                      help = 'force dpkg install even if dependency problems are reported')
    parser.add_option('--dry-run', dest = 'dryrun', default = False, action = 'store_true',
                      help = 'do not actually run the commands')
    (opt, args) = parser.parse_args()
    try:
        Walker(opt.base).walk(args, opt)
    except RuntimeError as ex:
        sys.stderr.write("ERROR: {0}\n".format(ex))
        exit(1)
