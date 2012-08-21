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
import fcntl
import time
from subprocess import Popen
from hashlib import sha1, md5
from base64 import b32encode, b64encode
import json
from http.client import HTTPConnection, BadStatusLine
from urllib.parse import urlparse


__version__ = '12.09.0'

USERCOUCH_INI = path.join(
    path.dirname(path.abspath(__file__)), 'data', 'usercouch.ini'
)
assert path.isfile(USERCOUCH_INI)

# Allowed values for `file_compression`:
FILE_COMPRESSION = (
    'none',
    'deflate_1',
    'deflate_2',
    'deflate_3',
    'deflate_4',
    'deflate_5',
    'deflate_6',
    'deflate_7',
    'deflate_8',
    'deflate_9',
    'snappy',
)

DEFAULT_CONFIG = (
    ('address', '127.0.0.1'),
    ('loglevel', 'notice'),
    ('file_compression', 'snappy'),
)

OPEN = """[httpd]
bind_address = {address}
port = {port}

[couchdb]
database_dir = {databases}
view_index_dir = {views}
file_compression = {file_compression}

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

TEMPLATES = {
    'open': OPEN,
    'basic': BASIC,
    'oauth': OAUTH,
}


########################################################################
# Functions for building CouchDB session.ini file, Microfiber-style env:

def random_b32(numbytes=15):
    """
    Return a 120-bit base32-encoded random string.

    The `str` will be 24-characters long, URL and filesystem safe.
    """
    return b32encode(os.urandom(numbytes)).decode('utf-8')


def random_oauth():
    """
    Return a `dict` containing random OAuth 1a tokens.
    """
    return dict(
        (k, random_b32())
        for k in ('consumer_key', 'consumer_secret', 'token', 'token_secret')
    )


def random_salt():
    """
    Return a 128-bit hex-encoded random salt for use  by `couch_hashed()`.
    """
    return md5(os.urandom(16)).hexdigest()


def couch_hashed(password, salt):
    """
    Hash *password* using *salt*.

    This returns a CouchDB-style hashed password to be use in the session.ini
    file.  For example:

    >>> couch_hashed('secret', 'da52c844db4b8bd88ebb96d72542457a')
    '-hashed-ddf425840fd7f81cc45d9e9f5aa484d1f60964a9,da52c844db4b8bd88ebb96d72542457a'

    Typically `UserCouch` is used with a per-session random password, so this
    function means that the clear-text of the password is only stored in
    memory, is never written to disk.
    """
    assert len(salt) == 32
    data = (password + salt).encode('utf-8')
    hexdigest = sha1(data).hexdigest()
    return '-hashed-{},{}'.format(hexdigest, salt)


def build_config(auth, overrides=None):
    if auth not in TEMPLATES:
        raise ValueError('invalid auth: {!r}'.format(auth))
    config = dict(DEFAULT_CONFIG)
    if overrides:
        config.update(overrides)
    if config['file_compression'] not in FILE_COMPRESSION:
        raise ValueError("invalid 'file_compression': {!r}".format(
                config['file_compression'])
        )
    if auth in ('basic', 'oauth'):
        if 'username' not in config:
            config['username'] = random_b32()
        if 'password' not in config:
            config['password'] = random_b32()
        if 'salt' not in config:
            config['salt'] = random_salt()
    if auth == 'oauth':
        if 'oauth' not in config:
            config['oauth'] = random_oauth()
    return config


def build_env(auth, config, port):
    if auth not in TEMPLATES:
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
    if auth not in TEMPLATES:
        raise ValueError('invalid auth: {!r}'.format(auth))
    kw = {
        'address': config['address'],
        'loglevel': config['loglevel'],
        'file_compression': config['file_compression'],
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


def build_session_ini(auth, kw):
    if auth not in TEMPLATES:
        raise ValueError('invalid auth: {!r}'.format(auth))
    template = TEMPLATES[auth]
    return template.format(**kw)


def bind_random_port(address):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((address, 0))
    port = sock.getsockname()[1]
    return (sock, port)


def get_cmd(session_ini):
    return [
        '/usr/bin/couchdb',
        '-n',  # reset configuration file chain (including system default)
        '-a', '/etc/couchdb/default.ini',
        '-a', USERCOUCH_INI,
        '-a', session_ini,
    ]



#######################
# Path related helpers:

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

    __slots__ = ('ini', 'databases', 'views', 'dump', 'bzr', 'log', 'logfile')

    def __init__(self, basedir):
        # FIXME: We should remove the `bzr` dir and use `dump` instead
        self.ini = path.join(basedir, 'session.ini')
        self.databases = mkdir(basedir, 'databases')
        self.views = mkdir(basedir, 'views')
        self.dump = mkdir(basedir, 'dump')
        self.bzr = mkdir(basedir, 'bzr')
        self.log = mkdir(basedir, 'log')
        self.logfile = logfile(self.log, 'couchdb')



#######################
# HTTP related helpers:

class HTTPError(Exception):
    def __init__(self, response, method, path):
        self.response = response
        self.method = method
        self.path = path
        super().__init__(
            '{} {}: {} {}'.format(response.status, response.reason, method, path)
        )


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



########################
# The `UserCouch` class:


class LockError(Exception):
    def __init__(self, lockfile):
        self.lockfile = lockfile
        super().__init__(
            'cannot acquire exclusive lock on {!r}'.format(lockfile)
        )


class UserCouch:
    def __init__(self, basedir):
        self.couchdb = None
        self.basedir = path.abspath(basedir)
        if not path.isdir(self.basedir):
            raise ValueError('{}.basedir not a directory: {!r}'.format(
                self.__class__.__name__, self.basedir)
            )
        self.lockfile = open(path.join(self.basedir, 'lockfile'), 'wb')
        try:
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise LockError(self.lockfile.name)
        self.paths = Paths(self.basedir)
        self.cmd = get_cmd(self.paths.ini)
        self.__bootstraped = False

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.basedir)

    def __del__(self):
        self.kill()
        if not self.lockfile.closed:
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_UN)
            self.lockfile.close()

    def bootstrap(self, auth='basic', overrides=None):
        if self.__bootstraped:
            raise Exception(
                '{}.bootstrap() already called'.format(self.__class__.__name__)
            )
        self.__bootstraped = True
        config = build_config(auth, overrides)
        (sock, port) = bind_random_port(config['address'])
        env = build_env(auth, config, port)
        kw = build_template_kw(auth, config, port, self.paths)
        session = build_session_ini(auth, kw)
        open(self.paths.ini, 'w').write(session)
        self._conn = get_conn(env)
        self._headers = get_headers(env)
        sock.close()
        self.start()
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
