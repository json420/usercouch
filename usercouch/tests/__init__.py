# usercouch: Starts per-user CouchDB instances for fun and unit testing
# Copyright (C) 2011 Novacut Inc
#
# This file is part of `usercouch`.
#
# `usercouch` is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# `usercouch` is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with `usercouch`.  If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#   Jason Gerard DeRose <jderose@novacut.com>

"""
Unit tests for `usercouch` package.
"""

from unittest import TestCase
import socket
import os
from os import path
import io
import tempfile
import shutil
import subprocess
import time
from copy import deepcopy
from base64 import b32decode
from http.client import HTTPConnection
from random import SystemRandom

import usercouch


random = SystemRandom()
B32ALPHABET = frozenset('234567ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def test_port():
    return random.randint(1001, 50000)


class TempDir(object):
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix='unittest.')

    def __del__(self):
        self.rmtree()

    def rmtree(self):
        if self.dir is not None:
            shutil.rmtree(self.dir)
            self.dir = None

    def join(self, *parts):
        return path.join(self.dir, *parts)

    def makedirs(self, *parts):
        d = self.join(*parts)
        if not path.exists(d):
            os.makedirs(d)
        assert path.isdir(d), d
        return d

    def touch(self, *parts):
        self.makedirs(*parts[:-1])
        f = self.join(*parts)
        open(f, 'wb').close()
        return f

    def write(self, data, *parts):
        self.makedirs(*parts[:-1])
        f = self.join(*parts)
        open(f, 'wb').write(data)
        return f

    def copy(self, src, *parts):
        self.makedirs(*parts[:-1])
        dst = self.join(*parts)
        shutil.copy(src, dst)
        return dst


