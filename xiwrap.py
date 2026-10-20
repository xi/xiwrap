#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path

USAGE = """Usage: xiwrap [OPTION]... -- CMD

Example: xiwrap --include host-os --setenv TERM -- bash

The following options are available:

-h, --help              Print this message and exit
--debug                 Print the bwrap command instead of executing it.
--share-pid             Do not create new pid namespace.
--share-net             Do not create new network namespace.
--share-ipc             Do not create new ipc namespace.
--setenv VAR [VALUE]    Set an environment variable. If VALUE is not provided,
                        share it from the current environment
--[ro-]bind[-try] SRC [DEST], --dev-bind[-try] SRC [DEST]
                        Bind mount the host path SRC on DEST. If SRC is not
                        provided, it is the same as DEST. See `man bwrap` for
                        details.
--proc DEST             Mount new procfs on DEST.
--dev DEST              Mount new dev on DEST.
--tmpfs DEST            Mount new tmpfs on DEST.
--mqueue DEST           Mount new mqueue on DEST.
--dir DEST              Create a directory at DEST.
--dbus-see NAME, --dbus-talk NAME, --dbus-own NAME,
--dbus-call NAME=RULE, --dbus-broadcast NAME=RULE,
--dbus-system-see NAME, --dbus-system-talk NAME, --dbus-system-own NAME,
--dbus-system-call NAME=RULE, --dbus-system-broadcast NAME=RULE
                        Allow filtered access to dbus. See `man xdg-dbus-proxy`
                        for details.
-I FILE --include FILE  Load additional options from FILE. FILE can be an
                        absolute path or relative to the current directory,
                        $XDG_CONFIG_HOME/xiwrap/includes/ or
                        /etc/xiwrap/includes/. FILE must contain one option per
                        line, without the leading --. Empty lines or lines
                        starting with # are ignored.
"""

DBUS_SESSION_SRC = f'{os.environ["XDG_RUNTIME_DIR"]}/dbus-session-proxy-{os.getpid()}'
DBUS_SESSION_DEST = '$XDG_RUNTIME_DIR/bus'
DBUS_SYSTEM_SRC = f'{os.environ["XDG_RUNTIME_DIR"]}/dbus-system-proxy-{os.getpid()}'
DBUS_SYSTEM_DEST = '/run/dbus/system_bus_socket'

# https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
XDG_DEFAULTS = {
    'XDG_DATA_HOME': '.local/share',
    'XDG_CONFIG_HOME': '.config',
    'XDG_STATE_HOME': '.local/state',
    'XDG_CACHE_HOME': '.cache',
}


class RuleError(ValueError):
    def __init__(self, key, args):
        rule = ' '.join([key, *args])
        super().__init__(f'Invalid rule: {rule}')


def expandvars(path, env):
    original = os.environ

    os.environ = {**env}
    if 'HOME' in env:
        for var, default in XDG_DEFAULTS.items():
            if var not in env:
                os.environ[var] = str(Path(env['HOME']) / default)

    try:
        return os.path.expandvars(path)
    finally:
        os.environ = original


class DBusProxy:
    def __init__(self, rules, dest, src, app_id, sync_fd):
        self.cmd = ['xdg-dbus-proxy', f'--fd={sync_fd}', dest, src, '--filter']
        for value, typ in sorted(rules.items()):
            self.cmd.append(f'--{typ}={value}')

        wrapper = RuleSet()
        wrapper.push_rule('tmpfs', '/tmp')
        wrapper.push_rule('dev', '/dev')
        wrapper.push_rule('proc', '/proc')
        wrapper.push_rule('bind', '/run')
        for path in ['/bin', '/lib', '/lib64', '/usr', '/etc']:
            wrapper.push_rule('ro-bind-try', path)

        self.cmd = wrapper.build(self.cmd)
        self.fds = [sync_fd, *wrapper.fds]

    def popen(self):
        return subprocess.Popen(self.cmd, pass_fds=self.fds)


