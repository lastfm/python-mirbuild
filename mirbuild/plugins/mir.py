# -*- coding: utf-8 -*-

r"""
MIR plugins for mirbuild

Plugins used by the Last.fm MIR team.

"""

__author__ = 'Marcus Holland-Moritz <marcus@last.fm>'
__all__ = 'Service ThriftService ServiceInitScript ThriftServiceInitScript DatasetProvider'.split()

import re
import os
import mirbuild.plugin

class ServiceInitScript(object):
    def __init__(self, service, shell = True, config = True, logging = True, **args):
        self.service = service
        self.filename = '/etc/init.d/' + service
        self.shell = shell
        self.config = config
        self.logging = logging
        self.__args = args
        self.__cmds = []
        self.__shell_cmds = []
        self.__extra_args = []

    def add_extra_arguments(self, *args):
        self.__extra_args += args

    def add_shell_command(self, name, command):
        assert self.shell
        self.__shell_cmds.append([name, command])

    def add_command(self, name, impl):
        self.__cmds.append([name, impl])

    def __format_args(self, args, indent = 0, width = 80):
        tmp = []
        while args:
            ap = [ args.pop(0) ]
            while args and not args[0].startswith('-'):
                ap.append('"' + args[0] + '"' if re.search('\s|\$', args[0]) else args[0])
                args.pop(0)
            tmp.append(' '.join(ap))
        lines = []
        while tmp:
            line = ' '*indent + tmp.pop(0)
            while tmp and len(line + tmp[0]) < width:
                line += ' ' + tmp.pop(0)
            if tmp:
                line += ' \\\n'
            lines.append(line)
        return ''.join(lines)

    def write(self, filename, **args):
        for k, v in self.__args.iteritems():
            args[k] = v

        if not args.has_key('service'):
            args['service'] = self.service

        if not args.has_key('defaults'):
            args['defaults'] = '/etc/default/' + self.service

        if not args.has_key('pidfile'):
            args['pidfile'] = '/var/run/{0}/{1}.pid'.format(args['user'], self.service)

        if not args.has_key('summary_format'):
            args['summary_format'] = '{summary}'

        for action in 'pre_start post_start pre_stop post_stop'.split():
            if not args.has_key(action):
                args[action] = ['/bin/true']

        args['summary'] = args['summary_format'].format(**args)

        init = '''#!/bin/bash
### BEGIN INIT INFO
# Provides:             {service}
# Required-Start:       $syslog $local_fs $remote_fs $time $network $named
# Required-Stop:        $syslog $local_fs $remote_fs $time $network $named
# Should-Start:
# Should-Stop:
# Default-Start:        2 3 4 5
# Default-Stop:         0 1 6
# Short-Description:    {service} - {summary}
# Description:          {service} - {summary}
'''.format(**args)

        desc = args.get('description', None)
        if desc is not None:
            for line in desc:
                init += '#                       {0}\n'.format(line)

        init += '''### END INIT INFO

NAME={service}
DESC="{summary}"

DAEMON={binary}
DEFAULTS={defaults}
PIDFILE={pidfile}
QUIET=--quiet
'''.format(**args)

        init += self._global_vars(**args)

        if self.shell or self._needs_netcat():
            init += '''
for prog in /bin/nc /bin/netcat /usr/bin/nc /usr/bin/netcat; do
    if [ -x "$prog" ]; then
        NETCAT="$prog"
        break
    fi
done

if [ ! -x "$NETCAT" ]; then
    log_failure_msg "no netcat executable found"
    exit 1
fi
'''

        init += '''
test -x $DAEMON || exit 0

set -e

. /lib/lsb/init-functions

if [ ! -s "$DEFAULTS" ]; then
    log_failure_msg "No defaults file found at $DEFAULTS"
    exit 1
fi
'''
        init += self._global_checks(**args)

        init += '''
. $DEFAULTS

export PATH="${PATH:+$PATH:}/usr/sbin:/sbin"
'''

        if self.__shell_cmds:
            assert self.shell
            init += '''
send_shell_command () {
    echo "$@" | $NETCAT -q 0 localhost $SHELL_PORT >/dev/null 2>&1
}
'''

        for cmd in self.__cmds:
            init += '\ncommand_' + cmd[0] + ' () {\n' + re.sub('^', '    ', cmd[1].strip()) + '\n}\n'

        daemon_params = [ '--daemon',
                          '--pidfile', '$PIDFILE',
                          '--noerr' ]

        params = []

        if self.config:
            params += [ '--config', '$CONFIG' ]

        params += [ '--uid', '$DAEMON_UID' ]

        if self.shell:
            params += [ '--shell-port', '$SHELL_PORT' ]

        if self.logging:
            params += [ '--logging-config', '$LOGGING_CONFIG' ]

        params += self.__extra_args

        init += '''
start_service () {
    start-stop-daemon $QUIET --start --pidfile $PIDFILE --startas $DAEMON -- \\
''' + self.__format_args(daemon_params + params, indent = 12) + '\n}\n'

        init += '''
debug_service () {
    $DAEMON \\
''' + self.__format_args(params, indent = 12) + '\n}\n'

        init += '''
stop_service () {{
    start-stop-daemon $QUIET --stop --oknodo --pidfile $PIDFILE --retry={0}
}}
'''.format(args.get('stop_service_schedule', 'TERM/60/KILL/10'))

        for action in 'pre_start post_start pre_stop post_stop'.split():
            init += "\n{0}_actions".format(action) + " () {\n"
            for a in args[action]:
                init += "    {0}\n".format(a)
            init += "}\n"

        if self.shell:
            init += '''
check_shell () {
    echo -n '' | $NETCAT -w1 -q0 localhost $SHELL_PORT >/dev/null 2>&1
}
'''

        init += '''
check_status () {
    local pid status ping

    status=3 # program not running

    if [ -n "${PIDFILE:-}" -a -e "$PIDFILE" ]; then
        read pid < "$PIDFILE" || true
        if [ -n "${pid:-}" ]; then
            if $(kill -0 "${pid:-}" 2> /dev/null); then
                status=0 # service is running
            elif ps "${pid:-}" >/dev/null 2>&1; then
                status=0 # service is running, but not owned by this user
            else
                status=2 # service is dead and /var/run pid file exists
            fi
        fi
    fi
'''
        init += self._check_connect(**args)

        init += '''
    echo -n $status
}
'''
        init += '''
case "$1" in
    start)
        pre_start_actions
        log_daemon_msg "Starting $DESC"
        log_progress_msg "$NAME"
        start_service
        log_end_msg 0
        post_start_actions
        ;;

    stop)
        pre_stop_actions
        log_daemon_msg "Stopping $DESC"
        log_progress_msg "$NAME"
        stop_service
        log_end_msg 0
        post_stop_actions
        ;;

    restart|force-reload)
        pre_stop_actions
        log_daemon_msg "Stopping $DESC"
        log_progress_msg "$NAME"
        stop_service
        log_end_msg 0
        post_stop_actions
        pre_start_actions
        log_daemon_msg "Starting $DESC"
        log_progress_msg "$NAME"
        start_service
        log_end_msg 0
        post_start_actions
        ;;

    debug)
        debug_service
        ;;

    status)
        status="$(check_status)"
        case "$status" in
'''

        if self.shell:
            init += '''            0) if check_shell; then
                   shell="up on port $SHELL_PORT"
               else
                   shell="down"
               fi
               log_success_msg "$DESC is {status_msg} (shell is $shell)"
               ;;
'''.format(status_msg = self._status_message(**args))
        else:
            init += '''            0) log_success_msg "$DESC is {status_msg}" ;;
'''.format(status_msg = self._status_message(**args))

        init += '''            1) log_success_msg "$DESC is starting" ;;
            2) log_success_msg "$DESC is NOT running (but pidfile exists)" ;;
            *) log_success_msg "$DESC is NOT running" ;;
        esac
        exit $status
        ;;
'''

        commands = 'start|stop|restart|status|debug|force-reload'.split('|')

        for cmd in self.__cmds:
            init += '''
    {0})
        if command_{0}; then
            log_success_msg "$DESC '{0}' successful"
        else
            log_failure_msg "$DESC '{0}' failed (status $?)"
            exit 1
        fi
        ;;
'''.format(cmd[0])
            commands.append(cmd[0])

        for cmd in self.__shell_cmds:
            init += '''
    {0})
        if send_shell_command {1}; then
            log_success_msg "sent '{1}' command to $DESC"
        else
            log_failure_msg "could not connect to $DESC shell"
            exit 1
        fi
        ;;
'''.format(*cmd)
            commands.append(cmd[0])

        init += '''
    *)
        echo "Usage: $0 {0}" >&2
        exit 1
        ;;
esac

exit 0
'''.format('{' + '|'.join(commands) + '}')

        open(filename, 'w').write(init)
        os.chmod(filename, 0755)

    def _needs_netcat(self):
        return False

    def _global_vars(self, **args):
        return ''

    def _global_checks(self, **args):
        return ''

    def _check_connect(self, **args):
        return ''

    def _status_message(self, **args):
        return 'up'

