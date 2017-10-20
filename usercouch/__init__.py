# usercouch: Starts per-user CouchDB instances for fun and unit testing
# Copyright (C) 2011-2016 Novacut Inc
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
from hashlib import sha1, pbkdf2_hmac
import binascii
from base64 import b64encode
import json
from collections import namedtuple

from dbase32 import random_id
from degu.client import Client


__version__ = '17.09.0'


def _check_for_couchdb2(rootdir):
    couch2 = path.join(rootdir, 'opt', 'couchdb', 'bin', 'couchdb')
    if path.isfile(couch2):
        return True
    couch1 = path.join(rootdir, 'usr', 'bin', 'couchdb')
    if path.isfile(couch1):
        return False
    raise RuntimeError(
        'No CouchDB? Checked:\n{!r}\n{!r}'.format(couch2, couch1)
    )


class CouchVersion:
    __slots__ = ('rootdir', '_couchdb2')

    def __init__(self, rootdir='/'):
        self.rootdir = rootdir
        self._couchdb2 = None

    @property
    def couchdb2(self):
        if self._couchdb2 is None:
            self._couchdb2 = _check_for_couchdb2(self.rootdir)
        assert type(self._couchdb2) is bool
        return self._couchdb2


couch_version = CouchVersion()
StartData = namedtuple('StartData', 'erts app')

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

OPEN = """
[couchdb]
uuid = {uuid}
database_dir = {databases}
view_index_dir = {views}
file_compression = {file_compression}
delayed_commits = true
uri_file =

[httpd]
allow_jsonp	= false
bind_address = {bind_address}
port = {port}
socket_options = [{{recbuf, 262144}}, {{sndbuf, 262144}}, {{nodelay, true}}]
config_whitelist = [] ; Don't allow any config changes through REST API
authentication_handlers	= {{couch_httpd_auth, cookie_authentication_handler}}, {{couch_httpd_auth, default_authentication_handler}}

[log]
file = {logfile}
level = {loglevel}

[database_compaction]
doc_buffer_size = 4194304 ; 4 MiB
checkpoint_after = 8388608 ; 8 MiB

[compaction_daemon]
check_interval = 300 ; 5 minutes (5 * 60)
min_file_size = 1048576 ; 1 MiB

[compactions]
_default = [{{db_fragmentation, "60%"}}, {{view_fragmentation, "60%"}}]
"""

OPEN_1 = """
[replicator]
socket_options = [{{recbuf, 262144}}, {{sndbuf, 262144}}, {{nodelay, true}}]
max_replication_retry_count = 20 ; default is 10
worker_batch_size = 250 ; default is 500
http_connections = 10 ; default is 20 (we want more connection reuse)
"""

OPEN_2 = """
[query_servers]
javascript = /opt/couchdb/bin/couchjs /opt/couchdb/share/server/main.js

[chttpd]
bind_address = {bind_address}
port = {chttpd_port}
docroot	= /opt/couchdb/share/www

[cluster]
q = 1
r = 1
w = 1
n = 1
"""

BASIC = """
[couch_httpd_auth]
require_valid_user = true

[admins]
{username} = {hashed}
"""

OAUTH = """
[oauth_token_users]
{token} = {username}

[oauth_token_secrets]
{token} = {token_secret}

[oauth_consumer_secrets]
{consumer_key} = {consumer_secret}
"""

VERSION_TEMPLATE = {
    1: {
        'open': (OPEN, OPEN_1),
        'basic': (OPEN, OPEN_1, BASIC),
        'oauth': (OPEN, OPEN_1, BASIC, OAUTH),
    },
    2: {
        'open': (OPEN, OPEN_2),
        'basic': (OPEN, OPEN_2, BASIC),
        'oauth': (OPEN, OPEN_2, BASIC, OAUTH),
    },
}


def check_auth(version, auth):
    templates = VERSION_TEMPLATE[version]
    value = templates.get(auth)
    if value is None:
        raise ValueError('invalid auth: {!r}'.format(auth))
    return value


def get_template(version, auth):
    parts = check_auth(version, auth)
    return ''.join(parts)


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

ALLOW_CONFIG = """
[httpd]
config_whitelist =
"""