class RuleSet:
    def __init__(self):
        self.env = {}
        self.paths = {}
        self.dbus_session = {}
        self.dbus_system = {}
        self.share = {}
        self.sync_fds = None
        self.fds = []
        self.debug = False
        self.usage = False
        self.userconfig = Path(
            expandvars('$XDG_CONFIG_HOME/xiwrap/includes', os.environ)
        )
        self.sysconfig = Path('/etc/xiwrap/includes')

    def find_config_file(self, name, cwd):
        if name.startswith('/'):
            return Path(name)
        elif name.startswith('~'):
            return Path(name).expanduser()
        for base in [cwd, self.userconfig, self.sysconfig]:
            path = base / name
            if path.exists():
                return path
        raise FileNotFoundError(name)

    def parse_env(self, key, args):
        if len(args) == 2:
            return args[0], args[1]
        elif len(args) == 1:
            return args[0], os.getenv(args[0])
        else:
            raise RuleError(key, args)

    def parse_path(self, key, args):
        if len(args) == 2:
            return args[0], args[1]
        elif len(args) == 1:
            return args[0], args[0]
        else:
            raise RuleError(key, args)

    def ensure_sync_fds(self):
        if self.sync_fds is None:
            self.sync_fds = os.pipe2(0)

    def push_rule(self, key, *args, cwd=None):
        if key == 'include':
            if len(args) != 1:
                raise RuleError(key, args)
            path = self.find_config_file(args[0], cwd)
            self.read_config_file(path)
        elif key in ['share-ipc', 'share-pid', 'share-net']:
            if len(args) != 0:
                raise RuleError(key, args)
            self.share[key] = True
        elif key in ['dbus-see', 'dbus-talk', 'dbus-own', 'dbus-call', 'dbus-broadcast']:
            if len(args) != 1:
                raise RuleError(key, args)
            self.ensure_sync_fds()
            self.push_rule('ro-bind', DBUS_SESSION_SRC, DBUS_SESSION_DEST)
            self.dbus_session[args[0]] = key.removeprefix('dbus-')
        elif key in [
            'dbus-system-see',
            'dbus-system-talk',
            'dbus-system-own',
            'dbus-system-call',
            'dbus-system-broadcast',
        ]:
            if len(args) != 1:
                raise RuleError(key, args)
            self.ensure_sync_fds()
            self.push_rule('ro-bind', DBUS_SYSTEM_SRC, DBUS_SYSTEM_DEST)
            self.dbus_system[args[0]] = key.removeprefix('dbus-system-')
        elif key == 'setenv':
            var, value = self.parse_env(key, args)
            if value is not None:
                self.env[var] = value
        elif key in [
            'bind',
            'bind-try',
            'dev-bind',
            'dev-bind-try',
            'ro-bind',
            'ro-bind-try',
        ]:
            src, target = self.parse_path(key, args)
            self.paths[target] = (key, src)
        elif key in ['tmpfs', 'dev', 'proc', 'mqueue', 'dir']:
            if len(args) != 1:
                raise RuleError(key, args)
            self.paths[args[0]] = (key, None)
        else:
            raise RuleError(key, args)

    def read_config_file(self, path):
        with open(path) as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    self.push_rule(*line.split(), cwd=path.parent)
                except RuleError as e:
                    raise SyntaxError(str(e), (path, lineno, 1, line)) from e

    def read_argv(self, argv):
        key = None
        args = []
        for i, token in enumerate(argv):
            if token == '-I':
                token = '--include'
            if token == '--':
                if key is not None:
                    self.push_rule(key, *args, cwd=Path.cwd())
                return argv[i + 1:]
            elif token in ['-h', '--help']:
                self.usage = True
            elif token == '--debug':
                self.debug = True
            elif token.startswith('--'):
                if key is not None:
                    self.push_rule(key, *args, cwd=Path.cwd())
                key = token.removeprefix('--')
                args = []
            else:
                args.append(token)
        raise ValueError('--')

    def build(self, bwrap_args):
        cmd = [
            'bwrap',
            '--die-with-parent',
            '--clearenv',
        ]
        if self.sync_fds is not None:
            cmd += ['--sync-fd', str(self.sync_fds[0])]
        if self.dbus_session:
            bus = expandvars(DBUS_SESSION_DEST, self.env)
            cmd += ['--setenv', 'DBUS_SESSION_BUS_ADDRESS', f'unix:path={bus}']
        for key in ['share-ipc', 'share-pid', 'share-net']:
            if not self.share.get(key):
                cmd.append(f'--un{key}')
        for key, value in self.env.items():
            if value is not None:
                cmd += ['--setenv', key, value]
        for target, typ, src in sorted(
            (expandvars(target, self.env), *value)
            for target, value in self.paths.items()
        ):
            if src is None:
                cmd += [f'--{typ}', target]
            else:
                src = expandvars(src, os.environ)
                src = os.path.realpath(src)
                cmd += [f'--{typ}', src, target]
        return cmd + bwrap_args

    def build_dbus_session(self):
        if not self.dbus_session:
            return None
        return DBusProxy(
            self.dbus_session,
            os.getenv('DBUS_SESSION_BUS_ADDRESS'),
            DBUS_SESSION_SRC,
            self.app_id,
            self.sync_fds[1],
        )

    def build_dbus_system(self):
        if not self.dbus_system:
            return None
        return DBusProxy(
            self.dbus_system,
            os.getenv(
                'DBUS_SYSTEM_BUS_ADDRESS',
                'unix:path=/run/dbus/system_bus_socket',
            ),
            DBUS_SYSTEM_SRC,
            self.app_id,
            self.sync_fds[1],
        )


if __name__ == '__main__':
    rules = RuleSet()
    try:
        tail = rules.read_argv(sys.argv)
    except SyntaxError as e:
        print(f'{e.filename}:{e.lineno}: {e.msg}', file=sys.stderr)
        sys.exit(1)
    except ValueError:
        print(USAGE)
        sys.exit(1)

    cmd = rules.build(tail)
    dbus_system = rules.build_dbus_system()
    dbus_session = rules.build_dbus_session()

    if rules.usage:
        print(USAGE)
    elif rules.debug:
        print(' '.join(cmd))
        if dbus_system:
            print(' '.join(dbus_system.cmd))
        if dbus_session:
            print(' '.join(dbus_session.cmd))
    else:
        if dbus_system:
            dbus_system.popen()
            os.read(rules.sync_fds[0], 8)
        if dbus_session:
            dbus_session.popen()
            os.read(rules.sync_fds[0], 8)
        os.execvp('/usr/bin/bwrap', cmd)