class TestFunctions(TestCase):
    def test_random_b32(self):
        _id = usercouch.random_b32()
        self.assertIsInstance(_id, str)
        self.assertEqual(len(_id), 24)
        self.assertTrue(set(_id).issubset(B32ALPHABET))
        b = b32decode(_id.encode('ascii'))
        self.assertIsInstance(b, bytes)
        self.assertEqual(len(b) * 8, 120)
        self.assertNotEqual(usercouch.random_b32(), _id)

    def test_random_oauth(self):
        kw = usercouch.random_oauth()
        self.assertIsInstance(kw, dict)
        self.assertEqual(
            set(kw),
            set(['consumer_key', 'consumer_secret', 'token', 'token_secret'])
        )
        for value in kw.values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(set(value).issubset(B32ALPHABET))

        new = usercouch.random_oauth()
        self.assertNotEqual(new, kw)
        for key in ['consumer_key', 'consumer_secret', 'token', 'token_secret']:
            self.assertNotEqual(new[key], kw[key])

    def test_random_salt(self):
        salt = usercouch.random_salt()
        self.assertIsInstance(salt, str)
        self.assertEqual(len(salt), 32)
        self.assertEqual(len(bytes.fromhex(salt)), 16)
        self.assertNotEqual(usercouch.random_salt(), salt)

    def test_couch_hashed(self):
        salt = 'a' * 32
        self.assertEqual(
            usercouch.couch_hashed('very secret', salt),
            '-hashed-f3051dd7e647cdb7fd1d56c52fcd73724895417b,' + salt
        )
        salt = '9' * 32
        self.assertEqual(
            usercouch.couch_hashed('very secret', salt),
            '-hashed-791a7d0f893bfbf6311d36081f797fe166cee072,' + salt
        )

    def test_build_config(self):
        overrides = {
            'address': usercouch.random_b32(),
            'loglevel': usercouch.random_b32(),
        }

        # Test with bad auth
        with self.assertRaises(ValueError) as cm:
            usercouch.build_config('magic')
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")
        with self.assertRaises(ValueError) as cm:
            usercouch.build_config('magic', deepcopy(overrides))
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")

        # auth='open'
        config = usercouch.build_config('open')
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set(['address', 'loglevel'])
        )
        self.assertEqual(config['address'], '127.0.0.1')
        self.assertEqual(config['loglevel'], 'notice')

        # auth='open' with overrides
        self.assertEqual(
            usercouch.build_config('open', deepcopy(overrides)),
            {
                'address': overrides['address'],
                'loglevel': overrides['loglevel'],
            }
        )

        # auth='basic'
        config = usercouch.build_config('basic')
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set(['address', 'loglevel', 'username', 'password', 'salt'])
        )
        self.assertEqual(config['address'], '127.0.0.1')
        self.assertEqual(config['loglevel'], 'notice')

        # auth='basic' with overrides
        config = usercouch.build_config('basic', deepcopy(overrides))
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set(['address', 'loglevel', 'username', 'password', 'salt'])
        )
        self.assertEqual(config['address'], overrides['address'])
        self.assertEqual(config['loglevel'], overrides['loglevel'])
        o2 = {
            'address': usercouch.random_b32(),
            'loglevel': usercouch.random_b32(),
            'username': usercouch.random_b32(),
            'password': usercouch.random_b32(),
            'salt': usercouch.random_salt(),
        }
        self.assertEqual(
            usercouch.build_config('basic', deepcopy(o2)),
            {
                'address': o2['address'],
                'loglevel': o2['loglevel'],
                'username': o2['username'],
                'password': o2['password'],
                'salt': o2['salt'],
            }
        )

        # auth='oauth'
        config = usercouch.build_config('oauth')
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set(['address', 'loglevel', 'username', 'password', 'salt', 'oauth'])
        )
        self.assertEqual(config['address'], '127.0.0.1')
        self.assertEqual(config['loglevel'], 'notice')
        self.assertIsInstance(config['oauth'], dict)
        self.assertEqual(set(config['oauth']),
            set(['token', 'token_secret', 'consumer_key', 'consumer_secret'])
        )

        # auth='oauth' with overrides
        config = usercouch.build_config('oauth', deepcopy(overrides))
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set(['address', 'loglevel', 'username', 'password', 'salt', 'oauth'])
        )
        self.assertEqual(config['address'], overrides['address'])
        self.assertEqual(config['loglevel'], overrides['loglevel'])
        self.assertIsInstance(config['oauth'], dict)
        self.assertEqual(set(config['oauth']),
            set(['token', 'token_secret', 'consumer_key', 'consumer_secret'])
        )
        o3 = {
            'address': usercouch.random_b32(),
            'loglevel': usercouch.random_b32(),
            'username': usercouch.random_b32(),
            'password': usercouch.random_b32(),
            'salt': usercouch.random_salt(),
            'oauth': usercouch.random_oauth(),
        }
        self.assertEqual(
            usercouch.build_config('basic', deepcopy(o3)),
            {
                'address': o3['address'],
                'loglevel': o3['loglevel'],
                'username': o3['username'],
                'password': o3['password'],
                'salt': o3['salt'],
                'oauth': o3['oauth'],
            }
        )

    def test_build_env(self):
        config = {
            'username': usercouch.random_b32(),
            'password': usercouch.random_b32(),
            'oauth': usercouch.random_oauth(),
        }
        port = test_port()

        # Test with bad auth
        with self.assertRaises(ValueError) as cm:
            usercouch.build_env('magic', deepcopy(config), port)
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")

        # auth='open'
        self.assertEqual(
            usercouch.build_env('open', deepcopy(config), port),
            {
                'port': port,
                'url': 'http://localhost:{}/'.format(port),
            }
        )

        # auth='basic'
        self.assertEqual(
            usercouch.build_env('basic', deepcopy(config), port),
            {
                'port': port,
                'url': 'http://localhost:{}/'.format(port),
                'basic': {
                    'username': config['username'],
                    'password': config['password'],
                },
            }
        )

        # auth='oauth'
        self.assertEqual(
            usercouch.build_env('oauth', deepcopy(config), port),
            {
                'port': port,
                'url': 'http://localhost:{}/'.format(port),
                'basic': {
                    'username': config['username'],
                    'password': config['password'],
                },
                'oauth': config['oauth'],
            }
        )

    def test_build_template_kw(self):
        config = {
            'address': usercouch.random_b32(),
            'loglevel': usercouch.random_b32(),
            'username': usercouch.random_b32(),
            'password': usercouch.random_b32(),
            'salt': usercouch.random_salt(),
            'oauth': usercouch.random_oauth(),
        }
        port = test_port()
        tmp = TempDir()
        paths = usercouch.Paths(tmp.dir)

        # Test with bad auth
        with self.assertRaises(ValueError) as cm:
            usercouch.build_template_kw('magic', deepcopy(config), port, paths)
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")

        # auth='open'
        self.assertEqual(
            usercouch.build_template_kw('open', deepcopy(config), port, paths),
            {
                'address': config['address'],
                'loglevel': config['loglevel'],
                'port': port,
                'databases': paths.databases,
                'views': paths.views,
                'logfile': paths.logfile,
            }
        )

        # auth='basic'
        self.assertEqual(
            usercouch.build_template_kw('basic', deepcopy(config), port, paths),
            {
                'address': config['address'],
                'loglevel': config['loglevel'],
                'port': port,
                'databases': paths.databases,
                'views': paths.views,
                'logfile': paths.logfile,
                'username': config['username'],
                'hashed': usercouch.couch_hashed(
                    config['password'], config['salt']
                ),
            }
        )

        # auth='oauth'
        self.assertEqual(
            usercouch.build_template_kw('oauth', deepcopy(config), port, paths),
            {
                'address': config['address'],
                'loglevel': config['loglevel'],
                'port': port,
                'databases': paths.databases,
                'views': paths.views,
                'logfile': paths.logfile,
                'username': config['username'],
                'hashed': usercouch.couch_hashed(
                    config['password'], config['salt']
                ),
                'token': config['oauth']['token'],
                'token_secret': config['oauth']['token_secret'],
                'consumer_key': config['oauth']['consumer_key'],
                'consumer_secret': config['oauth']['consumer_secret'],
            }
        )

    def test_build_session_ini(self):
        # Test with bad auth
        with self.assertRaises(ValueError) as cm:
            usercouch.build_session_ini('magic', {})
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")

        # Test with auth='open'
        keys = ('address', 'port', 'databases', 'views', 'logfile', 'loglevel')
        kw = dict(
            (key, usercouch.random_b32())
            for key in keys
        )
        self.assertEqual(
            usercouch.build_session_ini('open', deepcopy(kw)),
            usercouch.OPEN.format(**kw)
        )
        for key in keys:
            bad = deepcopy(kw)
            del bad[key]
            with self.assertRaises(KeyError) as cm:
                usercouch.build_session_ini('open', bad)
            self.assertEqual(str(cm.exception), repr(key))

        # Test with auth='basic'
        keys = (
            'address', 'port', 'databases', 'views', 'logfile', 'loglevel',
            'username', 'hashed',
        )
        kw = dict(
            (key, usercouch.random_b32())
            for key in keys
        )
        self.assertEqual(
            usercouch.build_session_ini('basic', deepcopy(kw)),
            usercouch.BASIC.format(**kw)
        )
        for key in keys:
            bad = deepcopy(kw)
            del bad[key]
            with self.assertRaises(KeyError) as cm:
                usercouch.build_session_ini('basic', bad)
            self.assertEqual(str(cm.exception), repr(key))

        # Test with auth='oauth'
        keys = (
            'address', 'port', 'databases', 'views', 'logfile', 'loglevel',
            'username', 'hashed',
            'token', 'token_secret', 'consumer_key', 'consumer_secret',
        )
        kw = dict(
            (key, usercouch.random_b32())
            for key in keys
        )
        self.assertEqual(
            usercouch.build_session_ini('oauth', deepcopy(kw)),
            usercouch.OAUTH.format(**kw)
        )
        for key in keys:
            bad = deepcopy(kw)
            del bad[key]
            with self.assertRaises(KeyError) as cm:
                usercouch.build_session_ini('oauth', bad)
            self.assertEqual(str(cm.exception), repr(key))

    def test_bind_random_port(self):
        (sock, port) = usercouch.bind_random_port('127.0.0.1')
        self.assertIsInstance(sock, socket.socket)
        self.assertIsInstance(port, int)
        self.assertEqual(sock.getsockname(), ('127.0.0.1', port))
        self.assertNotEqual(port,
            usercouch.bind_random_port('127.0.0.1')[1]
        )

        (sock, port) = usercouch.bind_random_port('0.0.0.0')
        self.assertIsInstance(sock, socket.socket)
        self.assertIsInstance(port, int)
        self.assertEqual(sock.getsockname(), ('0.0.0.0', port))
        self.assertNotEqual(port,
            usercouch.bind_random_port('0.0.0.0')[1]
        )

    def test_get_cmd(self):
        tmp = TempDir()
        ini = tmp.join('session.ini')
        self.assertEqual(
            usercouch.get_cmd(ini),
            [
                '/usr/bin/couchdb',
                '-n',
                '-a', '/etc/couchdb/default.ini',
                '-a', usercouch.USERCOUCH_INI,
                '-a', ini,
            ]
        )


