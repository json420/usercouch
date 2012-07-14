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
`usercouch` - starts per-user CouchDB instances for fun and unit testing.
"""

import socket
import os
from os import path
import stat
import time
from subprocess import Popen
from hashlib import sha1, md5
from base64 import b32encode, b64encode
import json
from http.client import HTTPConnection, BadStatusLine
from urllib.parse import urlparse


__version__ = '12.07.0'
usercouch_ini = path.join(
    path.dirname(path.abspath(__file__)), 'data', 'usercouch.ini'
)
assert path.isfile(usercouch_ini)


DEFAULT_CONFIG = (
    ('address', '127.0.0.1'),
    ('loglevel', 'notice'),
)

OPEN = """[httpd]
bind_address = {address}
port = {port}

[couchdb]
database_dir = {databases}
view_index_dir = {views}

[log]
file = {logfile}
level = {loglevel}
"""

BASIC = OPEN + """
[couch_httpd_auth]
require_valid_user = true

[admins]
{username} = {hashed}
"""

OAUTH = BASIC + """
[oauth_token_users]
{token} = {username}

[oauth_token_secrets]
{token} = {token_secret}

[oauth_consumer_secrets]
{consumer_key} = {consumer_secret}
"""


def random_id(numbytes=15):
    """
    Returns a 120-bit base32-encoded random ID.

    The ID will be 24-characters long, URL and filesystem safe.  For example:

    >>> random_id()  #doctest: +SKIP
    'OVRHK3TUOUQCWIDMNFXGC4TP'

    This is how dmedia/Novacut random IDs are created, so this is "Jason
    approved", for what that's worth.
    """
    return b32encode(os.urandom(numbytes)).decode('utf-8')


def random_basic():
    return dict(
        (k, random_id())
        for k in ('username', 'password')
    )


def random_oauth():
    return dict(
        (k, random_id())
        for k in ('consumer_key', 'consumer_secret', 'token', 'token_secret')
    )


def random_salt():
    return md5(os.urandom(16)).hexdigest()


def couch_hashed(password, salt):
    assert len(salt) == 32
    data = (password + salt).encode('utf-8')
    hexdigest = sha1(data).hexdigest()
    return '-hashed-{},{}'.format(hexdigest, salt)


def build_config(auth, overrides=None):
    if auth not in ('open', 'basic', 'oauth'):
        raise ValueError('invalid auth: {!r}'.format(auth))
    config = dict(DEFAULT_CONFIG)
    if overrides:
        config.update(overrides)
    if auth in ('basic', 'oauth'):
        if 'username' not in config:
            config['username'] = random_id()
        if 'password' not in config:
            config['password'] = random_id()
        if 'salt' not in config:
            config['salt'] = random_salt()
    if auth == 'oauth':
        if 'oauth' not in config:
            config['oauth'] = random_oauth()
    return config


def build_env(auth, config, port):
    if auth not in ('open', 'basic', 'oauth'):
        raise ValueError('invalid auth: {!r}'.format(auth))
    env = {
        'port': port,
        'url': 'http://localhost:{}/'.format(port),
    }
    if auth in ('basic', 'oauth'):
        env['basic'] = {
            'username': config['username'],
            'password': config['password'],
        }
    if auth == 'oauth':
        env['oauth'] = config['oauth']
    return env


def build_template_kw(auth, config, port, paths):
    if auth not in ('open', 'basic', 'oauth'):
        raise ValueError('invalid auth: {!r}'.format(auth))
    kw = {
        'address': config['address'],
        'loglevel': config['loglevel'],
        'port': port,
        'databases': paths.databases,
        'views': paths.views,
        'logfile': paths.logfile,
    }
    if auth in ('basic', 'oauth'):
        kw['username'] = config['username']
        kw['hashed'] = couch_hashed(config['password'], config['salt'])
    if auth == 'oauth':
        kw.update(config['oauth'])
    return kw


def basic_auth_header(basic):
    b = '{username}:{password}'.format(**basic).encode('utf-8')
    b64 = b64encode(b).decode('utf-8')
    return {'Authorization': 'Basic ' + b64}


def get_conn(env):
    t = urlparse(env['url'])
    assert t.scheme == 'http'
    assert t.netloc
    return HTTPConnection(t.netloc)


def get_headers(env):
    headers = {'Accept': 'application/json'}
    if 'basic' in env:
        headers.update(basic_auth_header(env['basic']))
    return headers


def get_template(auth):
    if auth == 'open':
        return OPEN
    if auth == 'basic':
        return BASIC
    if auth == 'oauth':
        return OAUTH
    raise ValueError('invalid auth: {!r}'.format(auth))


def bind_random_port(address='127.0.0.1'):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((address, 0))
    port = sock.getsockname()[1]
    return (sock, port)


def random_env(port, auth, tokens=None):
    if auth not in ('open', 'basic', 'oauth'):
        raise ValueError('invalid auth: {!r}'.format(auth))
    env = {
        'port': port,
        'url': 'http://localhost:{}/'.format(port),
    }
    if auth == 'basic':
        env['basic'] = random_basic()
    elif auth == 'oauth':
        env['basic'] = random_basic()
        env['oauth'] = (random_oauth() if tokens is None else tokens)
    return env


def get_cmd(session_ini):
    return [
        '/usr/bin/couchdb',
        '-n',  # reset configuration file chain (including system default)
        '-a', '/etc/couchdb/default.ini',
        '-a', usercouch_ini,
        '-a', session_ini,
    ]


def mkdir(basedir, name):
    dirname = path.join(basedir, name)
    try:
        os.mkdir(dirname)
    except OSError:
        mode = os.lstat(dirname).st_mode
        if not stat.S_ISDIR(mode):
            raise ValueError('not a directory: {!r}'.format(dirname))
    return dirname


def logfile(logdir, name):
    filename = path.join(logdir, name + '.log')
    if path.isfile(filename):
        os.rename(filename, filename + '.previous')
    return filename


class Paths:
    """
    Just a namespace for the various files and directories in *basedir*.
    """

    __slots__ = ('ini', 'databases', 'views', 'bzr', 'log', 'logfile')

    def __init__(self, basedir):
        self.ini = path.join(basedir, 'session.ini')
        self.databases = mkdir(basedir, 'databases')
        self.views = mkdir(basedir, 'views')
        self.bzr = mkdir(basedir, 'bzr')
        self.log = mkdir(basedir, 'log')
        self.logfile = logfile(self.log, 'couchdb')


class HTTPError(Exception):
    def __init__(self, response, method, path):
        self.response = response
        self.method = method
        self.path = path
        super().__init__(
            '{} {}: {} {}'.format(response.status, response.reason, method, path)
        )


class UserCouch:
    def __init__(self, basedir):
        self.couchdb = None
        if not path.isdir(basedir):
            raise ValueError('{}.basedir not a directory: {!r}'.format(
                self.__class__.__name__, basedir)
            )
        self.basedir = basedir
        self.paths = Paths(basedir)
        self.cmd = get_cmd(self.paths.ini)
        self.__bootstraped = False

    def __del__(self):
        self.kill()

    def bootstrap(self, auth='basic', address='127.0.0.1', tokens=None, loglevel='notice'):
        if self.__bootstraped:
            raise Exception(
                '{}.bootstrap() already called'.format(self.__class__.__name__)
            )
        self.__bootstraped = True
        (sock, port) = bind_random_port(address)
        env = random_env(port, auth, tokens)
        kw = {
            'address': address,
            'port': port,
            'databases': self.paths.databases,
            'views': self.paths.views,
            'logfile': self.paths.logfile,
            'loglevel': loglevel,
        }
        if auth in ('basic', 'oauth'):
            kw['username'] = env['basic']['username']
            kw['hashed'] = couch_hashed(env['basic']['password'], random_salt())
        if auth == 'oauth':
            kw.update(env['oauth'])
        config = get_template(auth).format(**kw)
        open(self.paths.ini, 'w').write(config)
        self._conn = get_conn(env)
        self._headers = get_headers(env)
        sock.close()
        self.start()
        return env

    def bootstrap2(self, tokens):
        env = self.bootstrap(auth='oauth', address='0.0.0.0', tokens=tokens)
        del env['oauth']
        return env

    def start(self):
        if not self.__bootstraped:
            raise Exception(
                'Must call {0}.bootstrap() before {0}.start()'.format(
                        self.__class__.__name__)
            )
        if self.couchdb is not None:
            return False
        self.couchdb = Popen(self.cmd)
        # We give CouchDB ~67 seconds to start:
        t = 0.1
        for i in range(23):
            time.sleep(t)
            t *= 1.25
            if self.isalive():
                return True
        raise Exception('could not start CouchDB')

    def kill(self):
        if self.couchdb is None:
            return False
        self.couchdb.terminate()
        self.couchdb.wait()
        self.couchdb = None
        return True

    def _request(self, method, path):
        for retry in range(2):
            try:
                self._conn.request(method, path, None, self._headers)
                response = self._conn.getresponse()
                data = response.read()
                break
            except BadStatusLine as e:
                self._conn.close()
                if retry == 1:
                    raise e
            except Exception as e:
                self._conn.close()
                raise e
        if response.status >= 400:
            self._conn.close()
            raise HTTPError(response, method, path)
        return (response, data)

    def isalive(self):
        if not self.__bootstraped:
            raise Exception(
                'Must call {0}.bootstrap() before {0}.isalive()'.format(
                        self.__class__.__name__)
            )
        try:
            (response, data) = self._request('GET', '/')
            self._welcome = json.loads(data.decode('utf-8'))
            return True
        except socket.error:
            return False

    def check(self):
        if not self.__bootstraped:
            raise Exception(
                'Must call {0}.bootstrap() before {0}.check()'.format(
                        self.__class__.__name__)
            )
        if not self.isalive():
            self.kill()
            return self.start()
        return False

    def crash(self):
        if self.couchdb is None:
            return False
        self.couchdb.terminate()
        return True
