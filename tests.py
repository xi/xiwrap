import unittest

from xiwrap import RuleSet
from xiwrap import patch_env

ENV = {
    'USER': 'foo',
    'HOME': '/home/foo'
}


class TestProcess(unittest.TestCase):
    def _test(self, rules, expected, skip=6):
        with patch_env(ENV):
            ruleset = RuleSet()
            for rule in rules:
                ruleset.push_rule(*rule)
            actual = ruleset.build()[skip:]
        self.assertEqual(actual, expected)

    def test_implicit_bind(self):
        self._test([
            ['bind', '/'],
        ], [
            '--bind', '/', '/',
        ])

    def test_implicit_setenv(self):
        self._test([
            ['setenv', 'HOME'],
        ], [
            '--setenv', 'HOME', '/home/foo',
        ])

    def test_overwrite_bind(self):
        self._test([
            ['bind', '/', '/'],
            ['bind', '/tmp', '/'],
        ], [
            '--bind', '/tmp', '/',
        ])

    def test_overwrite_bind_type(self):
        self._test([
            ['bind', '/', '/'],
            ['tmpfs', '/'],
        ], [
            '--tmpfs', '/',
        ])

    def test_overwrite_env(self):
        self._test([
            ['setenv', 'HOME', '/home/foo'],
            ['setenv', 'HOME', '/home/bar'],
        ], [
            '--setenv', 'HOME', '/home/bar',
        ])

    def test_reorder_types(self):
        self._test([
            ['bind', '/foo', '/etc'],
            ['setenv', 'HOME', '/home/bar'],
        ], [
            '--setenv', 'HOME', '/home/bar',
            '--bind', '/foo', '/etc',
        ])

    def test_reorder_bind(self):
        self._test([
            ['bind', '/foo', '/etc'],
            ['bind', '/', '/'],
        ], [
            '--bind', '/', '/',
            '--bind', '/foo', '/etc',
        ])

    def test_expand_in_target(self):
        self._test([
            ['setenv', 'HOME', '/foo'],
            ['bind', '$HOME'],
        ], [
            '--setenv', 'HOME', '/foo',
            '--bind', '/home/foo', '/foo',
        ])

    def test_expand_implicit_xdg_dirs(self):
        self._test([
            ['setenv', 'HOME', '/home/bar'],
            ['bind', '$XDG_CONFIG_HOME/test'],
        ], [
            '--setenv', 'HOME', '/home/bar',
            '--bind', '/home/foo/.config/test', '/home/bar/.config/test',
        ])

    def test_omit_redundant_bind(self):
        self._test([
            ['bind', '/'],
            ['bind', '/usr'],
        ], [
            '--bind', '/', '/',
        ])

    def test_no_omit_common_prefix(self):
        self._test([
            ['bind', '/lib'],
            ['bind', '/lib32'],
        ], [
            '--bind', '/lib', '/lib',
            '--bind', '/lib32', '/lib32',
        ])