class TestPathFunctions(TestCase):
    def test_mkdir(self):
        tmp = TempDir()

        # Test that os.makedirs() is not used:
        basedir = tmp.join('foo')
        d = tmp.join('foo', 'bar')
        with self.assertRaises(OSError) as cm:
            usercouch.mkdir(basedir, 'bar')
        self.assertEqual(
            str(cm.exception),
            '[Errno 2] No such file or directory: {!r}'.format(d)
        )
        self.assertFalse(path.exists(basedir))
        self.assertFalse(path.exists(d))

        # Test when dir does not exist
        d = tmp.join('foo')
        self.assertFalse(path.exists(d))
        self.assertEqual(usercouch.mkdir(tmp.dir, 'foo'), d)
        self.assertTrue(path.isdir(d))

        # Test when dir exists:
        self.assertEqual(usercouch.mkdir(tmp.dir, 'foo'), d)
        self.assertTrue(path.isdir(d))

        # Test when dir exists and is a file:
        d = tmp.touch('bar')
        with self.assertRaises(ValueError) as cm:
            usercouch.mkdir(tmp.dir, 'bar')
        self.assertEqual(str(cm.exception), 'not a directory: {!r}'.format(d))

        # Test when dir exists and is a symlink to a dir:
        target = tmp.makedirs('target')
        link = tmp.join('link')
        os.symlink(target, link)
        self.assertTrue(path.isdir(link))
        self.assertTrue(path.islink(link))
        with self.assertRaises(ValueError) as cm:
            usercouch.mkdir(tmp.dir, 'link')
        self.assertEqual(str(cm.exception), 'not a directory: {!r}'.format(link))

    def test_logfile(self):
        tmp = TempDir()
        self.assertEqual(
            usercouch.logfile(tmp.dir, 'foo'),
            tmp.join('foo.log')
        )
        self.assertEqual(os.listdir(tmp.dir), [])
        tmp.touch('bar.log')
        self.assertEqual(
            usercouch.logfile(tmp.dir, 'bar'),
            tmp.join('bar.log')
        )
        self.assertTrue(path.isfile(tmp.join('bar.log.previous')))
        self.assertEqual(os.listdir(tmp.dir), ['bar.log.previous'])