class ThriftServiceInitScript(ServiceInitScript):
    def __init__(self, service, fm303 = True, **args):
        ServiceInitScript.__init__(self, service, **args)
        self.fm303 = fm303
        self.add_extra_arguments('--port', '$THRIFT_PORT')

    def _needs_netcat(self):
        return not self.fm303

    def _global_vars(self, **args):
        init = ''

        if self.fm303:
            init += 'FM303_CLIENT={fm303client}\n'.format(**args)

        return init

    def _global_checks(self, **args):
        init = ''

        if self.fm303:
            init += '''
if [ ! -x "$FM303_CLIENT" ]; then
    log_failure_msg "FM303 client not found at $FM303_CLIENT"
    exit 1
fi
'''
        return init

    def _check_connect(self, **args):
        init = '''
    if [ "$status" == "0" ]; then
'''
        if self.fm303:
            init += '        $FM303_CLIENT --port $THRIFT_PORT --status >/dev/null 2>&1\n'
        else:
            init += '        $NETCAT -w1 -q0 localhost $THRIFT_PORT </dev/null 2>/dev/null\n'

        init += '''        case "$?" in
            0)
                # service is just fine
                ;;
            *)
                # service is most probably starting
                status=1
                ;;
        esac
    fi
'''
        return init

    def _status_message(self, **args):
        return 'listening on port $THRIFT_PORT'

