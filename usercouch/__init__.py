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
import signal
import os
from os import path
import stat
import time
from subprocess import Popen

from microfiber import Server, random_id


__version__ = '11.10.0'


template = """
[couch_httpd_auth]
require_valid_user = true

[httpd]
bind_address = 127.0.0.1
port = {port}
socket_options = '[{{recbuf, 262144}}, {{sndbuf, 262144}}, {{nodelay, true}}]'

[couchdb]
database_dir = {databases}
view_index_dir = {views}

[log]
file = {logfile}
level = {loglevel}

[admins]
{username} = {hashed}

[oauth_token_users]
{token} = {username}

[oauth_token_secrets]
{token} = {token_secret}

[oauth_consumer_secrets]
{consumer_key} = {consumer_secret}

[httpd_global_handlers]
_stats =

[daemons]
stats_collector =
stats_aggregator =

[stats]
rate =
samples =
"""


def random_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
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


def on_sigterm(signum, frame):
    print('kill')


signal.signal(signal.SIGTERM, on_sigterm)


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
    def __init__(self, basedir):
        self.ini = path.join(basedir, 'session.ini')
        self.databases = mkdir(basedir, 'databases')
        self.views = mkdir(basedir, 'views')
        self.log = mkdir(basedir, 'log')
        self.logfile = logfile(self.log, 'couchdb.log')


class UserCouch:
    def __init__(self, basedir):
        self.couchdb = None
        if not path.isdir(basedir):
            raise ValueError('{}.basedir not a directory: {!r}'.format(
                self.__class__.__name__, basedir)
            )
        self.basedir = basedir

    def __del__(self):
        self.kill()

    def kill(self):
        if self.couchdb is None:
            return False
        self.couchdb.terminate()
        self.couchdb.wait()
        self.couchdb = None
        return True

    def start(self):
        if self.couchdb is not None:
            return False
        self.couchdb = Popen(self.cmd)
        # We give CouchDB ~10.9 seconds to start:
        t = 0.1
        for i in range(15):
            time.sleep(t)
            t *= 1.25
            if self.isalive():
                return True
        raise Exception('could not start CouchDB')

    def isalive(self):
        try:
            self.server.get()
            return True
        except socket.error:
            return False


