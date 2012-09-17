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
`TempCouch` and `CouchTestCase`.
"""

from unittest import TestCase
import tempfile
import shutil
from os import path

from usercouch import UserCouch, random_b32
from usercouch.sslhelpers import PKIHelper


class TempPKI(PKIHelper):
    def __init__(self, client_pki=False):
        ssldir = tempfile.mkdtemp(prefix='TempPKI.')
        super().__init__(ssldir)
        self.load_server(random_b32(), random_b32())
        if client_pki:
            self.load_client(random_b32(), random_b32())

    def __del__(self):
        if path.isdir(self.ssldir):
            shutil.rmtree(self.ssldir)


class TempCouch(UserCouch):
    def __init__(self):
        basedir = tempfile.mkdtemp(prefix='TempCouch.')
        super().__init__(basedir)
        assert self.basedir == basedir

    def __del__(self):
        super().__del__()
        if path.isdir(self.basedir):
            shutil.rmtree(self.basedir)


class CouchTestCase(TestCase):
    auth = 'basic'
    bind_address = '127.0.0.1'

    def setUp(self):
        self.tmpcouch = TempCouch()
        self.env = self.tmpcouch.bootstrap(self.auth,
            {'bind_address': self.bind_address}
        )

    def tearDown(self):
        self.tmpcouch = None
        self.env = None
        
