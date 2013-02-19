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
from copy import deepcopy
from subprocess import Popen
from hashlib import sha1, md5
from base64 import b32encode, b64encode
import json
from http.client import HTTPConnection, BadStatusLine
from urllib.parse import urlparse

from dbase32 import random_id

__version__ = '13.03.0'

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

# Minimum SSL config that must be provided in overrides['ssl']:
REQUIRED_SSL_CONFIG = ('cert_file', 'key_file')

# ALL config that can be provided in overrides['ssl']:
POSSIBLE_SSL_CONFIG = REQUIRED_SSL_CONFIG + ('ca_file',)


DEFAULT_CONFIG = (
    ('bind_address', '127.0.0.1'),
    ('loglevel', 'notice'),
    ('file_compression', 'snappy'),
)

OPEN = """[httpd]
bind_address = {bind_address}
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


# Wether or not this couch is using SSL, we can make the replicator
# only trust remote couches with certs signed by a specific CA
REPLICATOR = """
[replicator]
verify_ssl_certificates = true
ssl_certificate_max_depth = {replicator[max_depth]}
ssl_trusted_certificates_file = {replicator[ca_file]}
"""

# And the replicator can use a client cert to authenticate to the remote couch:
REPLICATOR_EXTRA = REPLICATOR + """cert_file = {replicator[cert_file]}
key_file = {replicator[key_file]}
"""

SSL = """
[daemons]
httpsd = {{couch_httpd, start_link, [https]}}