class Service(mirbuild.plugin.Plugin):
    init_script_class = ServiceInitScript

    def __init__(self, name, **args):
        self.name = name
        self.__binary = args.get('binary', name)
        self.__package = args.get('package', 'lastfm-' + name)
        self.__user = args.get('user', name)
        self.__group = args.get('group', self.__user)
        self.__home = args.get('home', '/var/run/{0}'.format(self.__user))
        self.__init = args.get('init', [ self.init_script_class(name) ])
        self.__create = args.get('create', True)

    @property
    def init(self):
        assert len(self.__init) == 1
        return self.__init[0]

    def add_extra_arguments(self, *args):
        for init in self.__init:
            init.add_extra_arguments(*args)

    def add_command(self, name, impl):
        for init in self.__init:
            init.add_command(name, impl)

    def add_shell_command(self, name, command):
        for init in self.__init:
            init.add_shell_command(name, command)

    def pre_package(self, project):
        if self.__create:
            project.packager.create_user(self.__user, self.__group, home = self.__home,
                                         desc = '{0} service user'.format(self.name),
                                         package = self.__package)

            project.packager.create_group(self.__group, package = self.__package)

            for d in 'lib log run'.split():
                project.packager.create_dir('/var/{0}/{1}'.format(d, self.__user),
                                            user = self.__user, group = self.__group,
                                            package = self.__package)

        for init in self.__init:
            project.packager.add_service(init.service, package = self.__package)

    def post_install(self, project):
        info = project.packager.get_package_info(self.__package)
        for init in self.__init:
            project.env.say("**** writing " + init.filename)
            init.write(project.installpath(init.filename, mkdir = True),
                       summary = info.summary,
                       description = info.description,
                       binary = project.prefixpath(os.path.join('bin', self.__binary)),
                       user = self.__user,
                       group = self.__group,
                       **self._extra_init_write_args(project))

    def _extra_init_write_args(self, project):
        return {}

class ThriftService(Service):
    init_script_class = ThriftServiceInitScript

    def __init__(self, name, **args):
        Service.__init__(self, name, **args)
        self.__fm303client = args.get('fm303client', 'bin/fm303-client')

    def _extra_init_write_args(self, project):
        return { 'fm303client': project.prefixpath(self.__fm303client) }

class DatasetProvider(mirbuild.plugin.Plugin):
    def __init__(self, name, **args):
        self.name = name
        self.__packages = args.get('packages', ['lastfm-' + name + '-dataset', 'lastfm-' + name + '-datagen'])
        self.__loginpackages = args.get('loginpackages', [pkg for pkg in self.__packages if pkg.endswith('-datagen')])
        self.__user = args.get('user', name)
        self.__group = args.get('group', 'datasync')

    def pre_package(self, project):
        dir = '/var/lib/{0}'.format(self.__user)

        for pkg in self.__packages:
            project.packager.create_user(self.__user, self.__group, home = dir,
                                         desc = '{0} dataset user'.format(self.name),
                                         package = pkg, allow_login = pkg in self.__loginpackages)

            project.packager.create_group(self.__group, package = pkg)

            project.packager.create_dir(dir, user = self.__user, group = self.__group,
                                        package = pkg)