VM_ARGS = """
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

# Each node in the system must have a unique name.  A name can be short
# (specified using -sname) or it can by fully qualified (-name).  There can be
# no communication between nodes running with the -sname flag and those running 
# with the -name flag.
#-name {uuid}@localhost

# All nodes must share the same magic cookie for distributed Erlang to work.
# Comment out this line if you synchronized the cookies by other means (using
# the ~/.erlang.cookie file, for example).
#-setcookie monster

# http://erlang.org/doc/man/erl.html
-start_epmd false

# Tell kernel and SASL not to log anything
-kernel error_logger silent
-sasl sasl_error_logger false

# Use kernel poll functionality if supported by emulator
+K true

# Start a pool of asynchronous IO threads
+A 16

# Comment this line out to enable the interactive Erlang shell on startup
+Bd -noinput
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


def tohex(data):
    return binascii.hexlify(data).decode()


def random_salt():
    """
    Return a 128-bit hex-encoded random salt for use  by `couch_hashed()`.
    """
    return tohex(os.urandom(16))


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


def couch_pbkdf2(password, salt, rounds=10):
    """
    Hash *password* using *salt* with PKCS#5 password-based key derivation.

    This returns a CouchDB-style pbkdf2 hashed password to be use in the
    session.ini file.  For example:

    >>> couch_pbkdf2('password', 'salt', 1)
    '-pbkdf2-0c60c80f961f0e71f3a9b524af6012062fe037a6,salt,1'

    Typically `UserCouch` is used with a per-session random password, so this
    function means that the clear-text of the password is only stored in
    memory, is never written to disk.

    .. note:

        As of CouchDB 1.6.0, it seems we can no longer start CouchDB using a
        ``'-hashed-<digest>,<salt>'`` style hashed password as produced by
        `couch_hashed()`.
    """
    assert isinstance(password, str)
    assert isinstance(salt, str)
    digest = pbkdf2_hmac('sha1', password.encode(), salt.encode(), rounds)
    return '-pbkdf2-{},{},{}'.format(tohex(digest), salt, rounds)


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
    check_auth(1, auth)
    config = dict(DEFAULT_CONFIG)
    if overrides:
        config.update(overrides)
    if 'uuid' not in config:
        config['uuid'] = random_salt()
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


def _basic_authorization(basic):
    b = '{username}:{password}'.format(**basic).encode()
    b64 = b64encode(b).decode()
    return 'Basic ' + b64


def build_env(auth, config, ports):
    check_auth(1, auth)
    bind_address = config['bind_address']
    port = ports['port']
    env = {
        'port': port,
        'address': (bind_address, port),
        'url': build_url('http', bind_address, port),
    }
    if 'chttpd_port' in ports:
        env['chttpd_address'] = (bind_address, ports['chttpd_port'])
    if auth in ('basic', 'oauth'):
        env['basic'] = {
            'username': config['username'],
            'password': config['password'],
        }
        env['authorization'] = _basic_authorization(env['basic'])
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
    check_auth(1, auth)
    kw = {
        'bind_address': config['bind_address'],
        'loglevel': config['loglevel'],
        'file_compression': config['file_compression'],
        'uuid': config['uuid'],
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
        kw['hashed'] = couch_pbkdf2(config['password'], config['salt'])
    if auth == 'oauth':
        kw.update(config['oauth'])
    return kw


def build_session_ini(version, auth, kw):
    template = get_template(version, auth)
    if 'ssl_port' in kw:
        template += SSL
    if 'replicator' in kw:
        if 'cert_file' in kw['replicator']:
            template += REPLICATOR_EXTRA
        else:
            template += REPLICATOR
    return template.format(**kw)


def build_vm_args(kw):
    return VM_ARGS.format(**kw)


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
    Helper class to make it easy to deal with one or more random ports.
    """

    __slots__ = ('bind_address', 'socks')

    def __init__(self, bind_address):
        self.bind_address = bind_address
        self.socks = {}
        self.add_port('port')
        if couch_version.couchdb2:
            self.add_port('chttpd_port')

    def add_port(self, name):
        assert isinstance(name, str)
        assert name not in self.socks
        self.socks[name] = bind_socket(self.bind_address)

    def add_ssl(self):
        self.add_port('ssl_port')

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
        '-a', session_ini,
    ]


def read_start_data(prefix='/opt/couchdb'):
    filename = path.join(prefix, 'releases', 'start_erl.data')
    with open(filename, 'r') as fp:
        content = fp.read(4096)
        items = content.split()
        assert len(items) == 2
        return StartData(*items)


def build_environ(sd, prefix='/opt/couchdb'):
    assert isinstance(sd, StartData)
    return {
        'ROOTDIR': prefix,
        'BINDIR': path.join(prefix, 'erts-' + sd.erts, 'bin'),
        'EMU': 'beam',
        'PROGNAME': 'couchdb'
    }


def build_command(paths, sd, environ):
    appdir = path.join(environ['ROOTDIR'], 'releases', sd.app)
    return [
        path.join(environ['BINDIR'], 'erlexec'),
        '-boot', path.join(appdir, 'couchdb'),
        '-args_file', paths.vm_args,
        '-config', path.join(appdir, 'sys.config'),
        '-couch_ini', '/etc/couchdb/default.ini', paths.ini,
    ]


def start_couchdb(paths, prefix='/opt/couchdb'):
    if couch_version.couchdb2:
        sd = read_start_data(prefix)
        environ = dict(os.environ)
        environ.update(build_environ(sd, prefix))
        command = build_command(paths, sd, environ)
    else:
        command = get_cmd(paths.ini)
        environ = None
    return Popen(command, env=environ)


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

    __slots__ = (
        'ini',
        'vm_args',
        'databases',
        'views',
        'dump',
        'ssl',
        'log',
        'logfile',
    )

    def __init__(self, basedir):
        self.ini = path.join(basedir, 'session.ini')
        self.vm_args = path.join(basedir, 'vm.args')
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
    return {'authorization': _basic_authorization(basic)}


def get_headers(env):
    headers = {'accept': 'application/json'}
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
        version = (2 if couch_version.couchdb2 else 1)
        session_ini = build_session_ini(version, auth, kw)
        if extra:
            session_ini += extra
        open(self.paths.ini, 'w').write(session_ini)
        if couch_version.couchdb2:
            open(self.paths.vm_args, 'w').write(build_vm_args(kw))
        address = (env['chttpd_address'] if 'chttpd_address' in env else env['address'])
        self._client = Client(address,
            host=None,
            authorization=env.get('authorization'),
        )
        self._client.set_base_header('accept', 'application/json')
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
        self.couchdb = start_couchdb(self.paths)
        # We give CouchDB ~67 seconds to start:
        t = 0.1
        for i in range(5):
            time.sleep(t)
            t *= 1.25
            if self.isalive():
                if couch_version.couchdb2:
                    self._request('PUT', '/_users')
                    self._request('PUT', '/_replicator')
                    self._request('PUT', '/_global_changes')
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
        conn = self._client.connect()
        try:
            response = conn.request(method, path, {}, None)
            data = (response.body.read() if response.body else b'')
        finally:
            conn.close()   
        if response.status >= 400:
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
        except OSError:
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