class TestPaths(TestCase):
    def test_init(self):
        tmp = TempDir()
        paths = usercouch.Paths(tmp.dir)
        self.assertEqual(paths.ini, tmp.join('session.ini'))
        self.assertEqual(paths.databases, tmp.join('databases'))
        self.assertEqual(paths.views, tmp.join('views'))
        self.assertEqual(paths.bzr, tmp.join('bzr'))
        self.assertEqual(paths.log, tmp.join('log'))
        self.assertEqual(paths.logfile, tmp.join('log', 'couchdb.log'))
        self.assertTrue(path.isdir(paths.databases))
        self.assertTrue(path.isdir(paths.views))
        self.assertTrue(path.isdir(paths.bzr))
        self.assertTrue(path.isdir(paths.log))
        self.assertEqual(
            sorted(os.listdir(tmp.dir)),
            ['bzr', 'databases', 'log', 'views']
        )
        self.assertEqual(os.listdir(tmp.join('log')), [])

        tmp.touch('log', 'couchdb.log')
        paths = usercouch.Paths(tmp.dir)
        self.assertEqual(paths.ini, tmp.join('session.ini'))
        self.assertEqual(paths.databases, tmp.join('databases'))
        self.assertEqual(paths.views, tmp.join('views'))
        self.assertEqual(paths.bzr, tmp.join('bzr'))
        self.assertEqual(paths.log, tmp.join('log'))
        self.assertEqual(paths.logfile, tmp.join('log', 'couchdb.log'))
        self.assertTrue(path.isdir(paths.databases))
        self.assertTrue(path.isdir(paths.views))
        self.assertTrue(path.isdir(paths.bzr))
        self.assertTrue(path.isdir(paths.log))
        self.assertEqual(
            sorted(os.listdir(tmp.dir)),
            ['bzr', 'databases', 'log', 'views']
        )
        self.assertEqual(
            os.listdir(tmp.join('log')),
            ['couchdb.log.previous']
        )
        self.assertTrue(path.isfile(tmp.join('log', 'couchdb.log.previous')))


