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

from dbase32 import random_id, isdb32

from usercouch import sslhelpers
import usercouch


random = SystemRandom()


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


class TestConstants(TestCase):
    def test_version(self):
        self.assertIsInstance(usercouch.__version__, str)
        (year, month, rev) = usercouch.__version__.split('.')
        y = int(year)
        self.assertTrue(y >= 13)
        self.assertEqual(str(y), year)
        m = int(month)
        self.assertTrue(1 <= m <= 12)
        self.assertEqual('{:02d}'.format(m), month)
        r = int(rev)
        self.assertTrue(r >= 0)
        self.assertEqual(str(r), rev)


class TestFunctions(TestCase):
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
            self.assertTrue(isdb32(value))

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

    def test_check_ssl_config(self):
        tmp = TempDir()
        ca = tmp.touch('ca.pem')
        cert = tmp.touch('cert.pem')
        key = tmp.touch('key.pem')
        nope = tmp.join('nope.pem')
        good = {
            'cert_file': cert,
            'key_file': key,
            'ca_file': ca,
        }
        required = ('cert_file', 'key_file')
        possible = required + ('ca_file',)

        # Test when it's all good:
        self.assertIsNone(usercouch.check_ssl_config(good))
        also_good = deepcopy(good)
        del also_good['ca_file']
        self.assertIsNone(usercouch.check_ssl_config(also_good))

        # Test when a required key is missing:
        for key in required:
            bad = deepcopy(good)
            del bad[key]
            with self.assertRaises(ValueError) as cm:
                usercouch.check_ssl_config(bad)
            self.assertEqual(
                str(cm.exception),
                "config['ssl'][{!r}] is required, but missing".format(key)
            )

        # Test when a possible key isn't a file:
        for key in possible:
            bad = deepcopy(good)
            bad[key] = nope
            with self.assertRaises(ValueError) as cm:
                usercouch.check_ssl_config(bad)
            self.assertEqual(
                str(cm.exception),
                "config['ssl'][{!r}] not a file: {!r}".format(key, nope)
            )

        # Test when ssl_env is wrong type:
        with self.assertRaises(TypeError) as cm:
            usercouch.check_ssl_config('hello')
        self.assertEqual(
            str(cm.exception),
            "config['ssl'] must be a <class 'dict'>; got a <class 'str'>: 'hello'"
        )

        # Test when an empty ssl_env dict:
        with self.assertRaises(ValueError) as cm:
            usercouch.check_ssl_config({})
        self.assertEqual(
            str(cm.exception),
            "config['ssl']['cert_file'] is required, but missing"
        )

    def test_check_replicator_config(self):
        tmp = TempDir()
        ca_file = tmp.touch('ca.pem')
        cert_file = tmp.touch('cert.pem')
        key_file = tmp.touch('key.pem')
        nope = tmp.join('nope.pem')

        # Test with config['replicator'] is wrong type
        with self.assertRaises(TypeError) as cm:
            usercouch.check_replicator_config('world')
        self.assertEqual(
            str(cm.exception),
            "config['replicator'] must be a <class 'dict'>; got a <class 'str'>: 'world'"
        )

        # Test when ca_file is missing
        with self.assertRaises(ValueError) as cm:
            usercouch.check_replicator_config({})
        self.assertEqual(
            str(cm.exception),
            "config['replicator']['ca_file'] is required, but missing"
        )

        # Test when ca_file is not a file
        with self.assertRaises(ValueError) as cm:
            usercouch.check_replicator_config({'ca_file': nope})
        self.assertEqual(
            str(cm.exception),
            "config['replicator']['ca_file'] not a file: {!r}".format(nope)
        )

        # Test when max_depth isn't an int
        cfg = {'ca_file': ca_file, 'max_depth': 2.0}
        with self.assertRaises(TypeError) as cm:
            usercouch.check_replicator_config(cfg)
        self.assertEqual(
            str(cm.exception),
            "config['replicator']['max_depth'] not an int: 2.0"
        )

        # Test when max_depth is less than zero
        cfg = {'ca_file': ca_file, 'max_depth': -1}
        with self.assertRaises(ValueError) as cm:
            usercouch.check_replicator_config(cfg)
        self.assertEqual(
            str(cm.exception),
            "config['replicator']['max_depth'] < 0: -1"
        )

        # Test when it's all good
        cfg = {'ca_file': ca_file}
        self.assertIsNone(
            usercouch.check_replicator_config(cfg)
        )
        self.assertEqual(cfg,
            {'ca_file': ca_file, 'max_depth': 1}
        )
        cfg = {'ca_file': ca_file, 'max_depth': 2}
        self.assertIsNone(
            usercouch.check_replicator_config(cfg)
        )
        self.assertEqual(cfg,
            {'ca_file': ca_file, 'max_depth': 2}
        )

        # Test when cert_file is present, but key_file is missing
        cfg = {'ca_file': ca_file, 'cert_file': 'foo'}
        with self.assertRaises(ValueError) as cm:
            usercouch.check_replicator_config(cfg)
        self.assertEqual(
            str(cm.exception),
            "config['replicator']['key_file'] is required, but missing"
        )

        # Test when cert_file isn't a file
        cfg = {'ca_file': ca_file, 'cert_file': nope, 'key_file': 'bar'}
        with self.assertRaises(ValueError) as cm:
            usercouch.check_replicator_config(cfg)
        self.assertEqual(
            str(cm.exception),
            "config['replicator']['cert_file'] not a file: {!r}".format(nope)
        )

        # Test when key_file isn't a file
        cfg = {'ca_file': ca_file, 'cert_file': cert_file, 'key_file': nope}
        with self.assertRaises(ValueError) as cm:
            usercouch.check_replicator_config(cfg)
        self.assertEqual(
            str(cm.exception),
            "config['replicator']['key_file'] not a file: {!r}".format(nope)
        )

        # Test when it's all good, including cert_file and key_file
        cfg = {'ca_file': ca_file, 'cert_file': cert_file, 'key_file': key_file}
        self.assertIsNone(
            usercouch.check_replicator_config(cfg)
        )
        self.assertEqual(cfg,
            {
                'ca_file': ca_file,
                'max_depth': 1,
                'cert_file': cert_file,
                'key_file': key_file,
            }
        )
        cfg = {
            'ca_file': ca_file, 'max_depth': 0,
            'cert_file': cert_file, 'key_file': key_file,
        }
        self.assertIsNone(
            usercouch.check_replicator_config(cfg)
        )
        self.assertEqual(cfg,
            {
                'ca_file': ca_file,
                'max_depth': 0,
                'cert_file': cert_file,
                'key_file': key_file,
            }
        )

    def test_build_config(self):
        overrides = {
            'bind_address': random_id(),
            'loglevel': random_id(),
            'file_compression': 'deflate_9',
            'uuid': usercouch.random_salt(),
        }

        # Test with bad auth
        with self.assertRaises(ValueError) as cm:
            usercouch.build_config('magic')
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")
        with self.assertRaises(ValueError) as cm:
            usercouch.build_config('magic', deepcopy(overrides))
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")

        # Test with all valid "file_compression" values
        good = ['none', 'snappy']
        good.extend('deflate_{}'.format(i) for i in range(1, 10))
        for value in good:
            config = usercouch.build_config('open',
                {'file_compression': value}
            )
            self.assertEqual(config['file_compression'], value)

        # Test with a bad "file_compression" value
        with self.assertRaises(ValueError) as cm:
            usercouch.build_config('open', {'file_compression': 'deflate_10'})
        self.assertEqual(
            str(cm.exception),
            "invalid config['file_compression']: 'deflate_10'"
        )

        # Test with bad 'ssl' (makes sure check_ssl_config() is called):
        with self.assertRaises(ValueError) as cm:
            usercouch.build_config('open', {'ssl': {}})
        self.assertEqual(
            str(cm.exception),
            "config['ssl']['cert_file'] is required, but missing"
        )

        # Makes sure check_replicator_config() is calld:
        with self.assertRaises(ValueError) as cm:
            usercouch.build_config('open', {'replicator': {}})
        self.assertEqual(
            str(cm.exception),
            "config['replicator']['ca_file'] is required, but missing"
        )

        # auth='open'
        config = usercouch.build_config('open')
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set(['bind_address', 'loglevel', 'file_compression', 'uuid'])
        )
        self.assertEqual(config['bind_address'], '127.0.0.1')
        self.assertEqual(config['loglevel'], 'notice')
        self.assertEqual(config['file_compression'], 'snappy')

        # auth='open' with overrides
        self.assertEqual(
            usercouch.build_config('open', deepcopy(overrides)),
            {
                'bind_address': overrides['bind_address'],
                'loglevel': overrides['loglevel'],
                'file_compression': 'deflate_9',
                'uuid': overrides['uuid'],
            }
        )

        # auth='basic'
        config = usercouch.build_config('basic')
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set([
                'bind_address',
                'loglevel',
                'file_compression',
                'uuid',
                'username',
                'password',
                'salt',
            ])
        )
        self.assertEqual(config['bind_address'], '127.0.0.1')
        self.assertEqual(config['loglevel'], 'notice')
        self.assertEqual(config['file_compression'], 'snappy')

        # auth='basic' with overrides
        config = usercouch.build_config('basic', deepcopy(overrides))
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set([
                'bind_address',
                'loglevel',
                'file_compression',
                'uuid',
                'username',
                'password',
                'salt',
            ])
        )
        self.assertEqual(config['bind_address'], overrides['bind_address'])
        self.assertEqual(config['loglevel'], overrides['loglevel'])
        self.assertEqual(config['file_compression'], 'deflate_9')
        self.assertEqual(config['uuid'], overrides['uuid'])
        o2 = {
            'bind_address': random_id(),
            'loglevel': random_id(),
            'file_compression': 'none',
            'uuid': usercouch.random_salt(),
            'username': random_id(),
            'password': random_id(),
            'salt': usercouch.random_salt(),
        }
        self.assertEqual(
            usercouch.build_config('basic', deepcopy(o2)),
            {
                'bind_address': o2['bind_address'],
                'loglevel': o2['loglevel'],
                'file_compression': 'none',
                'uuid': o2['uuid'],
                'username': o2['username'],
                'password': o2['password'],
                'salt': o2['salt'],
            }
        )

        # auth='oauth'
        config = usercouch.build_config('oauth')
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set([
                'bind_address',
                'loglevel',
                'file_compression',
                'uuid',
                'username',
                'password',
                'salt',
                'oauth',
            ])
        )
        self.assertEqual(config['bind_address'], '127.0.0.1')
        self.assertEqual(config['loglevel'], 'notice')
        self.assertEqual(config['file_compression'], 'snappy')
        self.assertIsInstance(config['oauth'], dict)
        self.assertEqual(set(config['oauth']),
            set(['token', 'token_secret', 'consumer_key', 'consumer_secret'])
        )

        # auth='oauth' with overrides
        config = usercouch.build_config('oauth', deepcopy(overrides))
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config),
            set([
                'bind_address',
                'loglevel',
                'file_compression',
                'uuid',
                'username',
                'password',
                'salt',
                'oauth',
            ])
        )
        self.assertEqual(config['bind_address'], overrides['bind_address'])
        self.assertEqual(config['loglevel'], overrides['loglevel'])
        self.assertEqual(config['file_compression'], 'deflate_9')
        self.assertEqual(config['uuid'], overrides['uuid'])
        self.assertIsInstance(config['oauth'], dict)
        self.assertEqual(set(config['oauth']),
            set(['token', 'token_secret', 'consumer_key', 'consumer_secret'])
        )
        o3 = {
            'bind_address': random_id(),
            'loglevel': random_id(),
            'file_compression': 'none',
            'uuid': usercouch.random_salt(),
            'username': random_id(),
            'password': random_id(),
            'salt': usercouch.random_salt(),
            'oauth': usercouch.random_oauth(),
        }
        self.assertEqual(
            usercouch.build_config('basic', deepcopy(o3)),
            {
                'bind_address': o3['bind_address'],
                'loglevel': o3['loglevel'],
                'file_compression': 'none',
                'uuid': o3['uuid'],
                'username': o3['username'],
                'password': o3['password'],
                'salt': o3['salt'],
                'oauth': o3['oauth'],
            }
        )

    def test_netloc_template(self):
        self.assertEqual(
            usercouch.netloc_template('127.0.0.1'),
            '127.0.0.1:{}'
        )
        self.assertEqual(
            usercouch.netloc_template('0.0.0.0'),
            '127.0.0.1:{}'
        )
        self.assertEqual(
            usercouch.netloc_template('::1'),
            '[::1]:{}'
        )
        self.assertEqual(
            usercouch.netloc_template('::'),
            '[::1]:{}'
        )
        with self.assertRaises(ValueError) as cm:
            usercouch.netloc_template('192.168.0.2')
        self.assertEqual(
            str(cm.exception),
            "invalid bind_address: '192.168.0.2'"
        )

    def test_build_url(self):
        # Test with invalid scheme
        with self.assertRaises(ValueError) as cm:
            usercouch.build_url('sftp', None, None)
        self.assertEqual(
            str(cm.exception),
            "scheme must be 'http' or 'https'; got 'sftp'"
        )

        # Test with an invalid address:
        with self.assertRaises(ValueError) as cm:
            usercouch.build_url('http', '192.168.0.2', None)
        self.assertEqual(
            str(cm.exception),
            "invalid bind_address: '192.168.0.2'"
        )

        # IPv4:
        self.assertEqual(
            usercouch.build_url('http', '127.0.0.1', 2001),
            'http://127.0.0.1:2001/'
        )
        self.assertEqual(
            usercouch.build_url('http', '0.0.0.0', 2002),
            'http://127.0.0.1:2002/'
        )
        self.assertEqual(
            usercouch.build_url('https', '127.0.0.1', 2003),
            'https://127.0.0.1:2003/'
        )
        self.assertEqual(
            usercouch.build_url('https', '0.0.0.0', 2004),
            'https://127.0.0.1:2004/'
        )

        # IPv6:
        self.assertEqual(
            usercouch.build_url('http', '::1', 2005),
            'http://[::1]:2005/'
        )
        self.assertEqual(
            usercouch.build_url('http', '::', 2006),
            'http://[::1]:2006/'
        )
        self.assertEqual(
            usercouch.build_url('https', '::1', 2007),
            'https://[::1]:2007/'
        )
        self.assertEqual(
            usercouch.build_url('https', '::', 2008),
            'https://[::1]:2008/'
        )

    def test_build_env(self):
        config = {
            'username': random_id(),
            'password': random_id(),
            'oauth': usercouch.random_oauth(),
            'bind_address': '127.0.0.1',
        }
        port = test_port()
        ports = {'port': port}

        # Test with bad auth
        with self.assertRaises(ValueError) as cm:
            usercouch.build_env('magic', deepcopy(config), ports)
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")

        # auth='open'
        self.assertEqual(
            usercouch.build_env('open', deepcopy(config), ports),
            {
                'port': port,
                'url': 'http://127.0.0.1:{}/'.format(port),
            }
        )

        # auth='basic'
        self.assertEqual(
            usercouch.build_env('basic', deepcopy(config), ports),
            {
                'port': port,
                'url': 'http://127.0.0.1:{}/'.format(port),
                'basic': {
                    'username': config['username'],
                    'password': config['password'],
                },
            }
        )

        # auth='oauth'
        self.assertEqual(
            usercouch.build_env('oauth', deepcopy(config), ports),
            {
                'port': port,
                'url': 'http://127.0.0.1:{}/'.format(port),
                'basic': {
                    'username': config['username'],
                    'password': config['password'],
                },
                'oauth': config['oauth'],
            }
        )

    def test_build_template_kw(self):
        config = {
            'bind_address': random_id(),
            'loglevel': random_id(),
            'file_compression': random_id(),
            'uuid': usercouch.random_salt(),
            'username': random_id(),
            'password': random_id(),
            'salt': usercouch.random_salt(),
            'oauth': usercouch.random_oauth(),
        }
        port = test_port()
        ports = {'port': port}
        tmp = TempDir()
        paths = usercouch.Paths(tmp.dir)

        # Test with bad auth
        with self.assertRaises(ValueError) as cm:
            usercouch.build_template_kw('magic', deepcopy(config), ports, paths)
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")

        # auth='open'
        self.assertEqual(
            usercouch.build_template_kw('open', deepcopy(config), ports, paths),
            {
                'bind_address': config['bind_address'],
                'loglevel': config['loglevel'],
                'file_compression': config['file_compression'],
                'uuid': config['uuid'],
                'port': port,
                'databases': paths.databases,
                'views': paths.views,
                'logfile': paths.logfile,
            }
        )

        # auth='basic'
        self.assertEqual(
            usercouch.build_template_kw('basic', deepcopy(config), ports, paths),
            {
                'bind_address': config['bind_address'],
                'loglevel': config['loglevel'],
                'file_compression': config['file_compression'],
                'uuid': config['uuid'],
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
            usercouch.build_template_kw('oauth', deepcopy(config), ports, paths),
            {
                'bind_address': config['bind_address'],
                'loglevel': config['loglevel'],
                'file_compression': config['file_compression'],
                'uuid': config['uuid'],
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

        # Test with ssl_port and ssl:
        cfg = deepcopy(config)
        ca = tmp.touch('ca.pem')
        key = tmp.touch('key.pem')
        cert = tmp.touch('cert.pem')
        cfg['ssl'] = {'ca_file': ca, 'key_file': key, 'cert_file': cert}
        ssl_port = test_port()
        ports = {'port': port, 'ssl_port': ssl_port}
        self.assertEqual(
            usercouch.build_template_kw('open', cfg, ports, paths),
            {
                'bind_address': config['bind_address'],
                'loglevel': config['loglevel'],
                'file_compression': config['file_compression'],
                'uuid': config['uuid'],
                'port': port,
                'ssl_port': ssl_port,
                'databases': paths.databases,
                'views': paths.views,
                'logfile': paths.logfile,
                'ca_file': ca,
                'key_file': key,
                'cert_file': cert,
            }
        )

        # Test with replicator['ca_file']
        cfg = deepcopy(config)
        remote_ca = tmp.touch('remote.ca')
        cfg['replicator'] = {'ca_file': remote_ca}
        ports = {'port': port}
        self.assertEqual(
            usercouch.build_template_kw('open', cfg, ports, paths),
            {
                'bind_address': config['bind_address'],
                'loglevel': config['loglevel'],
                'file_compression': config['file_compression'],
                'uuid': config['uuid'],
                'port': port,
                'databases': paths.databases,
                'views': paths.views,
                'logfile': paths.logfile,
                'replicator': {'ca_file': remote_ca},
            }
        )

    def test_build_session_ini(self):
        # Test with bad auth
        with self.assertRaises(ValueError) as cm:
            usercouch.build_session_ini('magic', {})
        self.assertEqual(str(cm.exception), "invalid auth: 'magic'")

        # Test with auth='open'
        keys = (
            'bind_address',
            'port',
            'databases',
            'views',
            'file_compression',
            'uuid',
            'logfile',
            'loglevel',
        )
        kw = dict(
            (key, random_id())
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
            'bind_address',
            'port',
            'databases',
            'views',
            'file_compression',
            'uuid',
            'logfile',
            'loglevel',
            'username', 'hashed',
        )
        kw = dict(
            (key, random_id())
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
            'bind_address',
            'port',
            'databases',
            'views',
            'file_compression',
            'uuid',
            'logfile',
            'loglevel',
            'username', 'hashed',
            'token', 'token_secret', 'consumer_key', 'consumer_secret',
        )
        kw = dict(
            (key, random_id())
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

        # Test with auth='basic' and SSL
        keys = (
            'bind_address',
            'port',
            'databases',
            'views',
            'file_compression',
            'uuid',
            'logfile',
            'loglevel',
            'username', 'hashed',
            'ssl_port', 'cert_file', 'key_file',
        )
        kw = dict(
            (key, random_id())
            for key in keys
        )
        template = usercouch.BASIC + usercouch.SSL
        self.assertEqual(
            usercouch.build_session_ini('basic', deepcopy(kw)),
            template.format(**kw)
        )
        for key in keys:
            if key == 'ssl_port':
                continue
            bad = deepcopy(kw)
            del bad[key]
            with self.assertRaises(KeyError) as cm:
                usercouch.build_session_ini('basic', bad)
            self.assertEqual(str(cm.exception), repr(key))

        # Test with auth='basic' and kw['replicator']
        keys = (
            'bind_address',
            'port',
            'databases',
            'views',
            'file_compression',
            'uuid',
            'logfile',
            'loglevel',
            'username', 'hashed',
        )
        kw = dict(
            (key, random_id())
            for key in keys
        )
        kw['replicator'] = {
            'ca_file': random_id(),
            'max_depth': 2,
        }
        template = usercouch.BASIC + usercouch.REPLICATOR
        self.assertEqual(
            usercouch.build_session_ini('basic', deepcopy(kw)),
            template.format(**kw)
        )
        for key in keys:
            bad = deepcopy(kw)
            del bad[key]
            with self.assertRaises(KeyError) as cm:
                usercouch.build_session_ini('basic', bad)
            self.assertEqual(str(cm.exception), repr(key))
        for key in ['ca_file', 'max_depth']:
            bad = deepcopy(kw)
            del bad['replicator'][key]
            with self.assertRaises(KeyError) as cm:
                usercouch.build_session_ini('basic', bad)
            self.assertEqual(str(cm.exception), repr(key))

        # Test with auth='basic' and kw['replicator'], with 'cert_file'
        keys = (
            'bind_address',
            'port',
            'databases',
            'views',
            'file_compression',
            'uuid',
            'logfile',
            'loglevel',
            'username', 'hashed',
        )
        kw = dict(
            (key, random_id())
            for key in keys
        )
        kw['replicator'] = {
            'ca_file': random_id(),
            'max_depth': 1,
            'cert_file': random_id(),
            'key_file': random_id(),
        }
        template = usercouch.BASIC + usercouch.REPLICATOR_EXTRA
        self.assertEqual(
            usercouch.build_session_ini('basic', deepcopy(kw)),
            template.format(**kw)
        )
        for key in keys:
            bad = deepcopy(kw)
            del bad[key]
            with self.assertRaises(KeyError) as cm:
                usercouch.build_session_ini('basic', bad)
            self.assertEqual(str(cm.exception), repr(key))
        for key in ['ca_file', 'max_depth', 'key_file']:
            bad = deepcopy(kw)
            del bad['replicator'][key]
            with self.assertRaises(KeyError) as cm:
                usercouch.build_session_ini('basic', bad)
            self.assertEqual(str(cm.exception), repr(key))

    def test_bind_socket(self):
        sock = usercouch.bind_socket('127.0.0.1')
        self.assertIsInstance(sock, socket.socket)
        port = sock.getsockname()[1]
        self.assertEqual(sock.getsockname(), ('127.0.0.1', port))
        sock2 = usercouch.bind_socket('127.0.0.1')
        self.assertNotEqual(sock2.getsockname()[1], port)

        sock = usercouch.bind_socket('0.0.0.0')
        self.assertIsInstance(sock, socket.socket)
        port = sock.getsockname()[1]
        self.assertEqual(sock.getsockname(), ('0.0.0.0', port))
        sock2 = usercouch.bind_socket('0.0.0.0')
        self.assertNotEqual(sock2.getsockname()[1], port)

        sock = usercouch.bind_socket('::1')
        self.assertIsInstance(sock, socket.socket)
        port = sock.getsockname()[1]
        self.assertEqual(sock.getsockname(), ('::1', port, 0, 0))
        sock2 = usercouch.bind_socket('::1')
        self.assertNotEqual(sock2.getsockname()[1], port)

        sock = usercouch.bind_socket('::')
        self.assertIsInstance(sock, socket.socket)
        port = sock.getsockname()[1]
        self.assertEqual(sock.getsockname(), ('::', port, 0, 0))
        sock2 = usercouch.bind_socket('::')
        self.assertNotEqual(sock2.getsockname()[1], port)

        # Test with an invalid bind_address:
        with self.assertRaises(ValueError) as cm:
            usercouch.bind_socket('192.168.0.2')
        self.assertEqual(
            str(cm.exception),
            "invalid bind_address: '192.168.0.2'"
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


class TestSockets(TestCase):
    def test_init(self):
        socks = usercouch.Sockets('127.0.0.1')
        self.assertEqual(socks.bind_address, '127.0.0.1')
        self.assertIsInstance(socks.socks, dict)
        self.assertEqual(set(socks.socks), set(['port']))
        self.assertIsInstance(socks.socks['port'], socket.socket)

    def test_add_ssl(self):
        socks = usercouch.Sockets('127.0.0.1')
        self.assertIsNone(socks.add_ssl())
        self.assertIsInstance(socks.socks, dict)
        self.assertEqual(set(socks.socks), set(['port', 'ssl_port']))
        self.assertIsInstance(socks.socks['port'], socket.socket)
        self.assertIsInstance(socks.socks['ssl_port'], socket.socket)
        self.assertIsNot(socks.socks['port'], socks.socks['ssl_port'])

    def test_get_ports(self):
        socks = usercouch.Sockets('127.0.0.1')
        port = socks.socks['port'].getsockname()[1]
        self.assertEqual(socks.get_ports(),
            {'port': port}
        )

        socks = usercouch.Sockets('127.0.0.1')
        socks.add_ssl()
        port = socks.socks['port'].getsockname()[1]
        ssl_port = socks.socks['ssl_port'].getsockname()[1]
        self.assertEqual(socks.get_ports(),
            {'port': port, 'ssl_port': ssl_port}
        )

    def test_close(self):
        socks = usercouch.Sockets('127.0.0.1')
        for sock in socks.socks.values():
            self.assertFalse(sock._closed)
        self.assertIsNone(socks.close())
        for sock in socks.socks.values():
            self.assertTrue(sock._closed)

        socks = usercouch.Sockets('127.0.0.1')
        socks.add_ssl()
        for sock in socks.socks.values():
            self.assertFalse(sock._closed)
        self.assertIsNone(socks.close())
        for sock in socks.socks.values():
            self.assertTrue(sock._closed)


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
        self.assertEqual(paths.dump, tmp.join('dump'))
        self.assertEqual(paths.ssl, tmp.join('ssl'))
        self.assertEqual(paths.log, tmp.join('log'))
        self.assertEqual(paths.logfile, tmp.join('log', 'couchdb.log'))
        self.assertTrue(path.isdir(paths.databases))
        self.assertTrue(path.isdir(paths.views))
        self.assertTrue(path.isdir(paths.dump))
        self.assertTrue(path.isdir(paths.ssl))
        self.assertTrue(path.isdir(paths.log))
        self.assertEqual(
            sorted(os.listdir(tmp.dir)),
            ['databases', 'dump', 'log', 'ssl', 'views']
        )
        self.assertEqual(os.listdir(tmp.join('log')), [])

        tmp.touch('log', 'couchdb.log')
        paths = usercouch.Paths(tmp.dir)
        self.assertEqual(paths.ini, tmp.join('session.ini'))
        self.assertEqual(paths.databases, tmp.join('databases'))
        self.assertEqual(paths.views, tmp.join('views'))
        self.assertEqual(paths.dump, tmp.join('dump'))
        self.assertEqual(paths.ssl, tmp.join('ssl'))
        self.assertEqual(paths.log, tmp.join('log'))
        self.assertEqual(paths.logfile, tmp.join('log', 'couchdb.log'))
        self.assertTrue(path.isdir(paths.databases))
        self.assertTrue(path.isdir(paths.views))
        self.assertTrue(path.isdir(paths.dump))
        self.assertTrue(path.isdir(paths.ssl))
        self.assertTrue(path.isdir(paths.log))
        self.assertEqual(
            sorted(os.listdir(tmp.dir)),
            ['databases', 'dump', 'log', 'ssl', 'views']
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
        self.assertFalse(uc.lockfile.closed)
        self.assertIsInstance(uc.paths, usercouch.Paths)
        self.assertEqual(uc.paths.ini, tmp.join('good', 'session.ini'))
        self.assertEqual(uc.cmd, usercouch.get_cmd(uc.paths.ini))

    def test_lockfile(self):
        tmp = TempDir()
        lockfile = tmp.join('lockfile')

        # Create first instance
        a = usercouch.UserCouch(tmp.dir)
        self.assertIsInstance(a.lockfile, io.BufferedWriter)
        self.assertEqual(a.lockfile.name, lockfile)
        self.assertFalse(a.lockfile.closed)

        # Make sure `a` has the lock
        with self.assertRaises(usercouch.LockError) as cm:
            b = usercouch.UserCouch(tmp.dir)
        self.assertEqual(cm.exception.lockfile, lockfile)

        # Test releasing by directly calling UserCouch.__del__()
        self.assertFalse(a.lockfile.closed)
        a.__del__()
        self.assertTrue(a.lockfile.closed)
        b = usercouch.UserCouch(tmp.dir)

        # Make sure `b` has the lock:
        with self.assertRaises(usercouch.LockError) as cm:
            c = usercouch.UserCouch(tmp.dir)
        self.assertEqual(cm.exception.lockfile, lockfile)

        # Test releasing by dereferencing:
        self.assertFalse(b.lockfile.closed)
        b = None
        c = usercouch.UserCouch(tmp.dir)

        # Make sure `c` has the lock:
        with self.assertRaises(usercouch.LockError) as cm:
            d = usercouch.UserCouch(tmp.dir)
        self.assertEqual(cm.exception.lockfile, lockfile)

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
        self.assertEqual(env['url'], 'http://127.0.0.1:{}/'.format(port))

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
        self.assertEqual(env['url'], 'http://127.0.0.1:{}/'.format(port))
        self.assertIsInstance(env['basic'], dict)
        self.assertEqual(
            set(env['basic']),
            set(['username', 'password'])
        )
        for value in env['basic'].values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(isdb32(value))

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

        # Test with extra
        extra = random_id()
        tmp = TempDir()
        uc = usercouch.UserCouch(tmp.dir)
        env = uc.bootstrap(extra=extra)
        ini = open(tmp.join('session.ini'), 'r').read()
        self.assertTrue(ini.endswith(extra))

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
        self.assertEqual(env['url'], 'http://127.0.0.1:{}/'.format(port))
        self.assertIsInstance(env['basic'], dict)
        self.assertEqual(
            set(env['basic']),
            set(['username', 'password'])
        )
        for value in env['basic'].values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(isdb32(value))
        self.assertIsInstance(env['oauth'], dict)
        self.assertEqual(
            set(env['oauth']),
            set(['consumer_key', 'consumer_secret', 'token', 'token_secret'])
        )
        for value in env['oauth'].values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(isdb32(value))

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
            'bind_address': '::1',
            'username': random_id(),
            'password': random_id(),
            'uuid': usercouch.random_salt(),
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
            'http://[::1]:{}/'.format(env['port'])
        )
        self.assertEqual(env['basic'],
            dict((k, overrides[k]) for k in ('username', 'password'))
        )
        kw = {
            'bind_address': overrides['bind_address'],
            'uuid': overrides['uuid'],
            'port': env['port'],
            'databases': uc.paths.databases,
            'views': uc.paths.views,
            'file_compression': 'snappy',
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
            'bind_address': '::1',
            'username': random_id(),
            'password': random_id(),
            'uuid': usercouch.random_salt(),
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
            'http://[::1]:{}/'.format(env['port'])
        )
        self.assertEqual(env['basic'],
            dict((k, overrides[k]) for k in ('username', 'password'))
        )
        self.assertEqual(env['oauth'], overrides['oauth'])
        kw = {
            'bind_address': overrides['bind_address'],
            'uuid': overrides['uuid'],
            'port': env['port'],
            'databases': uc.paths.databases,
            'views': uc.paths.views,
            'file_compression': 'snappy',
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

    def test_bootstrap_ssl(self):
        tmp = TempDir()

        # Create CA, machine cert:
        user_id = random_id()
        machine_id = random_id()
        pki = sslhelpers.PKI(tmp.dir)
        pki.create_server_pki(user_id, machine_id)
        ssl_config = pki.get_server_config()

        overrides = {'ssl': ssl_config}

        uc = usercouch.UserCouch(tmp.dir)
        self.assertFalse(path.exists(uc.paths.ini))
        env = uc.bootstrap('basic', overrides)
        self.assertTrue(path.isfile(uc.paths.ini))
        self.assertEqual(uc._headers, usercouch.get_headers(env))
        self.assertEqual(set(uc._headers), set(['Accept', 'Authorization']))

        # check env
        self.assertIsInstance(env, dict)
        self.assertEqual(set(env), set(['port', 'url', 'basic', 'x_env_ssl']))
        port = env['port']
        self.assertIsInstance(port, int)
        self.assertGreater(port, 1024)
        self.assertEqual(env['url'], 'http://127.0.0.1:{}/'.format(port))
        self.assertIsInstance(env['basic'], dict)
        self.assertEqual(
            set(env['basic']),
            set(['username', 'password'])
        )
        for value in env['basic'].values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(isdb32(value))

        # check env['x_env_ssl']
        env2 = env['x_env_ssl']
        self.assertIsInstance(env2, dict)
        self.assertEqual(set(env2), set(['port', 'url', 'basic']))
        ssl_port = env2['port']
        self.assertIsInstance(ssl_port, int)
        self.assertGreater(ssl_port, 1024)
        self.assertNotEqual(ssl_port, port)
        self.assertEqual(env2['url'], 'https://127.0.0.1:{}/'.format(ssl_port))
        self.assertEqual(env2['basic'], env['basic'])

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
        self.assertIsInstance(uc._welcome, dict)
        self.assertTrue(
            set(uc._welcome).issubset(['couchdb', 'uuid', 'vendor', 'version'])
        )
        self.assertIn(uc._welcome['version'], ('1.2.0', '1.4.0'))
        if 'uuid' in uc._welcome:
            self.assertIsInstance(uc._welcome['uuid'], str)
            self.assertEqual(len(uc._welcome['uuid']), 32)
            self.assertTrue(
                set(uc._welcome['uuid']).issubset('0123456789abcdef')
            )
        if 'vendor' in uc._welcome:
            self.assertIsInstance(uc._welcome['vendor'], dict)
            self.assertEqual(set(uc._welcome['vendor']), 
                set(['name', 'version'])
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
