import os
import sys
from os.path import expandvars
from pathlib import Path

USER_CONFIG = Path(os.getenv('XDG_CONFIG_HOME', '~/.config')) / 'xiwrap'
SYSTEM_CONFIG = Path('/etc') / 'xiwrap'

USAGE = """Usage: xiwrap [OPTION]... -- [BWRAP_OPTIONS]... CMD

Example: xiwrap --import bin --env TERM -- --chdir /tmp bash

The following options are available:

-h, --help              Print this message and exit
--debug                 Print the bwrap command instead of executing it.
--env VAR [VALUE]       Set an environment variable. If VALUE is not provided,
                        the value from the current environment is kept.
--bind DEST [SRC]       Bind mount the host path SRC on DEST. If SRC is not
                        provided, it is the same as DEST. Ignored if SRC does
                        not exist.
--ro-bind DEST [SRC]    Bind mount the host path SRC readonly on DEST. If SRC
                        is not provided, it is the same as DEST. Ignored if SRC
                        does not exist.
--proc DEST             Mount new procfs on DEST.
--dev DEST              Mount new dev on DEST.
--tmpfs DEST            Mount new tmpfs on DEST.
--share-net             Do not create new network namespace.
--import FILE           Load additional options from FILE. FILE can be an
                        absolute path or relative to the current directory,
                        $XDG_CONFIG_HOME/xiwrap/ or /etc/xiwrap/. FILE must
                        contain one option per line, without the leading --.
                        Empty lines or lines starting with # are ignored.
"""


class RuleError(ValueError):
    def __init__(self, key, args):
        rule = ' '.join([key, *args])
        super().__init__(f'Invalid rule: {rule}')


class RuleSet:
    def __init__(self):
        self.env = {}
        self.paths = {
            '/tmp': ('tmpfs', None),
            '/dev': ('dev', None),
            '/proc': ('proc', None),
        }
        self.dbus = set()  # TODO
        self.share_net = False
        self.debug = False
        self.usage = False

    def find_config_file(self, name, cwd):
        if name.startswith('/'):
            return Path(name)
        elif name.startswith('~'):
            return Path(name).expanduser()
        for base in [cwd, USER_CONFIG, SYSTEM_CONFIG]:
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

    def push_rule(self, key, args, *, cwd):
        if key == 'import':
            if len(args) != 1:
                raise RuleError(key, args)
            path = self.find_config_file(args[0], cwd)
            self.read_config_file(path)
        elif key == 'share-net':
            if len(args) != 0:
                raise RuleError(key, args)
            self.share_net = True
        elif key == 'env':
            var, value = self.parse_env(key, args)
            self.env[var] = value
        elif key in ['ro-bind', 'bind']:
            src, target = self.parse_path(key, args)
            self.paths[expandvars(target)] = (key, expandvars(src))
        elif key in ['tmpfs', 'dev', 'proc']:
            if len(args) != 1:
                raise RuleError(key, args)
            self.paths[expandvars(args[0])] = (key, None)
        else:
            raise RuleError(key, args)

    def read_config_file(self, path):
        with open(path) as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    parts = line.split()
                    self.push_rule(parts[0], parts[1:], cwd=path.parent)
                except RuleError as e:
                    raise SyntaxError(str(e), (path, lineno, 1, line)) from e

    def read_argv(self, argv):
        key = None
        args = []
        for i, token in enumerate(argv):
            if token == '--':
                if key is not None:
                    self.push_rule(key, args, cwd=Path.cwd())
                return argv[i + 1:]
            elif token in ['-h', '--help']:
                self.usage = True
            elif token == '--debug':
                self.debug = True
            elif token.startswith('--'):
                if key is not None:
                    self.push_rule(key, args, cwd=Path.cwd())
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
            '--unshare-pid',
        ]
        if not self.share_net:
            cmd += ['--unshare-net']
        for key, value in self.env.items():
            if value is not None:
                cmd += ['--setenv', key, value]
        for target, value in sorted(self.paths.items()):
            typ, src = value
            if src is None:
                cmd += [f'--{typ}', target]
            else:
                cmd += [f'--{typ}-try', src, target]
        return cmd + bwrap_args


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
    if rules.usage:
        print(USAGE)
    elif rules.debug:
        print(' '.join(cmd))
    else:
        os.execvp('/usr/bin/bwrap', cmd)