class TestHTTPError(TestCase):
    def test_init(self):
        class response:
            status = 747
            reason = 'Really Big'

        e = usercouch.HTTPError(response, 'FLY', '/somewhere/awesome')
        self.assertIs(e.response, response)
        self.assertEqual(e.method, 'FLY')
        self.assertEqual(e.path, '/somewhere/awesome')
        self.assertEqual(str(e),
            '747 Really Big: FLY /somewhere/awesome'
        )


class TestHTTPFunctions(TestCase):
    def test_basic_auth_header(self):
        basic = {'username': 'Aladdin', 'password': 'open sesame'}
        self.assertEqual(
            usercouch.basic_auth_header(basic),
            {'Authorization': 'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=='}
        )

    def test_get_conn(self):
        tmp = TempDir()
        url = 'http://localhost:5634/'
        env = {'url': url}
        conn = usercouch.get_conn(env)
        self.assertIsInstance(conn, HTTPConnection)

    def test_get_headers(self):
        env = {}
        self.assertEqual(usercouch.get_headers(env),
            {'Accept': 'application/json'}
        )

        env = {'basic': {'username': 'Aladdin', 'password': 'open sesame'}}
        self.assertEqual(usercouch.get_headers(env),
            {
                'Accept': 'application/json',
                'Authorization': 'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==',
            }
        )


class TestLockError(TestCase):
    def test_init(self):
        lock = usercouch.LockError('/tmp/foo/lockfile')
        self.assertEqual(lock.lockfile, '/tmp/foo/lockfile')
        self.assertEqual(
            str(lock),
            "cannot acquire exclusive lock on '/tmp/foo/lockfile'"
        )

        tmp = TempDir()
        lockfile = tmp.join('lockfile')
        lock = usercouch.LockError(lockfile)
        self.assertEqual(lock.lockfile, lockfile)
        self.assertEqual(
            str(lock),
            'cannot acquire exclusive lock on {!r}'.format(lockfile)
        )


