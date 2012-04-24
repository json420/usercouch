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
from copy import deepcopy
from hashlib import sha1, md5

from microfiber import Server, NotFound, random_id


__version__ = '12.05.0'

# local doc ID for the usercouch admin doc, used for UserCouch.autocompact():
ADMIN_ID = '_local/usercouch'

OPEN = """
[httpd]
bind_address = {address}
port = {port}
socket_options = [{{recbuf, 262144}}, {{sndbuf, 262144}}, {{nodelay, true}}]

[couchdb]
database_dir = {databases}
view_index_dir = {views}
uri_file =

[log]
file = {logfile}
level = {loglevel}

[httpd_global_handlers]
_apps = {{couch_httpd_misc_handlers, handle_utils_dir_req, "/usr/share/couchdb/apps"}}
_stats =

[daemons]
stats_collector =
stats_aggregator =

[stats]
rate =
samples =
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


def get_template(auth):
    if auth == 'open':
        return OPEN
    if auth == 'basic':
        return BASIC
    if auth == 'oauth':
        return OAUTH
    raise ValueError('invalid auth: {!r}'.format(auth))


def random_port(address='127.0.0.1'):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((address, 0))
    port = sock.getsockname()[1]
    return (sock, port)


def random_oauth():
    return dict(
        (k, random_id())
        for k in ('consumer_key', 'consumer_secret', 'token', 'token_secret')
    )


def random_basic():
    return dict(
        (k, random_id())
        for k in ('username', 'password')
    )


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


def random_salt():
    return md5(os.urandom(16)).hexdigest()


def couch_hashed(password, salt):
    assert len(salt) == 32
    data = (password + salt).encode('utf-8')
    hexdigest = sha1(data).hexdigest()
    return '-hashed-{},{}'.format(hexdigest, salt)


def get_cmd(ini):
    return [
        '/usr/bin/couchdb',
        '-n',  # reset configuration file chain (including system default)
        '-a', '/etc/couchdb/default.ini',
        '-a', ini,
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
        self.server = None
        self.__bootstraped = False

    def __del__(self):
        self.kill()

    def bootstrap(self, auth='basic', address='127.0.0.1', tokens=None, loglevel='notice'):
        if self.__bootstraped:
            raise Exception(
                '{}.bootstrap() already called'.format(self.__class__.__name__)
            )
        self.__bootstraped = True
        (sock, port) = random_port(address)
        env = random_env(port, auth, tokens)
        self.server = Server(env)
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
        sock.close()
        self.start()
        return deepcopy(env)

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
        # We give CouchDB ~10.9 seconds to start:
        t = 0.1
        for i in range(20):
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

    def isalive(self):
        if not self.__bootstraped:
            raise Exception(
                'Must call {0}.bootstrap() before {0}.isalive()'.format(
                        self.__class__.__name__)
            )
        try:
            self.server.get()
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

    def autocompact(self):
        if not self.__bootstraped:
            raise Exception(
                'Must call {0}.bootstrap() before {0}.autocompact()'.format(
                        self.__class__.__name__)
            )
        s = Server(self.server.env)
        compacted = []
        for name in s.get('_all_dbs'):
            if name.startswith('_'):
                continue
            db = s.database(name)
            try:
                doc = db.get(ADMIN_ID)
            except NotFound:
                doc = {
                    '_id': ADMIN_ID,
                    'compact_seq': 0,
                }
                db.save(doc)
            update_seq = db.get()['update_seq']
            compact_seq = doc.get('compact_seq', 0)
            if update_seq > compact_seq + 500:
                compacted.append(name)
                doc['compact_seq'] = update_seq
                doc['compact_time'] = time.time()
                db.save(doc)
                db.post(None, '_compact')
        return compacted