[ssl]
port = {ssl_port}
cert_file = {cert_file}
key_file = {key_file}
"""

# FIXME: Currently client cert verification isn't working.  I believe we
# need to write a custom `verify_fun` Erlang function, see:
#   http://www.erlang.org/doc/man/ssl.html
SSL_EXTRA = """
[ssl]
verify_ssl_certificates = true
cacert_file = {ca_file}
verify_fun = ???
"""


########################################################################
# Functions for building CouchDB session.ini file, Microfiber-style env:

def random_oauth():
    """
    Return a `dict` containing random OAuth 1a tokens.
    """
    return dict(
        (k, random_id())
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


def check_ssl_config(ssl_config):
    if not isinstance(ssl_config, dict):
        raise TypeError(
            "config['ssl'] must be a {!r}; got a {!r}: {!r}".format(
                dict, type(ssl_config), ssl_config)
        )
    for key in REQUIRED_SSL_CONFIG:
        if key not in ssl_config:
            raise ValueError(
                "config['ssl'][{!r}] is required, but missing".format(key)
            )
    for key in POSSIBLE_SSL_CONFIG:
        if key not in ssl_config:
            assert key == 'ca_file'
            continue
        value = ssl_config[key]
        if not path.isfile(value):
            raise ValueError(
                "config['ssl'][{!r}] not a file: {!r}".format(key, value)
            )


def check_replicator_config(cfg):
    if not isinstance(cfg, dict):
        raise TypeError(
            "config['replicator'] must be a {!r}; got a {!r}: {!r}".format(
                dict, type(cfg), cfg)
        )
    if 'max_depth' not in cfg:
        cfg['max_depth'] = 1
    max_depth = cfg['max_depth']
    if not isinstance(max_depth, int):
        raise TypeError(
            "config['replicator']['max_depth'] not an int: {!r}".format(max_depth)
        )
    if max_depth < 0:
        raise ValueError(
            "config['replicator']['max_depth'] < 0: {!r}".format(max_depth)
        )
    if 'ca_file' not in cfg:
        raise ValueError(
            "config['replicator']['ca_file'] is required, but missing"
        )
    ca_file = cfg['ca_file']
    if not path.isfile(ca_file):
        raise ValueError(
            "config['replicator']['ca_file'] not a file: {!r}".format(ca_file)
        )
    if 'cert_file' in cfg:
        if 'key_file' not in cfg:
            raise ValueError(
                "config['replicator']['key_file'] is required, but missing"
            )
        for key in ('cert_file', 'key_file'):
            value = cfg[key]
            if not path.isfile(value):
                raise ValueError(
                    "config['replicator'][{!r}] not a file: {!r}".format(
                        key, value)
                )


def build_config(auth, overrides=None):
    if auth not in TEMPLATES:
        raise ValueError('invalid auth: {!r}'.format(auth))
    config = dict(DEFAULT_CONFIG)
    if overrides:
        config.update(overrides)
    if config['file_compression'] not in FILE_COMPRESSION:
        raise ValueError("invalid config['file_compression']: {!r}".format(
                config['file_compression'])
        )
    if 'ssl' in config:
        check_ssl_config(config['ssl'])
    if 'replicator' in config:
        check_replicator_config(config['replicator'])
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


def netloc_template(bind_address):
    """
    Return a netloc template appropriate for *bind_address*

    For example, for IPv4:

    >>> netloc_template('127.0.0.1')
    '127.0.0.1:{}'
    >>> netloc_template('0.0.0.0')
    '127.0.0.1:{}'

    And for IPv6:

    >>> netloc_template('::1')
    '[::1]:{}'
    >>> netloc_template('::')
    '[::1]:{}'

    Also see `build_url()`.
    """
    if bind_address in ('127.0.0.1', '0.0.0.0'):
        return '127.0.0.1:{}'
    if bind_address in ('::1', '::'):
        return '[::1]:{}'
    raise ValueError('invalid bind_address: {!r}'.format(bind_address))


def build_url(scheme, bind_address, port):
    """
    Build appropriate URL for *scheme*, *bind_address*, and *port*.

    For example, an IPv4 HTTP URL:

    >>> build_url('http', '127.0.0.1', 5984)
    'http://127.0.0.1:5984/'

    And an IPv6 HTTPS URL:

    >>> build_url('https', '::1', 6984)
    'https://[::1]:6984/'

    Also see `netloc_template()`.
    """
    if scheme not in ('http', 'https'):
        raise ValueError(
            "scheme must be 'http' or 'https'; got {!r}".format(scheme)
        )
    netloc = netloc_template(bind_address).format(port)
    return ''.join([scheme, '://', netloc, '/'])


def build_env(auth, config, ports):
    if auth not in TEMPLATES:
        raise ValueError('invalid auth: {!r}'.format(auth))
    bind_address = config['bind_address']
    port = ports['port']
    env = {
        'port': ports['port'],
        'url': build_url('http', bind_address, port),
    }
    if auth in ('basic', 'oauth'):
        env['basic'] = {
            'username': config['username'],
            'password': config['password'],
        }
    if auth == 'oauth':
        env['oauth'] = config['oauth']
    if 'ssl_port' in ports:
        ssl_port = ports['ssl_port']
        env2 = deepcopy(env)
        env2['port'] = ssl_port
        env2['url'] = build_url('https', bind_address, ssl_port)
        env['x_env_ssl'] = env2
    return env


def build_template_kw(auth, config, ports, paths):
    if auth not in TEMPLATES:
        raise ValueError('invalid auth: {!r}'.format(auth))
    kw = {
        'bind_address': config['bind_address'],
        'loglevel': config['loglevel'],
        'file_compression': config['file_compression'],
        'databases': paths.databases,
        'views': paths.views,
        'logfile': paths.logfile,
    }
    kw.update(ports)
    if 'ssl' in config:
        ssl_cfg = config['ssl']
        for key in ['ca_file', 'cert_file', 'key_file']:
            if key in ssl_cfg:
                kw[key] = ssl_cfg[key]
    if 'replicator' in config:
        kw['replicator'] = config['replicator']
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
    if 'ssl_port' in kw:
        template += SSL
    if 'replicator' in kw:
        if 'cert_file' in kw['replicator']:
            template += REPLICATOR_EXTRA
        else:
            template += REPLICATOR
    return template.format(**kw)


def bind_socket(bind_address):
    """
    Bind a socket to *bind_address* and a random port.

    For IPv4, *bind_address* must be ``'127.0.0.1'`` to listen only internally,
    or ``'0.0.0.0'`` to accept outside connections.  For example:

    >>> sock = bind_socket('127.0.0.1')

    For IPv6, *bind_address* must be ``'::1'`` to listen only internally, or
    ``'::'`` to accept outside connections.  For example:

    >>> sock = bind_socket('::1')

    The random port will be chosen by the operating system based on currently
    available ports.
    """
    if bind_address in ('127.0.0.1', '0.0.0.0'):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    elif bind_address in ('::1', '::'):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    else:
        raise ValueError('invalid bind_address: {!r}'.format(bind_address))
    sock.bind((bind_address, 0))
    return sock


class Sockets:
    """
    A helper class to make it easy to deal with one or two random ports.
    """

    def __init__(self, bind_address):
        self.bind_address = bind_address
        self.socks = {'port': bind_socket(bind_address)}

    def add_ssl(self):
        self.socks['ssl_port'] = bind_socket(self.bind_address)

    def get_ports(self):
        return dict(
            (key, sock.getsockname()[1])
            for (key, sock) in self.socks.items()
        )

    def close(self):
        for sock in self.socks.values():
            sock.close()


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

    __slots__ = ('ini', 'databases', 'views', 'dump', 'ssl', 'log', 'logfile')

    def __init__(self, basedir):
        self.ini = path.join(basedir, 'session.ini')
        self.databases = mkdir(basedir, 'databases')
        self.views = mkdir(basedir, 'views')
        self.dump = mkdir(basedir, 'dump')
        self.ssl = mkdir(basedir, 'ssl')
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

    def bootstrap(self, auth='basic', config=None, extra=None):
        if self.__bootstraped:
            raise Exception(
                '{}.bootstrap() already called'.format(self.__class__.__name__)
            )
        self.__bootstraped = True
        config = build_config(auth, config)
        socks = Sockets(config['bind_address'])
        if 'ssl' in config:
            socks.add_ssl()
        ports = socks.get_ports()
        env = build_env(auth, config, ports)
        kw = build_template_kw(auth, config, ports, self.paths)
        session_ini = build_session_ini(auth, kw)
        if extra:
            session_ini += extra
        open(self.paths.ini, 'w').write(session_ini)
        self._conn = get_conn(env)
        self._headers = get_headers(env)
        socks.close()
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