class TestUserCouch(TestCase):
    def test_init(self):
        tmp = TempDir()

        # basedir doesn't exists
        nope = tmp.join('nope')
        with self.assertRaises(ValueError) as cm:
            usercouch.UserCouch(nope)
        self.assertEqual(
            str(cm.exception),
            'UserCouch.basedir not a directory: {!r}'.format(nope)
        )

        # basedir is a file
        bad = tmp.touch('bad')
        with self.assertRaises(ValueError) as cm:
            usercouch.UserCouch(bad)
        self.assertEqual(
            str(cm.exception),
            'UserCouch.basedir not a directory: {!r}'.format(bad)
        )

        # When it's all good
        good = tmp.makedirs('good')
        uc = usercouch.UserCouch(good)
        self.assertIsNone(uc.couchdb)
        self.assertEqual(uc.basedir, good)
        self.assertIsInstance(uc.lockfile, io.BufferedWriter)
        self.assertEqual(uc.lockfile.name, path.join(good, 'lockfile'))
        self.assertIsInstance(uc.paths, usercouch.Paths)
        self.assertEqual(uc.paths.ini, tmp.join('good', 'session.ini'))
        self.assertEqual(uc.cmd, usercouch.get_cmd(uc.paths.ini))

    def test_lockfile(self):
        tmp = TempDir()
        uc1 = usercouch.UserCouch(tmp.dir)

        # Make sure lockfile is working:
        with self.assertRaises(usercouch.LockError) as cm:
            uc2 = usercouch.UserCouch(tmp.dir)
        self.assertEqual(cm.exception.lockfile, tmp.join('lockfile'))

        # Dereferenc uc1, make sure lock gets released
        uc1 = None
        uc2 = usercouch.UserCouch(tmp.dir)

    def test_repr(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        self.assertEqual(
            repr(uc),
            'UserCouch({!r})'.format(tmp.dir)
        )

    def test_bootstrap_open(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        self.assertFalse(path.exists(uc.paths.ini))
        env = uc.bootstrap('open')
        self.assertTrue(path.isfile(uc.paths.ini))
        self.assertEqual(uc._headers, {'Accept': 'application/json'})

        # check env
        self.assertIsInstance(env, dict)
        self.assertEqual(set(env), set(['port', 'url']))
        port = env['port']
        self.assertIsInstance(port, int)
        self.assertGreater(port, 1024)
        self.assertEqual(env['url'], 'http://localhost:{}/'.format(port))

        # check UserCouch.couchdb, make sure UserCouch.start() was called
        self.assertIsInstance(uc.couchdb, subprocess.Popen)
        self.assertIsNone(uc.couchdb.returncode)

        # check that Exception is raised if you call bootstrap() more than once
        with self.assertRaises(Exception) as cm:
            uc.bootstrap()
        self.assertEqual(
            str(cm.exception),
            'UserCouch.bootstrap() already called'
        )

    def test_bootstrap_basic(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        self.assertFalse(path.exists(uc.paths.ini))
        env = uc.bootstrap()
        self.assertTrue(path.isfile(uc.paths.ini))
        self.assertEqual(uc._headers, usercouch.get_headers(env))
        self.assertEqual(set(uc._headers), set(['Accept', 'Authorization']))

        # check env
        self.assertIsInstance(env, dict)
        self.assertEqual(set(env), set(['port', 'url', 'basic']))
        port = env['port']
        self.assertIsInstance(port, int)
        self.assertGreater(port, 1024)
        self.assertEqual(env['url'], 'http://localhost:{}/'.format(port))
        self.assertIsInstance(env['basic'], dict)
        self.assertEqual(
            set(env['basic']),
            set(['username', 'password'])
        )
        for value in env['basic'].values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(set(value).issubset(B32ALPHABET))

        # check UserCouch.couchdb, make sure UserCouch.start() was called
        self.assertIsInstance(uc.couchdb, subprocess.Popen)
        self.assertIsNone(uc.couchdb.returncode)

        # check that Exception is raised if you call bootstrap() more than once
        with self.assertRaises(Exception) as cm:
            uc.bootstrap()
        self.assertEqual(
            str(cm.exception),
            'UserCouch.bootstrap() already called'
        )

    def test_bootstrap_oauth(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        self.assertFalse(path.exists(uc.paths.ini))
        env = uc.bootstrap(auth='oauth')
        self.assertTrue(path.isfile(uc.paths.ini))
        self.assertEqual(uc._headers, usercouch.get_headers(env))
        self.assertEqual(set(uc._headers), set(['Accept', 'Authorization']))

        # check env
        self.assertIsInstance(env, dict)
        self.assertEqual(set(env), set(['port', 'url', 'basic', 'oauth']))
        port = env['port']
        self.assertIsInstance(port, int)
        self.assertGreater(port, 1024)
        self.assertEqual(env['url'], 'http://localhost:{}/'.format(port))
        self.assertIsInstance(env['basic'], dict)
        self.assertEqual(
            set(env['basic']),
            set(['username', 'password'])
        )
        for value in env['basic'].values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(set(value).issubset(B32ALPHABET))
        self.assertIsInstance(env['oauth'], dict)
        self.assertEqual(
            set(env['oauth']),
            set(['consumer_key', 'consumer_secret', 'token', 'token_secret'])
        )
        for value in env['oauth'].values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(set(value).issubset(B32ALPHABET))

        # check UserCouch.couchdb, make sure UserCouch.start() was called
        self.assertIsInstance(uc.couchdb, subprocess.Popen)
        self.assertIsNone(uc.couchdb.returncode)

        # check that Exception is raised if you call bootstrap() more than once
        with self.assertRaises(Exception) as cm:
            uc.bootstrap()
        self.assertEqual(
            str(cm.exception),
            'UserCouch.bootstrap() already called'
        )

    def test_bootstrap_override_basic(self):
        overrides = {
            'loglevel': 'debug',
            'address': '0.0.0.0',
            'username': usercouch.random_b32(),
            'password': usercouch.random_b32(),
            'salt': usercouch.random_salt(),
        }
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        env = uc.bootstrap('basic', deepcopy(overrides))
        self.assertIsInstance(env, dict)
        self.assertEqual(set(env),
            set(['port', 'url', 'basic'])
        )
        self.assertIsInstance(env['port'], int)
        self.assertEqual(env['url'],
            'http://localhost:{}/'.format(env['port'])
        )
        self.assertEqual(env['basic'],
            dict((k, overrides[k]) for k in ('username', 'password'))
        )
        kw = {
            'address': overrides['address'],
            'port': env['port'],
            'databases': uc.paths.databases,
            'views': uc.paths.views,
            'logfile': uc.paths.logfile,
            'loglevel': overrides['loglevel'],

            'username': overrides['username'],
            'hashed': usercouch.couch_hashed(
                overrides['password'], overrides['salt']
            ),
        }
        self.assertEqual(
            open(uc.paths.ini, 'r').read(),
            usercouch.BASIC.format(**kw)
        )

    def test_bootstrap_override_oauth(self):
        overrides = {
            'loglevel': 'debug',
            'address': '0.0.0.0',
            'username': usercouch.random_b32(),
            'password': usercouch.random_b32(),
            'salt': usercouch.random_salt(),
            'oauth': usercouch.random_oauth(),
        }
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        env = uc.bootstrap('oauth', deepcopy(overrides))
        self.assertIsInstance(env, dict)
        self.assertEqual(set(env),
            set(['port', 'url', 'basic', 'oauth'])
        )
        self.assertIsInstance(env['port'], int)
        self.assertEqual(env['url'],
            'http://localhost:{}/'.format(env['port'])
        )
        self.assertEqual(env['basic'],
            dict((k, overrides[k]) for k in ('username', 'password'))
        )
        self.assertEqual(env['oauth'], overrides['oauth'])
        kw = {
            'address': overrides['address'],
            'port': env['port'],
            'databases': uc.paths.databases,
            'views': uc.paths.views,
            'logfile': uc.paths.logfile,
            'loglevel': overrides['loglevel'],

            'username': overrides['username'],
            'hashed': usercouch.couch_hashed(
                overrides['password'], overrides['salt']
            ),

            'token': overrides['oauth']['token'],
            'token_secret': overrides['oauth']['token_secret'],
            'consumer_key': overrides['oauth']['consumer_key'],
            'consumer_secret': overrides['oauth']['consumer_secret'],
        }
        self.assertEqual(
            open(uc.paths.ini, 'r').read(),
            usercouch.OAUTH.format(**kw)
        )

    def test_start(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)

        with self.assertRaises(Exception) as cm:
            uc.start()
        self.assertEqual(
            str(cm.exception),
            'Must call UserCouch.bootstrap() before UserCouch.start()'
        )

        uc.bootstrap()
        self.assertEqual(uc._welcome,
            {'couchdb': 'Welcome', 'version': '1.2.0'}
        )
        self.assertFalse(uc.start())
        self.assertTrue(uc.kill())
        self.assertIsNone(uc.couchdb)
        self.assertTrue(uc.start())
        self.assertIsInstance(uc.couchdb, subprocess.Popen)

    def test_kill(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        self.assertFalse(uc.kill())
        uc.bootstrap()
        self.assertIsInstance(uc.couchdb, subprocess.Popen)
        self.assertTrue(uc.kill())
        self.assertIsNone(uc.couchdb)

    def test_isalive(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)

        with self.assertRaises(Exception) as cm:
            uc.isalive()
        self.assertEqual(
            str(cm.exception),
            'Must call UserCouch.bootstrap() before UserCouch.isalive()'
        )

        uc.bootstrap()
        self.assertTrue(uc.isalive())
        uc.couchdb.terminate()
        self.assertFalse(uc.isalive())

    def test_check(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)

        with self.assertRaises(Exception) as cm:
            uc.check()
        self.assertEqual(
            str(cm.exception),
            'Must call UserCouch.bootstrap() before UserCouch.check()'
        )

        uc.bootstrap()
        self.assertFalse(uc.check())
        uc.couchdb.terminate()
        self.assertTrue(uc.check())

    def test_crash(self):
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        self.assertFalse(uc.crash())
        uc.bootstrap()
        self.assertTrue(uc.isalive())
        self.assertTrue(uc.crash())
        self.assertFalse(uc.isalive())
        uc.couchdb.wait()
        uc.couchdb = None
        self.assertFalse(uc.crash())
